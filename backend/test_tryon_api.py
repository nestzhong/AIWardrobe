"""
AI 试穿接口测试（以图生图，统一入口）。

用 patch 替换模块级符号 + 临时目录隔离，不触网、不落真实 uploads。
"""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


def _garment(garment_id: int, category: str, item: str):
    return SimpleNamespace(
        id=garment_id,
        category=category,
        item=item,
        description=f"{item} description",
        image_url="/uploads/garment.png",
    )


class TryOnApiTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_dir = Path(self.temp_dir.name) / "uploads"
        tryon_dir = self.upload_dir / "tryon"
        tryon_dir.mkdir(parents=True, exist_ok=True)
        (self.upload_dir / "garment.png").write_bytes(b"garment-bytes")

        self.generate_mock = AsyncMock(return_value=b"generated-image")

        self.active_patches = [
            patch("api.tryon.UPLOAD_DIR", self.upload_dir),
            patch("api.tryon.TRYON_DIR", tryon_dir),
            patch(
                "api.tryon.load_config",
                return_value=SimpleNamespace(person_image_filename="person.png"),
            ),
            patch(
                "services.tryon.load_config",
                return_value=SimpleNamespace(image_model="test-image-model"),
            ),
            patch("services.tryon.generate_image", new=self.generate_mock),
        ]
        for active in self.active_patches:
            active.start()

    def tearDown(self):
        for active in self.active_patches:
            active.stop()
        self.temp_dir.cleanup()

    def test_missing_person_image_returns_400(self):
        with patch("api.tryon.load_person_image_bytes", return_value=None):
            response = self.client.post("/api/tryon", json={"garment_ids": [1]})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "PERSON_IMAGE_MISSING")
        self.generate_mock.assert_not_called()

    def test_single_garment_uses_person_and_one_reference(self):
        with patch("api.tryon.load_person_image_bytes", return_value=b"person-bytes"), \
                patch("api.tryon.get_clothes_by_id", new=AsyncMock(return_value=_garment(1, "top", "Jacket"))):
            response = self.client.post("/api/tryon", json={"garment_ids": [1]})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["result_image_url"].startswith("/uploads/tryon/"))

        kwargs = self.generate_mock.await_args.kwargs
        self.assertEqual(kwargs["model"], "test-image-model")
        self.assertEqual(kwargs["category"], "tryon")
        self.assertEqual(kwargs["reference_images"], [b"person-bytes", b"garment-bytes"])

    def test_single_garment_prompt_contains_garment_reference(self):
        with patch("api.tryon.load_person_image_bytes", return_value=b"person-bytes"), \
                patch("api.tryon.get_clothes_by_id", new=AsyncMock(return_value=_garment(1, "top", "Jacket"))):
            self.client.post("/api/tryon", json={"garment_ids": [1]})

        prompt = self.generate_mock.await_args.kwargs["prompt"]
        self.assertIn("Image 1 is a photo of a person", prompt)
        self.assertIn("upper body garment", prompt)
        self.assertIn("Jacket description", prompt)

    def test_outfit_with_three_garments(self):
        garments = {
            1: _garment(1, "top", "Jacket"),
            2: _garment(2, "bottom", "Jeans"),
            3: _garment(3, "shoes", "Sneakers"),
        }

        async def fake_get(garment_id):
            return garments.get(garment_id)

        with patch("api.tryon.load_person_image_bytes", return_value=b"person-bytes"), \
                patch("api.tryon.get_clothes_by_id", new=AsyncMock(side_effect=fake_get)):
            response = self.client.post("/api/tryon", json={"garment_ids": [1, 2, 3]})

        self.assertEqual(response.status_code, 200)
        kwargs = self.generate_mock.await_args.kwargs
        self.assertEqual(len(kwargs["reference_images"]), 4)
        self.assertIn("lower body garment", kwargs["prompt"])
        self.assertIn("pair of shoes", kwargs["prompt"])

    def test_unknown_garment_returns_404(self):
        with patch("api.tryon.load_person_image_bytes", return_value=b"person-bytes"), \
                patch("api.tryon.get_clothes_by_id", new=AsyncMock(return_value=None)):
            response = self.client.post("/api/tryon", json={"garment_ids": [999]})

        self.assertEqual(response.status_code, 404)

    def test_missing_garment_file_returns_404(self):
        garment = _garment(1, "top", "Jacket")
        garment.image_url = "/uploads/does-not-exist.png"

        with patch("api.tryon.load_person_image_bytes", return_value=b"person-bytes"), \
                patch("api.tryon.get_clothes_by_id", new=AsyncMock(return_value=garment)):
            response = self.client.post("/api/tryon", json={"garment_ids": [1]})

        self.assertEqual(response.status_code, 404)

    def test_empty_garment_ids_rejected(self):
        response = self.client.post("/api/tryon", json={"garment_ids": []})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()