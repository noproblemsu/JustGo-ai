# backend/gpt_places_recommender.py
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Tuple, Optional

# 1) .env를 가장 먼저 로드 (루트의 .env)
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv(dotenv_path=(Path(__file__).resolve().parent.parent / ".env"))
except Exception:
    pass

# 2) OpenAI 클라이언트 (키 없으면 None로)
try:
    from openai import OpenAI  # pip install openai>=1.30
except Exception:
    OpenAI = None  # type: ignore

API_KEY = os.getenv("OPENAI_API_KEY")
client = None
if OpenAI and API_KEY:
    try:
        client = OpenAI(api_key=API_KEY)
    except Exception:
        client = None


def ask_gpt(prompt: str, destination: Optional[str] = None) -> str:
    """
    간단한 장소 추천을 위해 GPT 호출.
    - 키/클라이언트가 없으면 안전 폴백 문자열을 반환하여 서버가 죽지 않도록 함.
    """
    if client is None:
        # 폴백: 목적지/프롬프트를 섞어 대충 형태만 유지
        city = destination or "여행지"
        return (
            f"[관광지 추천]\n"
            f"1. {city} 랜드마크 A - 전망이 좋은 장소\n"
            f"2. {city} 박물관 B - 대표 전시 관람\n"
            f"3. {city} 공원 C - 산책 코스\n\n"
            f"[맛집 추천]\n"
            f"1. {city} 맛집 D - 현지식\n"
            f"2. {city} 카페 E - 디저트\n"
            f"3. {city} 식당 F - 가성비"
        )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 한국어로 답하는 여행지/맛집 추천 전문가입니다."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return (resp.choices[0].message.content or "").strip()


def extract_places(response: str) -> Tuple[List[str], List[str]]:
    """
    GPT 응답에서 '관광지'와 '맛집' 라인만 대충 추출.
    """
    sightseeing: List[str] = []
    restaurants: List[str] = []

    lines = (response or "").splitlines()
    current = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if "관광지" in s:
            current = "sight"
            continue
        if "맛집" in s:
            current = "rest"
            continue

        if s[0:1].isdigit():  # '1.' 로 시작하는 목록 라인
            if current == "sight":
                sightseeing.append(s)
            elif current == "rest":
                restaurants.append(s)

    return sightseeing, restaurants
