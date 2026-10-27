import sys
import requests
import json
import base64
import time

def test_generate(
    prompt: str = "man walking towards camera, cinematic lighting, 8k",
    model: str = "nano_banana_2_1",
    aspect_ratio: str = "16:9",
    image_base64: str = None,
    image_url: str = None,
    output_format: str = "base64"
):
    endpoint = "http://localhost:8000/api/v1/generate"
    payload = {
        "prompt": prompt,
        "model": model,
        "aspect_ratio": aspect_ratio,
        "output_format": output_format
    }
    if image_base64:
        payload["image_base64"] = image_base64
    if image_url:
        payload["image_url"] = image_url

    start = time.time()
    if output_format == "binary":
        response = requests.post(endpoint, json=payload, stream=True, timeout=120)
        response.raise_for_status()
        filename = f"output_{int(time.time())}.png"
        with open(filename, "wb") as f:
            f.write(response.content)
        print(f"Saved: {filename} ({len(response.content)} bytes)")
    else:
        response = requests.post(endpoint, json=payload, timeout=120)
        response.raise_for_status()
        data = response.json()
        filename = f"output_{int(time.time())}.png"
        if data.get("image", {}).get("base64"):
            raw_bytes = base64.b64decode(data["image"]["base64"])
            with open(filename, "wb") as f:
                f.write(raw_bytes)
            print(f"Saved: {filename} ({len(raw_bytes)} bytes)")
        print(f"Duration: {data.get('execution_time_seconds')}s")

if __name__ == "__main__":
    prompt_arg = sys.argv[1] if len(sys.argv) > 1 else "man walking towards camera, cinematic lighting, 8k"
    test_generate(prompt=prompt_arg)
