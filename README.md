# Google Flow Image Generation API

API service for programmatic image generation via Google Flow models (`nano_banana_2_1`, `nano_banana_pro`, `nano_banana_2_lite`, `upsample_2k`, `upsample_4k`).

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

#### Examples

##### A. Text-to-Image (JSON Response)
```json
{
  "prompt": "cinematic neon cyberpunk street at night, 8k render",
  "model": "nano_banana_pro",
  "aspect_ratio": "16:9",
  "output_format": "base64"
}
```

##### B. Image-to-Image (Prompt with Reference Image)
```json
{
  "prompt": "recreate this character in anime style, vibrant colors",
  "image_url": "https://example.com/character.png",
  "model": "nano_banana_2_1",
  "aspect_ratio": "1:1",
  "output_format": "base64"
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

##### Direct Binary Stream (`output_format: "binary"`)
Returns `image/png` raw binary data stream directly.

---

### 2. List Models
`GET /api/v1/models`

#### Response
```json
[
  {"id": "nano_banana_2_1", "name": "Nano Banana 2.1", "internal_name": "BELUGA"},
  {"id": "nano_banana_pro", "name": "Nano Banana Pro", "internal_name": "GEM_PIX_2"},
  {"id": "nano_banana_2_lite", "name": "Nano Banana 2 Lite", "internal_name": "HARBOR_SEAL"},
  {"id": "upsample_2k", "name": "2K Upscaler", "internal_name": "GEM_PIX_2_UPSAMPLE_2K"},
  {"id": "upsample_4k", "name": "4K Upscaler", "internal_name": "GEM_PIX_2_UPSAMPLE_4K"}
]
```

---

### 3. List Aspect Ratios
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

### 4. Health Check
`GET /health`

#### Response
```json
{
  "status": "healthy",
  "app": "Google Flow API",
  "browser_ready": true
}
```

---

## Code Examples

### cURL
```bash
curl -X POST "http://localhost:8000/api/v1/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "astronaut riding a horse on mars, photorealistic",
    "model": "nano_banana_2_1",
    "aspect_ratio": "16:9",
    "output_format": "base64"
  }'
```

### Python
```python
import base64
import requests

response = requests.post(
    "http://localhost:8000/api/v1/generate",
    json={
        "prompt": "astronaut riding a horse on mars, photorealistic",
        "model": "nano_banana_2_1",
        "aspect_ratio": "16:9",
        "output_format": "base64"
    },
    timeout=120
)
data = response.json()
image_bytes = base64.b64decode(data["image"]["base64"])
with open("result.png", "wb") as f:
    f.write(image_bytes)
```

### JavaScript / Node.js
```javascript
const response = await fetch("http://localhost:8000/api/v1/generate", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    prompt: "astronaut riding a horse on mars, photorealistic",
    model: "nano_banana_2_1",
    aspect_ratio: "16:9",
    output_format: "base64"
  })
});

const data = await response.json();
console.log("Image width:", data.image.width, "height:", data.image.height);
```

---

## Coolify Deployment

1. Connect this GitHub repository to Coolify.
2. Select **Docker Compose** or **Dockerfile**.
3. Set Port to `8000`.
4. Mount persistent storage for authentication:
   * Host path: `/data/coolify/google-flow-auth` (or any persistent directory)
   * Container path: `/app/auth`
5. Place your exported `session.json` into `/app/auth/session.json`.
6. Deploy.
