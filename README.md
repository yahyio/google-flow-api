# Google Flow Image & Video Generation API

API service for programmatic image and video generation via Google Flow models (`nano_banana_2_1`, `nano_banana_pro`, `nano_banana_2_lite`, `upsample_2k`, `upsample_4k`, `omni_1_1_flash`, `veo_3_1_lite`, `veo_3_1_fast`, `veo_3_1_quality`).

---

## Base URL
```
http://<host>:8000
```

Interactive documentation:
* Swagger UI: `http://<host>:8000/docs`
* Redoc: `http://<host>:8000/redoc`

---

## Endpoints

### 1. Generate Image
`POST /api/v1/generate`

#### Headers
```
Content-Type: application/json
```

#### Request Body Schema
```json
{
  "prompt": "string (required)",
  "model": "nano_banana_2_1 | nano_banana_pro | nano_banana_2_lite | upsample_2k | upsample_4k (default: nano_banana_2_1)",
  "aspect_ratio": "16:9 | 9:16 | 1:1 | 4:3 | 3:4 (default: 16:9)",
  "seed": "integer (optional)",
  "image_base64": "string (optional base64 encoded input reference image)",
  "image_url": "string (optional URL of input reference image)",
  "output_format": "base64 | url | binary (default: base64)"
}
```

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "prompt": "cinematic neon cyberpunk street at night, 8k render",
  "model": "nano_banana_pro",
  "aspect_ratio": "16:9",
  "image": {
    "url": "https://flow.google.com/asb/ANqvLO...=s1600-rw",
    "base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "width": 1376,
    "height": 768
  },
  "execution_time_seconds": 8.42
}
```

---

### 2. Generate Video (Omni 1.1 Flash & Veo 3.1)
`POST /api/v1/generate-video`

Supports both Text-to-Video and Image-to-Video (when `image_base64` or `image_url` is provided).

#### Headers
```
Content-Type: application/json
```

#### Request Body Schema
```json
{
  "prompt": "string (required)",
  "model": "omni_1_1_flash | veo_3_1_lite | veo_3_1_fast | veo_3_1_quality (default: omni_1_1_flash)",
  "aspect_ratio": "16:9 | 9:16 | 1:1 | 4:3 | 3:4 (default: 16:9)",
  "seed": "integer (optional)",
  "image_base64": "string (optional base64 encoded starting frame for image-to-video)",
  "image_url": "string (optional URL of starting frame for image-to-video)",
  "output_format": "base64 | url | binary (default: base64)"
}
```

#### Examples

##### A. Text-to-Video (Omni 1.1 Flash)
```json
{
  "prompt": "slow cinematic drone shot over a misty pine forest at sunrise",
  "model": "omni_1_1_flash",
  "aspect_ratio": "16:9",
  "output_format": "base64"
}
```

##### B. Image-to-Video (Animate Reference Image with Veo 3.1)
```json
{
  "prompt": "the character waves hand and smiles at the camera, subtle camera zoom in",
  "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
  "model": "veo_3_1_fast",
  "aspect_ratio": "16:9",
  "output_format": "base64"
}
```

#### Success Response (`200 OK`)
```json
{
  "success": true,
  "prompt": "slow cinematic drone shot over a misty pine forest at sunrise",
  "model": "omni_1_1_flash",
  "aspect_ratio": "16:9",
  "video": {
    "url": "https://flow.google.com/...",
    "base64": "AAAAIGZ0eXBtcDQyAAAAAGlzb21tcDQy..."
  },
  "execution_time_seconds": 54.18
}
```

##### Direct Binary Stream (`output_format: "binary"`)
Returns `video/mp4` raw binary stream directly.

---

### 3. List Models
`GET /api/v1/models`

#### Response
```json
[
  {"id": "nano_banana_2_1", "name": "Nano Banana 2.1", "internal_name": "BELUGA"},
  {"id": "nano_banana_pro", "name": "Nano Banana Pro", "internal_name": "GEM_PIX_2"},
  {"id": "nano_banana_2_lite", "name": "Nano Banana 2 Lite", "internal_name": "HARBOR_SEAL"},
  {"id": "upsample_2k", "name": "2K Upscaler", "internal_name": "GEM_PIX_2_UPSAMPLE_2K"},
  {"id": "upsample_4k", "name": "4K Upscaler", "internal_name": "GEM_PIX_2_UPSAMPLE_4K"},
  {"id": "omni_1_1_flash", "name": "Omni 1.1 Flash", "internal_name": "OMNI_1_1_FLASH"},
  {"id": "veo_3_1_lite", "name": "Veo 3.1 - Lite", "internal_name": "VEO_3_1_LITE"},
  {"id": "veo_3_1_fast", "name": "Veo 3.1 - Fast", "internal_name": "VEO_3_1_FAST"},
  {"id": "veo_3_1_quality", "name": "Veo 3.1 - Quality", "internal_name": "VEO_3_1_QUALITY"}
]
```

---

### 4. List Aspect Ratios
`GET /api/v1/aspect-ratios`

#### Response
```json
[
  {"ratio": "16:9", "name": "Landscape"},
  {"ratio": "9:16", "name": "Portrait"},
  {"ratio": "1:1", "name": "Square"},
  {"ratio": "4:3", "name": "Landscape 4:3"},
  {"ratio": "3:4", "name": "Portrait 3:4"}
]
```

---

### 5. Health Check & Diagnostics
* `GET /health` — Check session and browser status.
* `POST /api/v1/init` — Manually initialize browser session.
* `GET /api/v1/debug/screenshot` — View current browser screen as `image/png`.

---

## Python Usage Example (Video)
```python
import base64
import requests

response = requests.post(
    "http://localhost:8000/api/v1/generate-video",
    json={
        "prompt": "camera slowly pans across a neon-lit Tokyo alley in the rain",
        "model": "veo_2",
        "aspect_ratio": "16:9",
        "output_format": "base64"
    },
    timeout=300
)
data = response.json()
video_bytes = base64.b64decode(data["video"]["base64"])
with open("output.mp4", "wb") as f:
    f.write(video_bytes)
```
