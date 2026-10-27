import json
import time
from typing import Dict, Any
import requests

class FlowRPCClient:
    BASE_URL = "https://flow.google.com/_/AiSandboxAngularFrontend/data"
    
    MODEL_MAPPINGS = {
        "nano_banana_2_1": "BELUGA",
        "nano_banana_pro": "GEM_PIX_2",
        "nano_banana_2_lite": "HARBOR_SEAL",
        "upsample_2k": "GEM_PIX_2_UPSAMPLE_2K",
        "upsample_4k": "GEM_PIX_2_UPSAMPLE_4K",
    }
    
    ASPECT_RATIO_MAPPINGS = {
        "16:9": "LANDSCAPE",
        "9:16": "PORTRAIT",
        "1:1": "SQUARE",
        "4:3": "LANDSCAPE_4_3",
        "3:4": "PORTRAIT_3_4",
    }
    
    def __init__(self, cookies: Dict[str, str], at_token: str, f_sid: str, bl: str):
        self.cookies = cookies
        self.at_token = at_token
        self.f_sid = f_sid
        self.bl = bl
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "X-Same-Domain": "1",
            "Origin": "https://flow.google.com",
            "Referer": "https://flow.google.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin"
        })
        self.session.cookies.update(cookies)

    def generate_image_stream(self, project_id: str, prompt: str, recaptcha_token: str) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/google.internal.labs.aisandbox.proto.flow.agent.v1.FlowCreationAgentService/StreamChat"
        params = {
            "bl": self.bl,
            "f.sid": self.f_sid,
            "hl": "tr",
            "_reqid": str(int(time.time() * 1000) % 10000000),
            "rt": "c"
        }
        inner_data = [
            f"session_{int(time.time())}",
            [[[[prompt]]]],
            [f"projects/{project_id}", None, [recaptcha_token, 1], None, None, 1]
        ]
        payload = {
            "f.req": json.dumps([None, json.dumps(inner_data)]),
            "at": self.at_token
        }
        response = self.session.post(url, params=params, data=payload)
        response.raise_for_status()
        raw_text = response.text
        if raw_text.startswith(")]}'"):
            raw_text = raw_text[4:].strip()
        return {"raw_response": raw_text}
