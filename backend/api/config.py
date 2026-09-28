"""
配置管理 API
"""
import asyncio
import sys
from fastapi import APIRouter, HTTPException
from domain.config import LLMConfigUpdate, AvailableModel, ModelListResponse
from storage.config_store import load_config, update_config, get_masked_config
from services.openai_compatible import fetch_available_models
from services.segment import is_local_rembg_available

router = APIRouter()


def get_config_response() -> dict:
    """获取配置响应，并附带运行时依赖状态。"""
    config = get_masked_config()
    config["local_rembg_installed"] = is_local_rembg_available()
    return config


@router.get("/config")
async def get_config():
    """获取当前 LLM 配置（API Key 脱敏）"""
    return get_config_response()


@router.post("/config")
async def set_config(config_update: LLMConfigUpdate):
    """更新 LLM 配置"""
    try:
        config = update_config(
            api_base=config_update.api_base,
            api_key=config_update.api_key,
            model=config_update.model,
            removebg_api_key=config_update.removebg_api_key,
            bg_removal_method=config_update.bg_removal_method,
            tryon_provider=config_update.tryon_provider,
            tryon_api_url=config_update.tryon_api_url,
            tryon_api_key=config_update.tryon_api_key,
            tryon_model=config_update.tryon_model,
            weather_location=config_update.weather_location,
            zodiac_sign=config_update.zodiac_sign,
            recommendation_mode_weights=config_update.recommendation_mode_weights,
            experimental_garment_pipeline=config_update.experimental_garment_pipeline,
            vision_model=config_update.vision_model,
            image_model=config_update.image_model,
            image_api_base=config_update.image_api_base,
            image_api_key=config_update.image_api_key,
            image_reference_transport=config_update.image_reference_transport,
        )
        return {
            "success": True,
            "message": "配置已更新",
            "config": get_config_response()
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/install-rembg")
async def install_rembg_dependencies():
    """一键安装本地背景移除依赖 rembg + onnxruntime。"""
    if is_local_rembg_available():
        return {
            "success": True,
            "message": "rembg 已安装，可使用本地模式",
            "local_rembg_installed": True,
            "output": "",
        }

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pip",
        "install",
        "rembg",
        "onnxruntime",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    output = ((stdout or b"") + (stderr or b"")).decode("utf-8", errors="ignore")
    tail_output = output[-4000:] if output else ""

    local_rembg_installed = is_local_rembg_available()
    if process.returncode == 0 and local_rembg_installed:
        return {
            "success": True,
            "message": "安装成功，可使用本地 rembg",
            "local_rembg_installed": True,
            "output": tail_output,
        }

    return {
        "success": False,
        "message": "安装失败，请稍后重试或使用 remove.bg API",
        "local_rembg_installed": local_rembg_installed,
        "output": tail_output,
    }


@router.get("/models", response_model=ModelListResponse)
async def list_models():
    """获取可用模型列表"""
    try:
        models = await fetch_available_models()
        return ModelListResponse(
            models=[AvailableModel(id=m["id"], name=m["name"]) for m in models]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-connection")
async def test_connection():
    """测试 API 连接"""
    config = load_config()

    if not config.api_key:
        return {
            "success": False,
            "message": "请先配置 API Key"
        }

    try:
        models = await fetch_available_models()
        if models:
            return {
                "success": True,
                "message": f"连接成功，发现 {len(models)} 个可用模型",
                "model_count": len(models)
            }
        else:
            return {
                "success": False,
                "message": "连接成功但未获取到模型列表，请检查 API Base URL"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}"
        }
