import os
import math
import requests
from typing import List, Dict, Tuple
from urllib.parse import quote

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

# ---------- 공통 유틸 ----------
def _ensure_key():
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET not set")

def naver_map_link(name: str) -> str:
    return f"https://map.naver.com/v5/search/{quote(name)}"

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    to_rad = math.radians
    dlat = to_rad(lat2 - lat1)
    dlon = to_rad(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(to_rad(lat1))*math.cos(to_rad(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(min(1, math.sqrt(a)))

def _tm128_to_wgs84(x: float, y: float) -> Tuple[float, float]:
    """네이버 Local API mapx/mapy(TM128) -> 위경도 근사 변환"""
    origin_lat, origin_lng = 38.0, 127.5
    dx, dy = (x - 307000), (y - 548000)
    lat = origin_lat + (dy / 88000.0)
    lng = origin_lng + (dx / 111000.0)
    return float(lat), float(lng)

# ---------- 지역검색 ----------
def naver_local_search(query: str, display: int = 20) -> List[Dict]:
    _ensure_key()
    url = "https://openapi.naver.com/v1/search/local.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {
        "query": query,
        "display": max(1, min(display, 45)),
        "start": 1,
        "sort": "random"
    }
    r = requests.get(url, headers=headers, params=params, timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"Naver API error: {r.status_code} {r.text}")
    data = r.json()
    items = []
    for it in data.get("items", []):
        name = (it.get("title") or "").replace("<b>", "").replace("</b>", "")
        addr = it.get("roadAddress") or it.get("address") or ""
        try:
            mapx = float(it.get("mapx"))
            mapy = float(it.get("mapy"))
        except Exception:
            continue
        items.append({"name": name, "address": addr, "mapx": mapx, "mapy": mapy})
    return items

def search_place(query: str):
    """단건 조회(좌표 포함) — 일정 첫 장소 좌표 추출에 사용"""
    items = naver_local_search(query, display=1)
    if not items:
        return None
    it = items[0]
    lat, lng = _tm128_to_wgs84(it["mapx"], it["mapy"])
    return {
        "title": it["name"], "address": it["address"],
        "lat": lat, "lng": lng, "naver_url": naver_map_link(it["name"])
    }

# ---------- 거리+키워드 적합도 랭킹 ----------
def search_and_rank_places(
    prev_lat: float, prev_lng: float, keyword: str,
    max_distance_km: float = 5.0, display: int = 30
) -> List[Dict]:
    results = naver_local_search(keyword, display=display)
    ranked = []
    for it in results:
        lat, lng = _tm128_to_wgs84(it["mapx"], it["mapy"])
        dist = round(_haversine_km(prev_lat, prev_lng, lat, lng), 2)
        if dist > max_distance_km:
            continue
        name = it["name"]
        fit = 1.0 if all(k.strip() in name for k in keyword.split()) else 0.0
        score = 1.0/(1.0+dist) + 0.3*fit  # 거리 우선, 이름 적합도 가산
        ranked.append({
            "name": name, "address": it["address"],
            "lat": lat, "lng": lng, "distance_km": dist,
            "score": round(score, 4), "naver_url": naver_map_link(name)
        })
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked
