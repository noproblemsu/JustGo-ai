# backend/gpt_client.py
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional
from openai import OpenAI

# .env
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=(Path(__file__).resolve().parent.parent / ".env"))
except Exception:
    pass

# 단일 출처 프롬프트
from prompts import build_prompt

def _make_client() -> Optional[OpenAI]:
    try:
        key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_APIKEY")
        if not key:
            return None
        return OpenAI(api_key=key)
    except Exception:
        return None

client: Optional[OpenAI] = _make_client()

SYSTEM_STRICT = """
너는 여행 일정 전문가다.
- 출력은 **텍스트만**. 마크다운/코드블록/불릿 금지.
- 각 일정 제목은 '일정추천 N:' 으로 시작하며, 일정 사이 구분은 한 줄에 '---'만 사용.
- 매일 아침/점심/저녁 3개 활동, 날짜는 'YYYY-MM-DD (요일)' 전부 포함.
- 활동 라인은 'HH:MM ~ HH:MM 장소명 (도로명 주소) (약 xx,xxx원)' 형식, 실제 존재 상호만.
- 총 예상 비용은 각 일정 마지막에 **단 1회**만 표기(±15%).
- **같은 일정 내 장소/식당 중복 금지**, 사용자 선택 장소는 **각각 1회만**.
- **하루 안의 모든 활동은 시간순(오름차순)으로, 서로 겹치지 않게 작성**.
- 권장 슬롯: 08:00~09:30 / 09:30~12:00 / 12:00~13:30 / 14:00~18:00 / 19:00~20:30
"""


def _strip_code_fence(s: str) -> str:
    if not s: return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    if s.startswith("```"): s = s.split("```", 2)[-1]
    if s.endswith("```"): s = s.rsplit("```", 1)[0]
    return s.strip()

def _dedent_triple_dash(s: str) -> str:
    lines = []
    for line in s.splitlines():
        if line.strip("- ").strip() == "" and set(line.strip()) <= {"-"}:
            lines.append("---")
        elif line.strip() == "---":
            lines.append("---")
        else:
            lines.append(line)
    return "\n".join(lines).strip()

def generate_schedule_gpt(
    location: str,
    days: int,
    style: str | List[str],
    companions: List[str] | str,
    budget: int,
    selected_places: List[str],
    travel_date: str,
    count: int = 1,
) -> str:
    if client is None:
        return (
            f"일정추천 1: {location} {days}일 코스\n"
            f"{travel_date} (Day1)\n09:00 ~ 12:00 {location} 주요명소 A (도로명주소 예시)\n"
            "12:00 ~ 13:30 점심 (도로명주소 예시)\n"
            f"14:00 ~ 18:00 {location} 체험/산책 (도로명주소 예시)\n"
            "19:00 ~ 20:30 저녁 (도로명주소 예시)\n"
            "---\n일정추천 2: 샘플\n---\n일정추천 3: 샘플"
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
        temperature=0.2,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_STRICT},
            {"role": "user", "content": prompt},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    return _dedent_triple_dash(_strip_code_fence(text))
