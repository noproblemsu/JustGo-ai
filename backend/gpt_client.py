# backend/gpt_client.py
from __future__ import annotations

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=(Path(__file__).resolve().parent.parent / ".env"))
except Exception:
    pass

from openai import OpenAI
from .prompts import build_prompt
import re

def _make_client() -> OpenAI | None:
    try:
        key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_APIKEY")
        # 환경변수만 있어도 OpenAI()는 생성 가능하지만, 명시 전달해도 OK
        return OpenAI(api_key=key) if key else None
    except Exception:
        return None

client: OpenAI | None = _make_client()

SYSTEM_STRICT = (
    "너는 여행 일정 전문가다. 아래 모든 규칙을 반드시 지켜라. "
    "실제 존재하는 상호명만 쓰고, 괄호 안에 '도로명 주소'를 반드시 포함해라. "
    "날짜(YYYY-MM-DD (요일))는 전부 포함되어야 하며 하루라도 누락되면 전체를 다시 작성해라. "
    "총 예상 비용은 일정 끝에 딱 1번만 작성한다."
)

def _normalize(s: str) -> str:
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    # ```...``` 코드블록 제거
    s = re.sub(r"^```(?:\w+)?\n", "", s)
    s = re.sub(r"\n```$", "", s)
    return s.strip()

def generate_schedule_gpt(
    location: str,
    days: int,
    style: str,
    companions,
    budget: int,
    selected_places,
    travel_date: str,
    count: int = 1,  # 기본 1로 통일
) -> str:
    """
    prompts.build_prompt()로 프롬프트를 만들고, 한 번의 호출로
    '일정추천 1..count'를 생성한다.
    """
    if client is None:
        # 키가 없을 때는 샘플 반환 (가능한 형식 깨끗하게, '...' 제거)
        return (
            f"일정추천 1: {location} {days}일 샘플\n"
            f"{travel_date} (Day1)\n"
            f"09:00 ~ 12:00 {location} 주요명소 A (도로명 주소 미상) (약 0원)\n"
            "12:00 ~ 13:30 점심 (약 12,000원)\n"
            f"14:00 ~ 18:00 {location} 체험/산책 (약 0원)\n"
            "19:00 ~ 20:30 저녁 (약 15,000원)\n"
        )

    prompt = build_prompt(
        location=location,
        days=days,
        budget=budget,
        companions=companions,
        style=style,
        selected_places=selected_places,
        travel_date=travel_date,
        count=count,
    )

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.25,
        max_tokens=3000,
        messages=[
            {"role": "system", "content": SYSTEM_STRICT},
            {"role": "user", "content": prompt},
        ],
    )
    content = resp.choices[0].message.content or ""
    return _normalize(content)

def ask_gpt(prompt: str, destination: str | None = None) -> str:
    if client is None:
        return prompt

    sys = "너는 여행지 추천/요약 전문가다. 사실적이고 간결하게 한국어로 답한다."
    if destination:
        prompt = f"[도시] {destination}\n\n{prompt}"

    out = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.3,
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": prompt},
        ],
    )
    return _normalize(out.choices[0].message.content or "")

def extract_places(text: str):
    sightseeing, restaurants = [], []
    current = None
    for line in (text or "").splitlines():
        if "관광지 추천" in line:
            current = "s"
        elif "맛집 추천" in line:
            current = "r"
        elif line.strip().startswith(tuple("1234567890")):
            if current == "s":
                sightseeing.append(line)
            elif current == "r":
                restaurants.append(line)
    return sightseeing, restaurants
