"""
P0 去风险脚本：直连真实网关，验证服装录入链路的关键假设。

验证 3 件事：
1. 识别模型（qwen3.8-flash）是否接受 base64 图片输入。
2. 生图接口（/images/generations）是否接受 base64 参考图。
3. watermark=False 是否被接受（文档写固定 true；输出图片需人工检查是否带水印）。

注意：这是真调脚本，会消耗网关额度，**不纳入 CI**（同 test_weather.py 的定位）。

用法：
    cd backend && source venv/bin/activate
    python test_garment_capture.py                 # 跑全部
    python test_garment_capture.py --vision-only   # 只测识别
    python test_garment_capture.py --model qwen-image-3.0-pro
"""
import argparse
import asyncio
import sys
from pathlib import Path

DEMO_DIR = Path(__file__).parent / "uploads" / "demo"
OUTPUT_DIR = Path(__file__).parent / "uploads" / "generated"


def _pick_demo_image() -> bytes:
    for name in ("sample_top_hoodie.png", "sample_bottom_pants.png", "sample_shoes_sneaker.png"):
        path = DEMO_DIR / name
        if path.is_file():
            return path.read_bytes()
    raise FileNotFoundError(f"未找到 demo 图片: {DEMO_DIR}")


async def test_vision(image_bytes: bytes) -> bool:
    from services.garment_analysis import analyze_person_image

    print("\n[1/3] 识别 base64 图片 ...")
    try:
        garments = await analyze_person_image(image_bytes)
        print(f"  ✅ 识别成功，得到 {len(garments)} 件服饰")
        for garment in garments:
            print(f"     - {garment.garment_key}: {garment.category} / {garment.item} bbox={garment.bbox}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 识别失败: {exc}")
        return False


async def test_image_base64(image_bytes: bytes, model: str) -> bool:
    from services.image_generation import generate_image

    print(f"\n[2/3] 生图 base64 参考图（model={model}, watermark=False）...")
    prompt = (
        "Generate a complete standalone product image of the garment in the reference image. "
        "Remove any background and the person. Present it as a clean front-facing flat-lay "
        "product photograph on a neutral studio background. No mannequin. No hanger."
    )
    try:
        result = await generate_image(
            prompt=prompt,
            model=model,
            category="top",
            reference_images=[image_bytes],
            negative_prompt="person, mannequin, hanger, multiple garments, watermark, text",
            watermark=False,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 生图失败: {exc}")
        return False

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_model = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in model)
    output_path = OUTPUT_DIR / f"_p0_test_{safe_model}.png"
    output_path.write_bytes(result)
    print(f"  ✅ 生图成功，{len(result)} bytes -> {output_path}")
    print("     ⚠️ 请人工检查该图是否带水印（文档称 watermark 固定 true）")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vision-only", action="store_true", help="只测识别")
    parser.add_argument("--skip-vision", action="store_true", help="跳过识别")
    parser.add_argument("--model", default="qwen-image-3.0-pro", help="生图模型")
    args = parser.parse_args()

    image_bytes = _pick_demo_image()
    print(f"使用 demo 图片: {len(image_bytes)} bytes")

    results = {}

    if not args.skip_vision:
        results["vision_base64"] = await test_vision(image_bytes)

    if not args.vision_only:
        results["image_base64"] = await test_image_base64(image_bytes, args.model)

    print("\n===== P0 结果汇总 =====")
    for key, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {key}")

    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))