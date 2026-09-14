import requests

api_key = "Bearer ZEVihKpmjjSauNNScSLa:IexyAmRjLBUeAbHjrxmV"
url = "https://spark-api-open.xf-yun.com/v2/chat/completions"

def get_answer(content):
    headers = {
        'Authorization':api_key,
        'content-type': "application/json"
    }
    body = {
        "model": "x1",
        "user": "user_id",
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ]
    }

    response = requests.post(url=url,json= body,headers= headers)
    response = response.json()
    response_content = response["choices"][0]["message"]["content"]
    return response_content

if __name__ =='__main__':

    response = get_answer("你是谁？")
    print(response)


