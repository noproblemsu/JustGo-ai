# backend/gpt_client.py
from __future__ import annotations

import os
from pathlib import Path
from typing import List

# 1) .env 먼저 로드
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv(dotenv_path=(Path(__file__).resolve().parent.parent / ".env"))
except Exception:
    pass

# 2) OpenAI 클라이언트 준비 (키 없으면 None)
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


# ===== 내부 유틸 =====
def _join_list(a):
    if isinstance(a, (list, tuple)):
        return ", ".join(map(str, a))
    return str(a)


def _mock_schedules(location: str, days: int, budget: int, count: int) -> str:
    """키 없을 때도 서버가 죽지 않도록 매우 간단한 목업 일정 3개를 생성."""
    blocks = []
    for i in range(1, count + 1):
        lines = [f"일정추천 {i}: {location} {days}일 샘플"]
        for d in range(1, days + 1):
            lines.append(f"2025-08-{12 + d:02d} (Day{d})")
            lines.append(f"  09:00 ~ 12:00 {location} 주요명소 A")
            lines.append(f"  12:00 ~ 13:30 점심 — 약 12,000원")
            lines.append(f"  14:00 ~ 18:00 {location} 체험/산책")
            lines.append(f"  19:00 ~ 20:30 저녁 — 약 15,000원")
        lines.append(f"총 예상 비용은 약 {min(max(budget, 0), budget):,}원")
        blocks.append("\n".join(lines))
    return "\n\n---\n".join(blocks)


# ===== 프롬프트 빌더 =====
def build_prompt(
    location: str,
    days: int,
    budget: int,
    companions: List[str],
    style: str,
    selected_places: List[str],
    travel_date: str,
    count: int = 3,
) -> str:
    return (
        "다음 조건으로 한국어 여행 일정을 만들어 주세요.\n"
        "- 출력 형식: 각 블록은 '일정추천 N: <제목>' 한 줄로 시작하고, 그 아래에 일자별 타임라인을 작성.\n"
        "- 날짜는 각 일자마다 반드시 포함(예: 2025-08-13 (Wed)).\n"
        "- 실제 존재하는 상호명을 사용하고, 아침/점심/저녁을 구분, 각 식사에 대략 비용 '약 xx,xxx원' 기입.\n"
        "- 마지막 줄에 '총 예상 비용은 약 xx,xxx원'을 딱 1번만 표기.\n"
        f"- 일정 갯수: {count}개\n"
        f"- 여행지: {location}\n"
        f"- 여행 일자 수: {days}일, 시작일 {travel_date}\n"
        f"- 동행자: {_join_list(companions) or '없음'}\n"
        f"- 스타일: {style}\n"
        f"- 선호 장소: {_join_list(selected_places) or '없음'}\n"
        f"- 예산: {budget:,}원\n"
    )


# ===== 공개 함수 =====
def generate_schedule_gpt(
    location: str,
    days: int,
    style: str,
    companions: List[str],
    budget: int,
    selected_places: List[str],
    travel_date: str,
    count: int = 3,
) -> str:
    """
    일정 N개를 한 번에 생성해 하나의 텍스트로 반환.
    - 키가 없거나 OpenAI 사용 불가 시: 목업 일정 반환(서버가 죽지 않도록)
    """
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

    if client is None:
        # 안전 폴백
        return _mock_schedules(location, days, budget, count)

    # 모델은 경량 편집용으로 gpt-4o-mini 권장
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "너는 여행 일정 전문가야."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
    )
    return (resp.choices[0].message.content or "").strip()
