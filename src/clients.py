# clients.py
"""
Multi-model API client wrapper using AIGCBAR's unified OpenAI-compatible interface.

The full model name is used directly.
"""
import base64
import io
from pathlib import Path
from typing import Optional, Tuple

import httpx
from openai import OpenAI
from PIL import Image


def compress_image_to_base64(
    image_path: str,
    max_side: int = 1600,
    jpeg_quality: int = 85
) -> Tuple[str, str]:
    """
    压缩图片并转为 base64
    返回: (mime_type, base64_string)
    """
    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError("图片文件不存在: %s" % image_path)

    with Image.open(img_path) as img:
        if img.mode not in ("RGB",):
            img = img.convert("RGB")

        w, h = img.size
        long_side = max(w, h)
        if long_side > max_side:
            scale = float(max_side) / float(long_side)
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
        image_bytes = buffer.getvalue()

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return "image/jpeg", image_b64


class ModelClient:

    def __init__(self, model_name: str, api_key: str, base_url: str):
        if not api_key or api_key.strip() == "":
            raise ValueError("api_key 不能为空")

        if not base_url or base_url.strip() == "":
            raise ValueError("base_url 不能为空")

        self.model_name = model_name
        self.api_key = api_key.strip()
        self.base_url = base_url.strip().rstrip("/")

        timeout = httpx.Timeout(
            timeout=240.0,
            connect=60.0,
            read=240.0,
            write=240.0
        )

        http_client = httpx.Client(
            timeout=timeout,
            follow_redirects=True
        )

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            max_retries=2,
            http_client=http_client
        )

    def query(self, image_path: str, prompt: str, max_tokens: int = 1024) -> str:
        if not Path(image_path).exists():
            raise FileNotFoundError("图片文件不存在: %s" % image_path)

        mime_type, image_b64 = compress_image_to_base64(
            image_path=image_path,
            max_side=1600,
            jpeg_quality=85
        )

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:%s;base64,%s" % (mime_type, image_b64)
                            }
                        }
                    ]
                }
            ],
            max_tokens=max_tokens,
            temperature=0.0
        )

        return self._extract_text(response)

    @staticmethod
    def _extract_text(response) -> str:
        content = response.choices[0].message.content

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    texts.append(item.get("text", ""))
                else:
                    texts.append(str(item))
            return "\n".join([t for t in texts if t]).strip()

        return str(content)


def get_model_client(model_name: str, api_key: str, base_url: Optional[str] = None) -> ModelClient:
    if not base_url:
        raise ValueError("必须传入 base_url")
    return ModelClient(model_name, api_key, base_url)
