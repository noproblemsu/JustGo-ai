# backend/routers/modify.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from services.places import google_nearby_restaurants, rank_places

router = APIRouter(prefix="/api/modify", tags=["modify"])

class ModifyReq(BaseModel):
    date: str                          # "2025-08-12"
    mealtime: str                      # "점심", "저녁"
    cuisine: Optional[str] = None      # "일식", "한식" 등
    prev_lat: float = Field(..., description="직전 일정 위도")
    prev_lng: float = Field(..., description="직전 일정 경도")
    radius_m: int = 2500

class PlaceOut(BaseModel):
    name: str
    rating: float
    reviews: int
    distance_km: float
    address: str
    naver_url: str

class ModifyRes(BaseModel):
    candidates: List[PlaceOut]
    top_pick: Optional[PlaceOut] = None
    message: str

@router.post("/restaurant", response_model=ModifyRes)
def recommend_restaurant(req: ModifyReq):
    try:
        raw = google_nearby_restaurants(
            lat=req.prev_lat,
            lng=req.prev_lng,
            radius_m=req.radius_m,
            cuisine=req.cuisine,
            keyword=f"{req.mealtime} 식사",
        )
        ranked = rank_places(raw, req.prev_lat, req.prev_lng, max_distance_km=5.0)
        if not ranked:
            return ModifyRes(candidates=[], top_pick=None,
                             message="주변에서 조건에 맞는 후보가 없어요. 반경을 넓혀볼까요?")
        top5 = ranked[:5]
        top = top5[0]
        pack = lambda x: PlaceOut(
            name=x["name"], rating=x["rating"], reviews=x["reviews"],
            distance_km=x["distance_km"], address=x["address"], naver_url=x["naver_url"]
        )
        return ModifyRes(
            candidates=[pack(x) for x in top5],
            top_pick=pack(top),
            message=f"{req.mealtime} 추천 Top1: '{top['name']}' (★{top['rating']} / 후기 {top['reviews']}개 / {top['distance_km']}km)"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
