"""
服装录入链路单元测试（不发真实网络请求）。

覆盖：
- image_generation 的请求体分支与响应解析
- garment_analysis 的结果归一化
- garment_crop 的 bbox 裁剪
- garment_canonical 的生图失败降级
- capture API 的 analyze / commit 流程（patch 服务 + 临时 DB）

运行：
    cd backend && source venv/bin/activate && python -m unittest test_capture_pipeline.py
"""
import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image

import storage.db as db
import services.garment_analysis as ga
import services.garment_canonical as gcanon
import services.garment_crop as gc
import services.image_generation as ig
from domain.clothes import ClothesSemantics
from domain.garments import GarmentCandidate, GarmentSpec
from services.openai_compatible import normalize_semantics_payload


def _png_bytes(width: int = 100, height: int = 100, color=(120, 120, 120)) -> bytes:
    image = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


class ImageGenerationPayloadTest(unittest.TestCase):
    def test_detect_provider(self):
        self.assertEqual(ig.detect_provider("qwen-image-3.0-pro"), "qwen")
        self.assertEqual(ig.detect_provider("doubao-seedream-5.0-lite"), "doubao")
        self.assertEqual(ig.detect_provider("some-other-model"), "flat")

    def test_qwen_payload_with_reference(self):
        payload, provider = ig.build_payload(
            model="qwen-image-3.0-pro",
            prompt="flat lay",
            category="top",
            references=["data:image/png;base64,AAAA"],
            negative_prompt="person",
        )
        self.assertEqual(provider, "qwen")
        self.assertNotIn("prompt", payload)
        content = payload["input"]["messages"][0]["content"]
        self.assertEqual(content[-1]["text"], "flat lay")
        self.assertEqual(payload["parameters"]["size"], "1728*2368")
        self.assertEqual(payload["parameters"]["negative_prompt"], "person")

    def test_doubao_payload_with_reference(self):
        payload, provider = ig.build_payload(
            model="doubao-seedream-5.0-lite",
            prompt="flat lay",
            category="shoes",
            references=["data:image/png;base64,AAAA"],
        )
        self.assertEqual(provider, "doubao")
        self.assertEqual(payload["prompt"], "flat lay")
        self.assertEqual(payload["image"], ["data:image/png;base64,AAAA"])
        self.assertEqual(payload["size"], "2048x2048")

    def test_flat_payload_without_reference(self):
        payload, provider = ig.build_payload(
            model="qwen-image-3.0-pro",
            prompt="a cat",
            category="bottom",
        )
        self.assertEqual(provider, "qwen")
        self.assertEqual(payload["prompt"], "a cat")
        self.assertEqual(payload["size"], "1728x2368")


class ExtractImageResultTest(unittest.TestCase):
    def test_qwen_metadata(self):
        data = {
            "metadata": {
                "output": {
                    "choices": [
                        {"message": {"content": [{"image": "https://cdn/1.png"}]}}
                    ]
                }
            }
        }
        self.assertEqual(ig.extract_image_result(data), ("url", "https://cdn/1.png"))

    def test_openai_data_url(self):
        data = {"data": [{"url": "https://cdn/2.png"}]}
        self.assertEqual(ig.extract_image_result(data), ("url", "https://cdn/2.png"))

    def test_b64(self):
        data = {"data": [{"b64_json": "aGVsbG8="}]}
        self.assertEqual(ig.extract_image_result(data), ("b64", "aGVsbG8="))

    def test_nested_fallback(self):
        data = {"data": {"content": {"url": "https://cdn/3.png"}}}
        self.assertEqual(ig.extract_image_result(data), ("url", "https://cdn/3.png"))

    def test_missing(self):
        self.assertIsNone(ig.extract_image_result({"data": []}))


class NormalizeGarmentsTest(unittest.TestCase):
    def test_full_payload(self):
        parsed = {
            "garments": [
                {
                    "id": "g1",
                    "category": "top",
                    "item": "T恤",
                    "description": "black tee",
                    "spec": {"color": "black", "details": ["print"]},
                    "bbox": [100, 200, 500, 800],
                }
            ]
        }
        result = ga.normalize_garments(parsed)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].garment_key, "g1")
        self.assertEqual(result[0].category, "top")
        # 0-1000 归一化应缩放到 0-1
        self.assertAlmostEqual(result[0].bbox[0], 0.1)
        self.assertEqual(result[0].spec.color, "black")

    def test_invalid_bbox_dropped(self):
        parsed = {"garments": [{"category": "shoes", "item": "鞋", "bbox": [0.5, 0.5, 0.2, 0.2]}]}
        result = ga.normalize_garments(parsed)
        self.assertIsNone(result[0].bbox)

    def test_category_fallback(self):
        parsed = {"garments": [{"category": "weird", "item": "something"}]}
        result = ga.normalize_garments(parsed)
        self.assertEqual(result[0].category, "accessory")

    def test_empty(self):
        self.assertEqual(ga.normalize_garments({"garments": []}), [])


class NormalizeSemanticsTest(unittest.TestCase):
    def test_string_lists_and_unknown(self):
        result = normalize_semantics_payload({
            "category": "top",
            "item": "T恤",
            "style_semantics": "休闲、正式",
            "season_semantics": ["夏"],
            "usage_semantics": "unknown",
            "color_semantics": "unknown",
            "description": "一件T恤",
        })
        self.assertEqual(result["style_semantics"], ["休闲", "正式"])
        self.assertEqual(result["season_semantics"], ["夏"])
        self.assertEqual(result["usage_semantics"], [])
        self.assertEqual(result["color_semantics"], "")
        self.assertEqual(result["category"], "top")

    def test_missing_fields(self):
        result = normalize_semantics_payload({})
        self.assertEqual(result["category"], "accessory")
        self.assertEqual(result["style_semantics"], [])
        self.assertEqual(result["description"], "")


class GarmentCropTest(unittest.TestCase):
    def test_crop_by_bbox(self):
        cropped = gc.crop_by_bbox(_png_bytes(200, 200), [0.2, 0.2, 0.8, 0.8])
        self.assertIsNotNone(cropped)
        image = Image.open(io.BytesIO(cropped))
        self.assertLess(image.width, 200)
        self.assertLess(image.height, 200)

    def test_invalid_bbox(self):
        self.assertIsNone(gc.crop_by_bbox(_png_bytes(), [0.5, 0.5, 0.5, 0.5]))

    def test_reference_prefers_bbox(self):
        reference = gc.crop_garment_reference(
            _png_bytes(200, 200), [0.1, 0.1, 0.9, 0.9], allow_mask_fallback=False
        )
        self.assertIsNotNone(reference)


class CanonicalFallbackTest(unittest.TestCase):
    def test_build_description_with_empty_description(self):
        # description 为空时不得抛异常，应回退用 spec + item 拼接
        text = gcanon.build_description(GarmentSpec(color="black"), "T恤", "")
        self.assertIn("black", text)
        self.assertIn("T恤", text)

    def test_build_description_uses_given_description(self):
        self.assertEqual(
            gcanon.build_description(GarmentSpec(), "T恤", "black tee"), "black tee"
        )

    def test_build_canonical_prompt_does_not_raise(self):
        prompt = gcanon.build_canonical_prompt("", "top", "")
        self.assertIn("SAME physical garment", prompt)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

        self.patchers = [
            patch.object(gcanon, "UPLOAD_DIR", root),
            patch.object(gcanon, "SOURCE_DIR", root / "source"),
            patch.object(gcanon, "REFERENCE_DIR", root / "reference"),
            patch.object(gcanon, "GENERATED_DIR", root / "generated"),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_fallback_when_generation_fails(self):
        config = SimpleNamespace(image_model="qwen-image-3.0-pro")

        async def boom(**kwargs):
            raise RuntimeError("generation failed")

        with patch.object(gcanon, "load_config", return_value=config), \
                patch.object(gcanon, "generate_image", side_effect=boom), \
                patch.object(gcanon, "alpha_or_original", side_effect=lambda data: data):
            result = asyncio.run(
                gcanon.generate_canonical_garment(
                    source_image_bytes=b"source",
                    reference_image_bytes=b"reference",
                    spec=GarmentSpec(),
                    category="top",
                    item="T恤",
                    description="black tee",
                )
            )

        self.assertEqual(result["status"], "fallback")
        self.assertTrue(result["alpha_filename"])
        self.assertIn("generation failed", result["error"])

    def test_done_when_generation_succeeds(self):
        config = SimpleNamespace(image_model="qwen-image-3.0-pro")

        async def fake_generate(**kwargs):
            return b"generated-image"

        with patch.object(gcanon, "load_config", return_value=config), \
                patch.object(gcanon, "generate_image", side_effect=fake_generate), \
                patch.object(gcanon, "alpha_or_original", side_effect=lambda data: data):
            result = asyncio.run(
                gcanon.generate_canonical_garment(
                    source_image_bytes=b"source",
                    reference_image_bytes=b"reference",
                    spec=GarmentSpec(),
                    category="top",
                    item="T恤",
                    description="black tee",
                )
            )

        self.assertEqual(result["status"], "done")
        self.assertTrue(result["generated_filename"])
        self.assertTrue(result["alpha_filename"])


class CaptureApiTest(unittest.TestCase):
    def setUp(self):
        import main
        from fastapi.testclient import TestClient

        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root
        self.addCleanup(self.tmp.cleanup)

        self.db_patcher = patch.object(db, "DB_PATH", root / "test.db")
        self.db_patcher.start()
        self.addCleanup(self.db_patcher.stop)

        import api.capture as capture

        self.source_patcher = patch.object(capture, "SOURCE_DIR", root / "source")
        self.reference_patcher = patch.object(capture, "REFERENCE_DIR", root / "reference")
        self.source_patcher.start()
        self.reference_patcher.start()
        self.addCleanup(self.source_patcher.stop)
        self.addCleanup(self.reference_patcher.stop)

        self.client = TestClient(main.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)

    def test_analyze(self):
        candidate = GarmentCandidate(
            garment_key="garment_01",
            category="top",
            item="T恤",
            description="black tee",
            spec=GarmentSpec(color="black"),
            bbox=[0.1, 0.1, 0.9, 0.9],
        )

        async def fake_analyze(image_bytes, mime=None):
            return [candidate]

        with patch("api.capture.analyze_person_image", side_effect=fake_analyze), \
                patch("api.capture.crop_garment_reference", return_value=_png_bytes()):
            response = self.client.post(
                "/api/capture/analyze",
                files={"file": ("person.png", _png_bytes(), "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["garments"]), 1)
        self.assertEqual(body["garments"][0]["garment_key"], "garment_01")
        self.assertTrue(body["garments"][0]["crop_url"].startswith("/uploads/reference/"))

    def test_commit_creates_clothes(self):
        session_id = "sess-test"
        image_filename = "final.png"

        async def setup():
            await db.create_garment_session(session_id, "source.png", {"garments": []})
            await db.create_garment_draft(
                session_id=session_id,
                garment_key="garment_01",
                category="top",
                item="T恤",
                description="black tee",
                spec=GarmentSpec(color="black").model_dump(),
                bbox=None,
                crop_filename=None,
            )
            await db.update_garment_draft(
                session_id, "garment_01", status="done", alpha_filename=image_filename
            )

        asyncio.run(setup())

        response = self.client.post(
            "/api/capture/commit",
            json={
                "session_id": session_id,
                "items": [
                    {
                        "garment_key": "garment_01",
                        "category": "top",
                        "item": "T恤",
                        "description": "black tee",
                        "selected": True,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["created"]), 1)
        self.assertEqual(body["created"][0]["item"], "T恤")
        self.assertEqual(body["created"][0]["image_url"], "/uploads/final.png")

    def test_commit_fills_chinese_semantics(self):
        session_id = "sess-semantics"
        image_filename = "final.png"
        # 写入真实图片，让语义分析有可读素材
        (self.root / image_filename).write_bytes(_png_bytes())

        async def setup():
            await db.create_garment_session(session_id, "source.png", {"garments": []})
            await db.create_garment_draft(
                session_id=session_id,
                garment_key="g1",
                category="top",
                item="T恤",
                description="black oversized tee",
                spec=GarmentSpec(color="black").model_dump(),
                bbox=None,
                crop_filename=None,
            )
            await db.update_garment_draft(
                session_id, "g1", status="done", alpha_filename=image_filename
            )

        asyncio.run(setup())

        fake_semantics = ClothesSemantics(
            category="top",
            item="T恤",
            style_semantics=["休闲"],
            season_semantics=["夏"],
            usage_semantics=["日常"],
            color_semantics="深色系",
            description="黑色宽松短袖T恤，适合夏季日常穿着。",
        )

        with patch(
            "api.capture.analyze_clothes_openai",
            new=AsyncMock(return_value=fake_semantics),
        ):
            response = self.client.post(
                "/api/capture/commit",
                json={
                    "session_id": session_id,
                    "items": [
                        {"garment_key": "g1", "category": "top", "item": "T恤", "selected": True}
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        created = response.json()["created"][0]
        self.assertEqual(created["style_semantics"], ["休闲"])
        self.assertEqual(created["season_semantics"], ["夏"])
        self.assertEqual(created["usage_semantics"], ["日常"])
        self.assertEqual(created["color_semantics"], "深色系")
        self.assertEqual(created["description"], "黑色宽松短袖T恤，适合夏季日常穿着。")


if __name__ == "__main__":
    unittest.main()