import sys
import asyncio
import time
import base64

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.flow_browser import FlowBrowserSession
from app.models import ImageModel, AspectRatio

async def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "man walking towards camera, cinematic lighting, 8k"
    model = ImageModel.NANO_BANANA_2_1
    aspect_ratio = AspectRatio.RATIO_16_9
    image_url = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("http") else None

    session = FlowBrowserSession.get_instance()
    try:
        result = await session.generate_image(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            image_url=image_url
        )

        filename = f"flow_image_{int(time.time())}.png"
        image_bytes = result.get("image_bytes")
        if not image_bytes and result.get("image_base64"):
            image_bytes = base64.b64decode(result["image_base64"])

        if image_bytes:
            with open(filename, "wb") as f:
                f.write(image_bytes)
            print(f"Saved: {filename} ({result.get('width')}x{result.get('height')})")
        else:
            print("Failed to save image")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await session.close()

if __name__ == "__main__":
    asyncio.run(main())
