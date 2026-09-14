import base64
import hashlib
import time
import requests
URL = "http://webapi.xfyun.cn/v1/service/v1/ocr/handwriting"

APPID = "7a093b54"

API_KEY = "a4278031dd36653720b858bf18e8598b"

def getHeader(language, location):
    curTime = str(int(time.time()))
    param = "{\"language\":\""+language+"\",\"location\":\""+location+"\"}"
    paramBase64 = base64.b64encode(param.encode('utf-8'))

    m2 = hashlib.md5()
    str1 = API_KEY + curTime + str(paramBase64, 'utf-8')
    m2.update(str1.encode('utf-8'))
    checkSum = m2.hexdigest()

    header = {
        'X-CurTime': curTime,
        'X-Param': paramBase64,
        'X-Appid': APPID,
        'X-CheckSum': checkSum,
        'Content-Type': 'application/x-www-form-urlencoded; charset=utf-8',
    }
    return header

def getBody(filepath):
    with open(filepath, 'rb') as f:
        imgfile = f.read()
    data = {'image': str(base64.b64encode(imgfile), 'utf-8')}
    return data

def ocr(language="cn|en", location="false", picFilePath="./ocr_img/ocr.jpg"):

    respones = requests.post(URL, headers=getHeader(language, location), data=getBody(picFilePath)).json()
    all_contents = []
    for block in respones['data']['block']:
        if block['type'] == 'text':
            for line in block['line']:
                for word in line['word']:
                    all_contents.append(word['content'])

    result_text = ' '.join(all_contents)
    return result_text

if __name__ == "__main__":

    ocr()