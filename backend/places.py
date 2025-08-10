# backend/services/places.py
import math
import os
import requests
from typing import List, Dict, Optional
from urllib.parse import quote

GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    to_rad = math.radians
    dlat = to_rad(lat2 - lat1)
    dlon = to_rad(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(to_rad(lat1))*math.cos(to_rad(lat2))*math.sin(dlon/2)**2
    return 2 * R * math.asin(min(1, math.sqrt(a)))

def naver_search_url(name: str) -> str:
    # 순수 장소명으로 네이버 지도 검색
    return f"https://map.naver.com/v5/search/{quote(name)}"

def google_nearby_restaurants(
    lat: float,
    lng: float,
    radius_m: int = 2500,
    keyword: Optional[str] = None,
    cuisine: Optional[str] = None,
) -> List[Dict]:
    """
    Google Places Nearby Search: 평점/후기수/좌표 포함
    """
    if not GOOGLE_KEY:
        raise RuntimeError("GOOGLE_MAPS_API_KEY not set in environment")

    params = {
        "key": GOOGLE_KEY,
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "type": "restaurant",
        "language": "ko",
    }
    if keyword:
        params["keyword"] = keyword
    if cuisine:
        params["keyword"] = (params.get("keyword", "") + f" {cuisine}").strip()

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    items: List[Dict] = []
    for p in data.get("results", []):
        name = p.get("name")
        rating = float(p.get("rating", 0) or 0)
        reviews = int(p.get("user_ratings_total", 0) or 0)
        loc = (p.get("geometry") or {}).get("location") or {}
        plat, plng = loc.get("lat"), loc.get("lng")
        if not (name and plat and plng):
            continue
        items.append({
            "name": name,
            "rating": rating,
            "reviews": reviews,
            "lat": float(plat),
            "lng": float(plng),
            "address": p.get("vicinity", ""),
            "naver_url": naver_search_url(name),
            "google_place_id": p.get("place_id"),
        })
    return items

def rank_places(
    items: List[Dict],
    origin_lat: float,
    origin_lng: float,
    max_distance_km: float = 5.0,
) -> List[Dict]:
    """
    점수 = 평점(60%) + 후기수로그정규(35%) – 거리패널티(25%)
    """
    if not items:
        return []

    for it in items:
        it["distance_km"] = round(haversine_km(origin_lat, origin_lng, it["lat"], it["lng"]), 2)

    items = [x for x in items if x["distance_km"] <= max_distance_km]
    if not items:
        return []

    max_reviews = max(x["reviews"] for x in items) or 1

    ranked = []
    for it in items:
        rating = it["rating"]                    # 0~5
        rev_norm = math.log1p(it["reviews"]) / math.log1p(max_reviews)  # 0~1
        dist_penalty = it["distance_km"] / max_distance_km              # 0~1
        score = (rating/5)*0.6 + rev_norm*0.35 - dist_penalty*0.25
        it["score"] = round(score, 4)
        ranked.append(it)

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked
