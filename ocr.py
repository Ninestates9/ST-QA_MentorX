import base64
import mimetypes
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"))

URL = "https://maas-api.cn-huabei-1.xf-yun.com/v2/chat/completions"
MODEL = "xoppaddleocrv16"
DEFAULT_PROMPT = "请识别图片中的文字，只输出识别到的文字内容。"


def getHeader(api_key=None):
    token = api_key or os.getenv("XFYUN_OCR_API_KEY")
    if not token:
        raise RuntimeError("未配置讯飞 OCR API Key，请设置环境变量 XFYUN_OCR_API_KEY")
    authorization = token if token.startswith("Bearer ") else f"Bearer {token}"
    return {
        "Content-Type": "application/json",
        "Authorization": authorization,
    }


def getBody(filepath, prompt=DEFAULT_PROMPT):
    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/png"
    with open(filepath, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
    return {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{encoded_image}"
                        },
                    },
                ],
            }
        ],
        "stream": False,
        "max_tokens": 8192,
    }


def _extract_content(payload):
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"讯飞 OCR 返回数据格式异常：{payload}") from exc
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        texts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "".join(texts).strip()
    raise RuntimeError(f"讯飞 OCR 返回内容格式异常：{content}")


def ocr(
    language="cn|en",
    location="false",
    picFilePath="./ocr_img/ocr.jpg",
    prompt=DEFAULT_PROMPT,
    api_key=None,
    timeout=60,
):
    _ = language, location
    response = requests.post(
        URL,
        headers=getHeader(api_key),
        json=getBody(picFilePath, prompt),
        timeout=timeout,
    )
    response.raise_for_status()
    return _extract_content(response.json())


if __name__ == "__main__":
    print(ocr())
