import os
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models import (
    GenerateImageRequest,
    GenerateImageResponse,
    GeneratedImage,
    ImageModel,
    AspectRatio,
    OutputFormat,
    ModelInfo,
    AspectRatioInfo
)
from app.flow_browser import FlowBrowserSession

@asynccontextmanager
async def lifespan(app: FastAPI):
    session = FlowBrowserSession.get_instance()
    asyncio.create_task(session.warmup())
    yield
    await session.close()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
@app.head("/")
async def root():
    return {"status": "ok", "app": settings.APP_NAME}

@app.get("/health")
async def health_check():
    session = FlowBrowserSession.get_instance()
    session_file = settings.SESSION_STORAGE_PATH
    if not os.path.isabs(session_file):
        session_file = os.path.abspath(session_file)
    session_exists = os.path.exists(session_file) and os.path.getsize(session_file) > 0
    session_env = bool(os.getenv("SESSION_JSON") or os.getenv("SESSION_BASE64"))
    
    current_url = None
    if session.page and not session.page.is_closed():
        try:
            current_url = session.page.url
        except Exception:
            pass

    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "browser_ready": session._is_initialized,
        "session_configured": session_exists or session_env,
        "session_file_exists": session_exists,
        "session_env_present": session_env,
        "current_url": current_url,
        "last_error": session.last_error
    }

@app.get("/api/v1/init")
@app.post("/api/v1/init")
async def initialize_browser():
    session = FlowBrowserSession.get_instance()
    try:
        await session.initialize()
        title = await session.page.title() if session.page else ""
        return {
            "success": True,
            "browser_ready": session._is_initialized,
            "current_url": session.page.url if session.page else None,
            "page_title": title
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/debug/screenshot")
async def debug_screenshot():
    session = FlowBrowserSession.get_instance()
    if not session.page or session.page.is_closed():
        raise HTTPException(status_code=400, detail="Tarayici acik degil. Once /api/v1/init cagirin.")
    try:
        screenshot_bytes = await session.page.screenshot(full_page=False)
        return Response(content=screenshot_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/models", response_model=List[ModelInfo])
async def list_models():
    return [
        ModelInfo(id=ImageModel.NANO_BANANA_2_1.value, name="Nano Banana 2.1", internal_name="BELUGA"),
        ModelInfo(id=ImageModel.NANO_BANANA_PRO.value, name="Nano Banana Pro", internal_name="GEM_PIX_2"),
        ModelInfo(id=ImageModel.NANO_BANANA_2_LITE.value, name="Nano Banana 2 Lite", internal_name="HARBOR_SEAL"),
        ModelInfo(id=ImageModel.UPSAMPLE_2K.value, name="2K Upscaler", internal_name="GEM_PIX_2_UPSAMPLE_2K"),
        ModelInfo(id=ImageModel.UPSAMPLE_4K.value, name="4K Upscaler", internal_name="GEM_PIX_2_UPSAMPLE_4K"),
    ]

@app.get("/api/v1/aspect-ratios", response_model=List[AspectRatioInfo])
async def list_aspect_ratios():
    return [
        AspectRatioInfo(ratio="16:9", name="Landscape"),
        AspectRatioInfo(ratio="9:16", name="Portrait"),
        AspectRatioInfo(ratio="1:1", name="Square"),
        AspectRatioInfo(ratio="4:3", name="Landscape 4:3"),
        AspectRatioInfo(ratio="3:4", name="Portrait 3:4")
    ]

@app.post("/api/v1/generate", response_model=GenerateImageResponse)
async def generate_image(request: GenerateImageRequest):
    session = FlowBrowserSession.get_instance()
    try:
        result = await session.generate_image(
            prompt=request.prompt,
            model=request.model,
            aspect_ratio=request.aspect_ratio,
            seed=request.seed,
            image_base64=request.image_base64,
            image_url=request.image_url
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if request.output_format == OutputFormat.BINARY:
        return Response(content=result["image_bytes"], media_type="image/png")

    base64_data = result["image_base64"] if request.output_format == OutputFormat.BASE64 else None

    return GenerateImageResponse(
        success=True,
        prompt=request.prompt,
        model=request.model.value,
        aspect_ratio=request.aspect_ratio.value,
        image=GeneratedImage(
            url=result["image_url"],
            base64=base64_data,
            width=result.get("width"),
            height=result.get("height")
        ),
        execution_time_seconds=result["execution_time_seconds"]
    )
