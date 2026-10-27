from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class ImageModel(str, Enum):
    NANO_BANANA_2_1 = "nano_banana_2_1"
    NANO_BANANA_PRO = "nano_banana_pro"
    NANO_BANANA_2_LITE = "nano_banana_2_lite"
    UPSAMPLE_2K = "upsample_2k"
    UPSAMPLE_4K = "upsample_4k"

class AspectRatio(str, Enum):
    RATIO_16_9 = "16:9"
    RATIO_9_16 = "9:16"
    RATIO_1_1 = "1:1"
    RATIO_4_3 = "4:3"
    RATIO_3_4 = "3:4"

class OutputFormat(str, Enum):
    URL = "url"
    BASE64 = "base64"
    BINARY = "binary"

class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., example="cinematic portrait of a warrior, 8k")
    model: ImageModel = Field(default=ImageModel.NANO_BANANA_2_1)
    aspect_ratio: AspectRatio = Field(default=AspectRatio.RATIO_16_9)
    seed: Optional[int] = Field(default=None)
    image_base64: Optional[str] = Field(default=None)
    image_url: Optional[str] = Field(default=None)
    output_format: OutputFormat = Field(default=OutputFormat.BASE64)

class GeneratedImage(BaseModel):
    url: Optional[str] = None
    base64: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

class GenerateImageResponse(BaseModel):
    success: bool
    prompt: str
    model: str
    aspect_ratio: str
    image: GeneratedImage
    execution_time_seconds: float

class ModelInfo(BaseModel):
    id: str
    name: str
    internal_name: str

class AspectRatioInfo(BaseModel):
    ratio: str
    name: str
