import requests
import os

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

def search_place(query):
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": 1,
        "start": 1,
        "sort": "random"
    }

    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"❌ 네이버 API 요청 실패: {response.status_code}")
        return None

    result = response.json()
    items = result.get("items", [])

    if not items:
        print(f"❗ 검색 결과 없음: '{query}'")
        return None

    first_item = items[0]

    return {
        "title": first_item.get("title"),
        "category": first_item.get("category"),
        "address": first_item.get("address"),
        "mapx": first_item.get("mapx"),
        "mapy": first_item.get("mapy"),
        "link": first_item.get("link"),
    }

