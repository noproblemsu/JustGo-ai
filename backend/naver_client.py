import os
import requests
from dotenv import load_dotenv

load_dotenv()

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

def search_blog(query, display=3):
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": display,
        "sort": "sim"  # 관련도순
    }

    res = requests.get(url, headers=headers, params=params)
    if res.status_code == 200:
        items = res.json().get("items", [])
        return [item["link"] for item in items]
    else:
        print(f"네이버 API 오류: {res.status_code}")
        return []

