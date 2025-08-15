# backend/main.py  (파일명이 app.py여도 동일하게 사용 가능)
from __future__ import annotations

import json
import re
import urllib.parse
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict

# ── (중요) .env 를 최우선으로 로드 ─────────────────────────
from pathlib import Path
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    # 프로젝트 루트(…/JustGo-ai/.env)에서 로드
    load_dotenv(dotenv_path=(Path(__file__).resolve().parent.parent / ".env"))
except Exception:
    # dotenv가 없어도 진행은 되게 함(환경변수 직접 세팅된 경우)
    pass

# ── FastAPI ──────────────────────────────────────────────
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── 내부 모듈 (반드시 dotenv 로드 이후 import) ────────────
from .gpt_client import generate_schedule_gpt, client  # client: OpenAI(...) 혹은 None/미설치 대응
from .gpt_places_recommender import ask_gpt, extract_places
from .naver_api import search_place, search_and_rank_places, search_image

try:
    from naver_api import search_image as _search_image
except Exception:
    _search_image = None


# ── FastAPI 기본 설정 ────────────────────────────────────
app = FastAPI(title="JustGo API (Unified)")

app.add_middleware(
    CORSMiddleware,
    # 필요 시 특정 도메인만 허용하고 싶으면 아래 2줄만 남겨도 됨
    allow_origins=["*", "http://127.0.0.1:5500", "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 요청/응답 간단 로그 (디버그용)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    body = await request.body()
    try:
        body_text = body.decode("utf-8")
    except Exception:
        body_text = str(body)
    print("\n========== [REQ] ==========")
    print(f"{request.method} {request.url}")
    if body_text:
        print(f"[BODY] {body_text[:800]}")
    resp = await call_next(request)
    print(f"[RES] status={resp.status_code}")
    print("===========================\n")
    return resp


# ── 유틸 ────────────────────────────────────────────────
def parse_total_cost(text: str) -> int:
    """본문의 '약 xx,xxx원' 패턴을 모두 합산."""
    prices = re.findall(r'약\s*([\d,]+)원', text)
    return sum(int(p.replace(',', '')) for p in prices)


def expected_date_strings(start: date, num_days: int) -> tuple[list[str], list[str]]:
    """YYYY-MM-DD (Tue)와 YYYY-MM-DD 두 포맷 모두 준비(검증용)."""
    dts = [(datetime.combine(start, datetime.min.time()) + timedelta(days=i)) for i in range(num_days)]
    full = [dt.strftime("%Y-%m-%d (%a)") for dt in dts]
    short = [dt.strftime("%Y-%m-%d") for dt in dts]
    return full, short


def block_has_all_dates(block_text: str, full_dates: list[str], short_dates: list[str]) -> bool:
    return all((fd in block_text) or (sd in block_text) for fd, sd in zip(full_dates, short_dates))


def repair_block_with_missing_dates(block_text: str, missing_dates: list[str]) -> str:
    """
    일정 블록에서 날짜가 누락되면 GPT에게 보완 요청(한 번).
    실패 시 원문 유지.
    """
    if not missing_dates:
        return block_text
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "너는 여행 일정 전문가야. 모든 날짜(아침/점심/저녁 포함)를 작성하고, "
                    "실제 존재하는 상호명과 도로명 주소를 포함하며, 총 예상비용은 마지막에만 1회 작성한다."
                ),
            },
            {
                "role": "user",
                "content": (
                    "아래 일정 블록에서 일부 날짜가 누락되었습니다. 누락된 날짜를 포함해 동일한 형식으로 보완하세요.\n\n"
                    f"[누락된 날짜]: {', '.join(missing_dates)}\n\n[기존 블록]\n{block_text}"
                ),
            },
        ]
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return block_text


def generate_naver_map_url(place_name: str, destination: Optional[str] = None, address: Optional[str] = None) -> str:
    """네이버 지도 검색 URL을 더 구체적으로 생성(도시/주소 앞 토큰 포함)."""
    parts = [place_name]
    if destination:
        parts.append(destination)
    if address:
        toks = address.split()
        parts.extend(toks[:2])  # 시/구 정도만
    dedup: list[str] = []
    for p in parts:
        p = (p or "").strip()
        if p and p not in dedup:
            dedup.append(p)
    q = " ".join(dedup)
    return f"https://map.naver.com/v5/search/{urllib.parse.quote(q)}"


def _preview(text: str, n: int = 350) -> str:
    if text is None:
        return ""
    t = text.replace("\n", "\\n")
    return t[:n] + ("..." if len(t) > n else "")


def _safe_search_image(q: str) -> Optional[str]:
    """이미지 검색이 불가능한 환경이면 None 반환."""
    if _search_image is None:
        return None
    try:
        return _search_image(q)
    except Exception:
        return None


def _call_ask_gpt(prompt: str, destination: Optional[str] = None) -> str:
    """
    ask_gpt 시그니처가 (prompt) 또는 (prompt, destination)일 수 있으므로 안전호출.
    """
    try:
        # 일부 구현은 (prompt, destination)을 받음
        return ask_gpt(prompt, destination)  # type: ignore[arg-type]
    except TypeError:
        # 기본 (prompt)만 받는 구현
        return ask_gpt(prompt)  # type: ignore[misc]


# ── 스키마 ──────────────────────────────────────────────
class ScheduleRequest(BaseModel):
    location: str
    days: int
    style: str
    companions: List[str] = []
    budget: int
    selected_places: List[str] = []
    travel_date: str
    count: int = 3


class ScheduleItem(BaseModel):
    title: str
    detail: str


class ScheduleResponse(BaseModel):
    schedules: List[ScheduleItem]
    base_point: Optional[Tuple[float, float]] = None  # 첫 장소 좌표(후속 추천 기준)


class RecommendRequest(BaseModel):
    destination: str
    dates: List[str] = Field(default_factory=list)
    companions: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    hasPet: bool = False
    budget: Optional[int] = None
    selected_places: List[str] = Field(default_factory=list)
    base_point: Optional[Tuple[float, float]] = None  # 기준점(없으면 도시 대표점/첫 장소 좌표)
    query: Optional[str] = None                      # 사용자가 입력한 원문 쿼리


class Review(BaseModel):
    text: str
    stars: Optional[float] = None


class Place(BaseModel):
    name: str
    category: str
    address: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    naver_url: Optional[str] = None
    image_url: Optional[str] = None
    distance_km: Optional[float] = None
    score: Optional[float] = None
    reviews: List[Review] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    places: List[Place]


class Schedule(BaseModel):
    id: int
    title: str
    dates: str


# ── Chat 편집 스키마 (신규) ─────────────────────────────
class ChatRequest(BaseModel):
    message: str
    itineraryIndex: int = Field(..., ge=0)
    itineraryText: Optional[str] = None
    context: Optional[Dict] = None  # {"budget": 300000} 등


class ChatResponse(BaseModel):
    reply: str
    updatedItinerary: Optional[str] = None


# 샘플 일정(옵션)
mock_schedules = [
    {"id": 1, "title": "제주도 여행", "dates": "2025.08.10 ~ 08.12"},
    {"id": 2, "title": "부산 가족여행", "dates": "2025.08.15 ~ 08.17"},
    {"id": 3, "title": "서울 데이트 코스", "dates": "2025.09.01"},
]


# ── 엔드포인트 ─────────────────────────────────────────
@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/schedules", response_model=List[Schedule])
def get_schedules():
    print("[/api/schedules] return mock_schedules len:", len(mock_schedules))
    return mock_schedules


@app.post("/api/plan", response_model=ScheduleResponse)
def create_plan(req: ScheduleRequest):
    """
    GPT로 일정 3개 생성 → 날짜 누락 보정 → 총비용 재계산 → 첫 일정 첫 장소에서 좌표(base_point) 캐시
    프론트는 반환된 base_point를 이후 추천 API에 넘기면, '직전 일정과 거리'까지 고려한 추천 가능.
    """
    try:
        print("[/api/plan] payload:", req.model_dump())

        raw = generate_schedule_gpt(
            location=req.location,
            days=req.days,
            style=req.style,
            companions=req.companions,
            budget=req.budget,
            selected_places=req.selected_places,
            travel_date=req.travel_date,
            count=req.count,
        )
        print("[/api/plan] raw GPT preview:", _preview(raw))

        raw_blocks = re.split(r"(?:---)?\s*일정추천\s*\d+:", raw.strip())
        titles = re.findall(r"(일정추천\s*\d+:\s*[^\n]+)", raw.strip())
        start_dt = datetime.strptime(req.travel_date, "%Y-%m-%d").date()
        full_dates, short_dates = expected_date_strings(start_dt, req.days)

        schedules: List[ScheduleItem] = []
        base_point: Optional[Tuple[float, float]] = None
        first_point_locked = False

        for i, block in enumerate(raw_blocks[1:]):
            title = titles[i] if i < len(titles) else f"일정추천 {i+1}"
            detail = block.strip()

            # 날짜 누락 보정 1회
            if not block_has_all_dates(detail, full_dates, short_dates):
                missing = [sd for fd, sd in zip(full_dates, short_dates) if (fd not in detail) and (sd not in detail)]
                detail = repair_block_with_missing_dates(detail, missing)

            # 총비용 문구 제거 후 재계산
            detail = re.sub(r"총 예상 비용.*?원\W*", "", detail)
            cost = parse_total_cost(detail)
            detail += f"\n\n총 예상 비용은 약 {cost:,}원으로, 입력 예산인 {req.budget:,}원 내에서 잘 계획되었어요."

            schedules.append(ScheduleItem(title=title, detail=detail))

            # 첫 일정의 첫 “시간 줄”에서 장소 추출 → 좌표 잠금
            if (not first_point_locked) and i == 0:
                for line in detail.splitlines():
                    m = re.search(r"\b\d{2}:\d{2}\s*~\s*\d{2}:\d{2}\s*([^(]+)", line)
                    if not m:
                        continue
                    place_name = m.group(1).strip()
                    sp = search_place(f"{req.location} {place_name}")
                    if sp and sp.get("lat") and sp.get("lng"):
                        try:
                            base_point = (float(sp["lat"]), float(sp["lng"]))
                            first_point_locked = True
                        except Exception:
                            pass
                    break

        print("[/api/plan] schedules:", len(schedules), "base_point:", base_point)
        return ScheduleResponse(schedules=schedules, base_point=base_point)

    except Exception as e:
        print("[/api/plan][ERROR]", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recommend/places", response_model=RecommendResponse)
def recommend_places(req: RecommendRequest):
    """
    네이버 지역검색 기반 랭킹:
    - 기준점(base_point 또는 도시 대표점)으로부터 거리 + 키워드 적합도로 정렬
    - 반환: 네이버 지도 링크/거리/점수/이미지(가능 시)
    """
    try:
        print("[/api/recommend/places] payload:", req.model_dump())

        # 기준점 결정
        base = req.base_point
        if base is None:
            city = search_place(req.destination)
            base = (float(city["lat"]), float(city["lng"])) if city else (37.5665, 126.9780)

        query_for_rank = req.query or f"{req.destination} 맛집"

        candidates = search_and_rank_places(
            prev_lat=base[0],
            prev_lng=base[1],
            keyword=query_for_rank,
            max_distance_km=5.0,
            display=30,
        )

        places: List[Place] = []
        for c in candidates[:20]:
            addr = c.get("address")
            naver_url = c.get("naver_url") or generate_naver_map_url(c["name"], req.destination, addr)
            image_url = _safe_search_image(
                f"{c['name']} {req.destination} 맛집 {addr.split()[0] if addr else ''}"
            )

            places.append(
                Place(
                    name=c["name"],
                    category="음식점",
                    address=addr,
                    rating=None,
                    review_count=None,
                    naver_url=naver_url,
                    image_url=image_url,
                    distance_km=c.get("distance_km"),
                    score=c.get("score"),
                    reviews=[],
                )
            )

        print("[/api/recommend/places] return:", len(places))
        return RecommendResponse(places=places)

    except Exception as e:
        print("[/api/recommend/places][ERROR]", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/recommend/attractions", response_model=RecommendResponse)
def recommend_attractions(req: RecommendRequest):
    """
    관광지 전용:
    - GPT로 후보명 추출(시그니처 자동 감지) → 네이버 검색 검증
    - URL/이미지 부여
    """
    try:
        print("[/api/recommend/attractions] payload:", req.model_dump())

        seed_prompt = generate_schedule_gpt(
            location=req.destination,
            days=len(req.dates) if req.dates else 3,
            style=", ".join(req.styles) if req.styles else "자유 여행",
            companions=", ".join(req.companions) if req.companions else "없음",
            budget=req.budget or 0,
            selected_places=req.selected_places,
            travel_date=req.dates[0] if req.dates else str(date.today()),
        )

        gpt_text = _call_ask_gpt(seed_prompt, req.destination)
        sightseeing, _ = extract_places(gpt_text)
        print(f"[/api/recommend/attractions] extracted sightseeing={len(sightseeing)}")

        places: List[Place] = []
        for raw_name in sightseeing:
            name = re.sub(r"^\d+\.\s*", "", raw_name).split("-")[0].strip()
            info = search_place(name)
            addr = info.get("address") if info else None
            naver_url = generate_naver_map_url(name, req.destination, addr)
            image_url = _safe_search_image(
                f"{name} {req.destination} 관광지 {addr.split()[0] if addr else ''}"
            )

            places.append(
                Place(
                    name=name,
                    category="관광지",
                    address=addr,
                    rating=None,
                    review_count=None,
                    naver_url=naver_url,
                    image_url=image_url,
                    reviews=[],
                )
            )

        print("[/api/recommend/attractions] return:", len(places))
        return RecommendResponse(places=places)

    except Exception as e:
        print("[/api/recommend/attractions][ERROR]", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


# ── 채팅 편집 엔드포인트 (신규) ─────────────────────────
SYSTEM_EDIT = """너는 여행 일정 편집자다.
입력으로 현재 일정 마크다운과 사용자 요청을 받으면 'JSON 문자열'만 출력한다.
다른 텍스트 금지. 키는 정확히 reply, updated_itinerary 두 개만 사용.

규칙:
- 한국어.
- 일정 포맷(제목 '일정추천 N', 다음 줄에 '---', 3일분 아침/점심/저녁) 유지.
- 예산이 제공되면 총 예상 비용은 예산의 ±15% 안에서 '일정 마지막에 1번만' 표기.
- 날짜별 비용 표기 금지.
- 장소는 실존 명칭 사용.
반환 예시:
{"reply":"요청 반영 설명","updated_itinerary":"일정추천 1\\n---\\nDay1 ...\\nDay2 ...\\nDay3 ...\\n\\n총 예상 비용: 270,000원"}
"""

def _build_chat_user_prompt(req: ChatRequest) -> str:
    budget = None
    if isinstance(req.context, dict):
        budget = req.context.get("budget")
    return (
        f"[선택 인덱스] {req.itineraryIndex}\n\n"
        f"[현재 일정]\n{req.itineraryText or '(없음)'}\n\n"
        f"[사용자 요청]\n{req.message}\n\n"
        f"[예산]\n{budget if budget is not None else '알 수 없음'}"
    )

@app.post("/api/chat", response_model=ChatResponse)
def chat_edit(req: ChatRequest):
    """
    선택한 일정에 대한 편집 대화.
    반환: { reply, updatedItinerary? }
    """
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message가 비어 있습니다.")

    # OpenAI 클라이언트가 없거나 키가 없으면 목업 응답
    if client is None:
        return ChatResponse(
            reply=f'(목업) "{req.message}" 요청을 반영했습니다.',
            updatedItinerary=req.itineraryText or None
        )

    try:
        messages = [
            {"role": "system", "content": SYSTEM_EDIT},
            {"role": "user", "content": _build_chat_user_prompt(req)},
        ]
        out = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
        )
        content = out.choices[0].message.content or ""
        # 모델은 JSON 문자열만 내도록 시켰지만 안전하게 파싱 보강
        try:
            data = json.loads(content)
            reply = (data.get("reply") or "").strip() or "수정했습니다."
            updated = data.get("updated_itinerary")
            if isinstance(updated, str):
                updated = updated.strip() or None
            return ChatResponse(reply=reply, updatedItinerary=updated)
        except Exception:
            # JSON 파싱 실패 시 원문을 reply로 반환
            return ChatResponse(reply=content.strip() or "응답 해석 실패")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")
