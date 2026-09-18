import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).resolve().with_name(".env"))

URL = "https://maas-api.cn-huabei-1.xf-yun.com/v2/chat/completions"


def get_api_key():
    token = os.getenv("XFYUN_LLM_API_KEY")
    if not token:
        raise RuntimeError("未配置大模型 API Key，请在 .env 中设置 XFYUN_LLM_API_KEY")
    return token if token.startswith("Bearer ") else f"Bearer {token}"

def get_answer(content):
    headers = {
        'Authorization': get_api_key(),
        'content-type': "application/json"
    }
    body = {
        "model": "spark-x2.5-4b",
        "user": "user_id",
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ]
    }

    response = requests.post(url=URL,json= body,headers= headers)
    response = response.json()
    response_content = response["choices"][0]["message"]["content"]
    return response_content

if __name__ =='__main__':

    response = get_answer("你是谁？")
    print(response)


