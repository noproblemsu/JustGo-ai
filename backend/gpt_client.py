# backend/gpt_client.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, List, Optional

# .env 먼저 로드 (OPENAI_API_KEY 등)
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv(dotenv_path=(Path(__file__).resolve().parent.parent / ".env"))
except Exception:
    pass

from openai import OpenAI

# ===== build_prompt 주입(없어도 안전하게) =====
try:
    from prompts import build_prompt  # 사용자가 만든 커스텀 프롬프트
except Exception:
    def build_prompt(
        location: str,
        days: int,
        budget: int,
        companions: List[str] | str,
        style: List[str] | str,
        selected_places: List[str],
        travel_date: str,
        count: int = 3,
    ) -> str:
        """
        prompts 모듈이 없을 때의 안전 기본 프롬프트.
        (사용자 모듈이 있으면 그걸 우선 사용)
        """
        comp = ", ".join(companions) if isinstance(companions, list) else str(companions)
        sty  = ", ".join(style) if isinstance(style, list) else str(style)
        sel  = "\n".join(f"- {p}" for p in selected_places) if selected_places else "없음"
        return f"""
[목표]
입력 정보를 모두 반영하여 '{count}개'의 3일치 여행 일정을 한 번에 생성한다.
각 일정은 반드시 '아침/점심/저녁' 3개 활동으로 구성하며, 한국어로 작성한다.

[입력]
- 여행지: {location}
- 여행일수: {days}일
- 동반자: {comp or '없음'}
- 여행스타일: {sty or '미정'}
- 총예산(원): {budget}
- 여행시작일: {travel_date}
- 선호 장소(있으면 반영): 
{sel}

[형식 규칙 — 매우 중요]
1) 출력은 마크다운 코드블록 금지. 순수 텍스트만.
2) 각 일정은 아래 제목으로 시작:
   일정추천 1: {location} {days}일 코스
   일정추천 2: ...
   일정추천 3: ...
3) 각 일정은 정확히 3일(Day1~Day3)이며, 매일 아침/점심/저녁 3개 타임라인을 포함.
   - 날짜 표기: YYYY-MM-DD (요일)
   - 시간 표기: 09:00 ~ 11:30  <장소명> (도로명주소)
4) 장소명은 '실제 존재하는 상호명'만 사용. 괄호 안에는 반드시 '도로명 주소'를 표기.
5) 하루별 소계/총계 금지. 각 일정의 '마지막'에만 '총 예상 비용' 1회 표기.
6) 총 예상 비용은 입력 예산의 ±15% 범위를 반드시 지킨다.
7) 일정 사이에는 한 줄에 '---' 만 넣어 구분.

[작성 가이드]
- 동선 합리적(이동 과도 금지), 동반자/스타일/선호장소 반영.
- 실내/실외 균형, 휴식 고려.
- 비용은 합리적인 금액(식사비 등)을 사용하되 마지막 합계만 노출.

이제 바로 3개 일정을 생성하라.
""".strip()


# ─────────────────────────────────────────────────────────
# OpenAI 클라이언트 (키는 .env의 OPENAI_API_KEY 사용)
# ─────────────────────────────────────────────────────────
def _make_client() -> Optional[OpenAI]:
    try:
        key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_APIKEY")
        if not key:
            return None
        return OpenAI(api_key=key)
    except Exception:
        return None

client: Optional[OpenAI] = _make_client()

# ===== 시스템 규칙(최상단에서 강력히 고정) =====
SYSTEM_STRICT = """
너는 여행 일정 전문가다. 아래 모든 규칙을 반드시 지켜라.

필수 규칙:
- 출력은 '텍스트'만. 마크다운 코드블록(```), 표, 불릿, 인라인 코드 절대 금지.
- 각 일정 제목은 반드시 '일정추천 N:' 형식으로 시작하고, 일정들 사이에는 한 줄로 '---' 만 넣어 구분.
- 각 일정은 정확히 3일치이며, 매일 '아침/점심/저녁' 3개 활동을 포함한다.
- 각 날짜는 'YYYY-MM-DD (요일)' 형식으로 모두 포함되어야 한다. 하루라도 누락되면 전체를 다시 작성한다.
- 각 활동 라인은 'HH:MM ~ HH:MM 장소명 (도로명 주소)' 형식으로, '실제 존재하는 상호명'만 사용하고 괄호에 도로명 주소를 반드시 넣는다.
- '총 예상 비용'은 각 일정의 맨 마지막에 '단 1회만' 표기한다. (하루별/활동별 소계 금지)
- 총 예상 비용은 입력 예산의 ±15% 범위를 반드시 지킨다.
- 한국어로 간결하고 사실적으로 작성한다.
"""

def _strip_code_fence(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n").strip()
    # 선행/후행 코드펜스 제거
    if s.startswith("```"):
        s = s.split("```", 2)[-1]
    if s.endswith("```"):
        s = s.rsplit("```", 1)[0]
    return s.strip()

def _dedent_triple_dash(s: str) -> str:
    # ' --- ' 같은 변형을 깔끔히 '---' 한 줄로 통일
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
    count: int = 3,
) -> str:
    """
    build_prompt()로 프롬프트를 만들고, 한 번의 호출로
    '일정추천 1..N'을 모두 생성한다.
    - 반환: 파싱 가능한 '텍스트' (코드펜스 제거, --- 구분 보정)
    """
    if client is None:
        # 키가 없을 때는 샘플 반환 (서버 죽지 않도록)
        return (
            f"일정추천 1: {location} 3일 샘플\n"
            f"{travel_date} (Day1)\n09:00 ~ 12:00 {location} 주요명소 A (도로명주소 예시)\n"
            "12:00 ~ 13:30 점심 (도로명주소 예시)\n"
            f"14:00 ~ 18:00 {location} 체험/산책 (도로명주소 예시)\n"
            "19:00 ~ 20:30 저녁 (도로명주소 예시)\n"
            "---\n일정추천 2: 샘플\n---\n일정추천 3: 샘플"
        )

    # 사용자 커스텀 프롬프트(또는 안전 기본 프롬프트)
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
        temperature=0.2,         # 규칙 준수 성향 강화
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_STRICT},
            {"role": "user", "content": prompt},
        ],
    )
    text = (resp.choices[0].message.content or "").strip()
    text = _strip_code_fence(text)
    text = _dedent_triple_dash(text)
    return text


def ask_gpt(prompt: str, destination: Optional[str] = None) -> str:
    """
    간단 질의/후처리용. destination이 있으면 문맥에 추가.
    반환: 순수 텍스트
    """
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
    return _strip_code_fence(out.choices[0].message.content or "").strip()


def extract_places(text: str):
    """
    기존 호환 헬퍼.
    - '관광지 추천' 섹션과 '맛집 추천' 섹션에서 번호로 시작하는 줄을 각각 수집.
    """
    sightseeing, restaurants = [], []
    current = None
    for line in (text or "").splitlines():
        s = line.strip()
        if "관광지 추천" in s:
            current = "s"; continue
        if "맛집 추천" in s:
            current = "r"; continue
        if s[:1].isdigit():  # '1.' 같은 번호줄
            if current == "s":
                sightseeing.append(line)
            elif current == "r":
                restaurants.append(line)
    return sightseeing, restaurants
