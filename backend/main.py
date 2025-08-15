# backend/main.py
from __future__ import annotations

# ========= .env 먼저 로드(키 인식 문제 예방) =========
from pathlib import Path
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv(dotenv_path=(Path(__file__).resolve().parent.parent / ".env"))
except Exception:
    pass

# ========= 표준/써드파티 =========
import re
import json
import urllib.parse
import traceback
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

  # ===== 내부 모듈 (항상 상대 경로로) =====
def _try_imports():
    """
    backend 패키지로 실행하거나(uvicorn backend.main:app),
    루트에서 실행할 때 모두 동작하도록 import 경로를 유연하게 처리.
    """
 
try:
    from .gpt_client import generate_schedule_gpt, client
except Exception as e:
    # 절대경로로 실행할 때를 대비한 백업
    from gpt_client import generate_schedule_gpt, client  # type: ignore

try:
    from .gpt_places_recommender import ask_gpt, extract_places
except Exception:
    # 없으면 더미 함수로 막아두기
    def ask_gpt(prompt: str, destination: str | None = None) -> str:
        return prompt
    def extract_places(text: str):
        return [], []

try:
    from .naver_api import search_place, search_and_rank_places, search_image as _search_image
except Exception:
    from .naver_api import search_place, search_and_rank_places  # type: ignore
    _search_image = None  # 이미지 검색이 없더라도 서버가 떠야 함

# ========= FastAPI =========
app = FastAPI(title="JustGo API (Unified)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 필요 시 프론트 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# (선택) 간단 요청 로깅
@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        body_bytes = await request.body()
        body_text = body_bytes.decode("utf-8", errors="ignore")
        print("\n========== [REQ] ==========")
        print(f"{request.method} {request.url}")
        if body_text:
            print(f"[BODY] {body_text[:800]}")
    except Exception:
        pass
    resp = await call_next(request)
    try:
        print(f"[RES] status={resp.status_code}")
        print("===========================\n")
    except Exception:
        pass
    return resp

# ========= 유틸 =========
def _model_to_dict(m):
    return m.model_dump() if hasattr(m, "model_dump") else m.dict()

def ask_gpt_safe(prompt: str, destination: Optional[str] = None) -> str:
    """프로젝트별 ask_gpt 시그니처 차이를 흡수하는 래퍼."""
    try:
        return ask_gpt(prompt, destination=destination)
    except TypeError:
        try:
            return ask_gpt(prompt, destination)  # 구버전 시그니처
        except TypeError:
            return ask_gpt(prompt)               # 매개변수 하나만 받는 경우

def _normalize_gpt_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"^```(?:\w+)?\n", "", text)
    text = re.sub(r"\n```$", "", text)
    return text.strip()

def parse_total_cost(text: str) -> int:
    """'약 12,000원' / '12000원' 등 다양한 표기 합산."""
    prices = re.findall(r'(?:약\s*)?(\d{1,3}(?:,\d{3})+|\d+)\s*원', text)
    total = 0
    for p in prices:
        try:
            total += int(p.replace(",", ""))
        except Exception:
            pass
    return total

def expected_date_strings(start: date, num_days: int) -> tuple[list[str], list[str]]:
    dts = [(datetime.combine(start, datetime.min.time()) + timedelta(days=i)) for i in range(num_days)]
    full = [dt.strftime("%Y-%m-%d (%a)") for dt in dts]
    short = [dt.strftime("%Y-%m-%d") for dt in dts]
    return full, short

def block_has_all_dates(block_text: str, full_dates: list[str], short_dates: list[str]) -> bool:
    return all((fd in block_text) or (sd in block_text) for fd, sd in zip(full_dates, short_dates))

def _preview(text: str, n: int = 350) -> str:
    if not text:
        return ""
    t = text.replace("\n", "\\n")
    return t[:n] + ("..." if len(t) > n else "")

def generate_naver_map_url(place_name: str, destination: Optional[str] = None, address: Optional[str] = None) -> str:
    parts = [place_name]
    if destination:
        parts.append(destination)
    if address:
        toks = (address or "").split()
        if toks:
            parts.append(toks[0])
        if len(toks) > 1:
            parts.append(toks[1])
    seen, qparts = set(), []
    for p in parts:
        p = (p or "").strip()
        if p and p not in seen:
            seen.add(p)
            qparts.append(p)
    return f"https://map.naver.com/v5/search/{urllib.parse.quote(' '.join(qparts))}"

def _safe_search_image(q: str, prefer_food: bool = False, strict: bool = True) -> Optional[str]:
    """naver_api.search_image가 없거나 시그니처가 달라도 안전 호출."""
    if _search_image is None:
        return None
    try:
        # 새 시그니처(prefer_food, strict)
        return _search_image(q, prefer_food=prefer_food, strict=strict)  # type: ignore
    except TypeError:
        try:
            # 옛 시그니처(인자 하나)
            return _search_image(q)  # type: ignore
        except Exception:
            return None
    except Exception:
        return None

# ========= “플레이스홀더 줄만” 보강 =========
PLACEHOLDER_PAT = re.compile(r"(주요명소|명소|관광|관광지|체험|산책|카페|휴식|식당|맛집|점심|저녁|아침)", re.I)
_ADDR_PAT = re.compile(r"\((?:[^()]*?(?:로|길|구|시|도|동|읍|면)[^()]*)\)")
_COST_PAT = re.compile(r"(?:약\s*)?(?:\d{1,3}(?:,\d{3})+|\d+)\s*원")
_TIME_RE = re.compile(r"\b\d{2}:\d{2}\s*~\s*\d{2}:\d{2}\b")

def line_has_address(line: str) -> bool:
    return bool(_ADDR_PAT.search(line))

def line_has_cost(line: str) -> bool:
    return bool(_COST_PAT.search(line))

def line_looks_like_placeholder(line: str) -> bool:
    m = re.match(r"\s*\d{2}:\d{2}\s*~\s*\d{2}:\d{2}\s+(.+)", line)
    if not m:
        return False
    name = m.group(1).split("(")[0].strip()
    return bool(PLACEHOLDER_PAT.search(name))

def _replace_line_with_real_place(line: str, city: str) -> str:
    try:
        m = re.match(r"(\s*\d{2}:\d{2}\s*~\s*\d{2}:\d{2})\s+(.+)", line)
        if not m:
            return line
        time_span, rest = m.groups()
        name_only = rest.split("(")[0].strip()
        if not PLACEHOLDER_PAT.search(name_only):
            return line

        kw = "관광지"
        if re.search(r"(점심|아침|브런치)", rest, re.I):
            kw = "맛집"
        elif re.search(r"저녁", rest, re.I):
            kw = "맛집"
        elif re.search(r"(카페|휴식)", rest, re.I):
            kw = "카페"

        q = f"{city} {kw}"
        info = search_place(q) or {}
        cand_name = info.get("name") or info.get("title") or q
        cand_name = re.sub(r"<[^>]+>", "", str(cand_name))  # 네이버 <b>태그 제거
        addr = info.get("address") or ""
        return f"{time_span} {cand_name}" + (f" ({addr})" if addr else "")
    except Exception:
        return line

# ========= 실제 장소 검증/치환 유틸 (추가) =========
_HTML_TAG = re.compile(r"<[^>]+>")

def _clean_html(s: str) -> str:
    return _HTML_TAG.sub("", s or "").strip()

def _best_place(city: str, name_or_keyword: str) -> dict:
    """
    네이버 장소 검색에서 첫 결과만 가져오되, None 안전 처리.
    name_or_keyword는 '경주 대릉원' 같은 구체명 or '경주 관광지' 같은 키워드.
    """
    try:
        q = f"{city} {name_or_keyword}".strip()
        info = search_place(q) or {}
        # key 정리(실제 구현체에 따라 name/title 중 하나만 있을 수 있음)
        info_name = _clean_html(info.get("name") or info.get("title") or "")
        if not info_name:
            return {}
        info["__resolved_name"] = info_name
        return info
    except Exception:
        return {}

_CAT_HINTS = [
    (re.compile(r"(아침|브런치)", re.I), "브런치 카페"),
    (re.compile(r"(점심|식사|런치)", re.I), "맛집"),
    (re.compile(r"(저녁|디너)", re.I), "맛집"),
    (re.compile(r"(카페|디저트|휴식)", re.I), "카페"),
    (re.compile(r"(관광|명소|체험|산책|공원|박물관|전시|유적|사찰)", re.I), "관광지"),
]

def _guess_keyword_from_line(rest: str) -> str:
    for rx, kw in _CAT_HINTS:
        if rx.search(rest or ""):
            return kw
    return "관광지"

_TS_RE = re.compile(r"^\s*(\d{2}:\d{2}\s*~\s*\d{2}:\d{2})\s+(.+?)\s*$")

def _verify_and_enrich_line(line: str, city: str) -> str:
    """
    '09:00 ~ 11:00 XX' 형태의 라인에서 XX가 실제 장소인지 확인하고
    주소가 없다면 주소를 붙여서 반환. 검색 실패 시 카테고리 키워드로 대체.
    비용(약 x원) 같은 문구는 유지.
    """
    m = _TS_RE.match(line)
    if not m:
        return line

    span, rest = m.groups()
    # (가격/주소) 괄호부를 떼서 core name만 얻기
    core = rest.split("(")[0].strip()

    # 1) 정확명으로 검색
    info = _best_place(city, core)

    # 2) 실패하면 카테고리 힌트로 대체 후보 검색
    if not info:
        kw = _guess_keyword_from_line(rest)
        info = _best_place(city, kw)

    # 3) 그래도 실패하면 원문 라인 반환
    if not info:
        return line

    name = info.get("__resolved_name") or core
    addr = (info.get("address") or "").strip()
    # 기존 라인에서 ( ... ) 괄호에 이미 주소/가격이 섞여 있을 수 있으니, 괄호부에서 '원' 가격만 추출하고 주소는 새로 붙임
    # 가격 부분만 남기기
    price_part = None
    m_price = re.search(r"(약\s*\d{1,3}(?:,\d{3})+|\d+)\s*원", rest)
    if m_price:
        # ' (약 12,000원)' 형태로 붙일 수 있게 보관
        price_txt = m_price.group(0)
        price_part = f" {price_txt}" if price_txt.startswith("약") else f" 약 {price_txt}"

    # 주소를 괄호로, 가격은 뒤에 같이 붙임
    if addr:
        enriched = f"{span} {name} ({addr})"
    else:
        enriched = f"{span} {name}"

    if price_part and price_part.strip():
        # 이미 괄호가 있다면 그대로 두고, 없다면 뒤에 가격만 추가 (중복 방지)
        if "원)" in enriched or "원" in enriched:
            return enriched
        return enriched + f" ({price_part.strip()})"

    return enriched

def verify_and_enrich_block(detail: str, city: str) -> str:
    """
    일정 블록 전체를 실제 장소 기반으로 보강.
    - 각 타임라인 라인을 검증/치환
    - 주소가 없으면 주소 추가
    """
    lines = (detail or "").splitlines()
    out = []
    for ln in lines:
        # 주소/비용이 이미 충분히 붙어 있더라도 verify 한 번은 해보면서 이름 정합성 맞춤
        if _TIME_RE.search(ln):
            out.append(_verify_and_enrich_line(ln, city))
        else:
            out.append(ln)
    return "\n".join(out).strip()


# ========= 스키마 =========
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
    base_point: Optional[Tuple[float, float]] = None

class RecommendRequest(BaseModel):
    destination: str
    dates: List[str] = Field(default_factory=list)
    companions: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    hasPet: bool = False
    budget: Optional[int] = None
    selected_places: List[str] = Field(default_factory=list)
    base_point: Optional[Tuple[float, float]] = None
    query: Optional[str] = None
    # 친구 코드 기능 유지: 음식 카테고리(한식/양식/중식/일식/카페/패스트푸드)
    food_categories: List[str] = Field(default_factory=list)

class Review(BaseModel):
    text: str
    stars: Optional[float] = None

class Place(BaseModel):
    name: str
    category: str     # "관광지" or "음식점"
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

# 데모 일정 목록
mock_schedules = [
    {"id": 1, "title": "제주도 여행", "dates": "2025.08.10 ~ 08.12"},
    {"id": 2, "title": "부산 가족여행", "dates": "2025.08.15 ~ 08.17"},
    {"id": 3, "title": "서울 데이트 코스", "dates": "2025.09.01"},
]

# ========= 파싱/백업 유틸(3개 보장) =========
SECTION_PATTERNS = [
    r"(일정추천\s*\d+\s*:\s*[^\n]+)",
    r"(?:^|\n)#+\s*(일정추천\s*\d+\s*[:：]?\s*[^\n]+)",
    r"(?:^|\n)\*\*\s*(일정추천\s*\d+\s*[:：]?\s*[^\n]+)\s*\*\*",
]

def _extract_sections(text: str) -> list[tuple[str, str]]:
    text = _normalize_gpt_text(text or "")
    for pat in SECTION_PATTERNS:
        matches = list(re.finditer(pat, text, flags=re.I))
        if matches:
            sections: list[tuple[str, str]] = []
            for i, m in enumerate(matches):
                title = m.group(1).strip()
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                body = text[start:end].strip()
                sections.append((title, body))
            if sections:
                return sections
    # 백업: --- 구분선
    chunks = re.split(r"\n\s*---\s*\n", text)
    if len(chunks) >= 2:
        return [(f"일정추천 {i+1}", ch.strip()) for i, ch in enumerate(chunks)]
    return []

def _build_sample_itinerary(location: str, start_date: str, days: int, title: str) -> str:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    lines = [title, ""]
    for i in range(days):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d (%a)")
        lines += [
            f"{d} (Day{i+1})",
            f"09:00 ~ 12:00 {location} 주요명소 A (약 0원)",
            "12:00 ~ 13:30 점심 (약 12,000원)",
            f"14:00 ~ 18:00 {location} 체험/산책 (약 0원)",
            "19:00 ~ 20:30 저녁 (약 15,000원)",
            "",
        ]
    return "\n".join(lines).strip()

def _ensure_three(sections: list[tuple[str, str]], req: "ScheduleRequest") -> list[tuple[str, str]]:
    if len(sections) >= req.count:
        return sections[: req.count]
    out = list(sections)
    for i in range(req.count - len(out)):
        idx = len(out) + 1
        title = f"일정추천 {idx}: {req.location} {req.days}일 샘플"
        body = _build_sample_itinerary(req.location, req.travel_date, req.days, title)
        out.append((title, body))
    return out[: req.count]

# ========= 엔드포인트 =========
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/schedules", response_model=List[Schedule])
def get_schedules():
    return mock_schedules

@app.post("/api/plan", response_model=ScheduleResponse)
def create_plan(req: ScheduleRequest):
    """
    GPT 호출 → 견고 파싱 → 3개 보장 → (필요시) 날짜 보정 → 플레이스홀더 보강 → 품질 가드 → 비용 재계산 → base_point 추출
    """
    try:
        # 1) GPT 호출(실패해도 계속 진행)
        try:
            raw = generate_schedule_gpt(
                location=req.location,
                days=req.days,
                style=req.style,
                companions=req.companions,
                budget=req.budget,
                selected_places=req.selected_places,
                travel_date=req.travel_date,
                count=req.count,
            ) or ""
        except Exception as e:
            print("[/api/plan] generate_schedule_gpt ERROR:", e)
            raw = ""

        raw = _normalize_gpt_text(raw)
        sections = _ensure_three(_extract_sections(raw), req)  # 정확히 req.count개 보장

        start_dt = datetime.strptime(req.travel_date, "%Y-%m-%d").date()
        full_dates, short_dates = expected_date_strings(start_dt, req.days)

        schedules: List[ScheduleItem] = []
        base_point: Optional[Tuple[float, float]] = None
        first_point_locked = False

        for i, (title, body) in enumerate(sections):
            detail = (body or "").strip()

            # (1) 날짜 누락 보정(최대 1회)
            if not block_has_all_dates(detail, full_dates, short_dates) and client is not None:
                try:
                    messages = [
                        {"role": "system", "content": (
                            "너는 여행 일정 전문가야. 모든 날짜(아침/점심/저녁 포함)를 작성하고, "
                            "실제 존재하는 상호명과 도로명 주소를 포함하며, 총 예상비용은 마지막에만 1회 작성한다."
                        )},
                        {"role": "user", "content": (
                            "아래 일정 블록에서 일부 날짜가 누락되었습니다. 누락된 날짜를 포함해 동일한 형식으로 보완하세요.\n\n"
                            f"[누락된 날짜]: {', '.join([sd for fd, sd in zip(full_dates, short_dates) if (fd not in detail) and (sd not in detail)])}\n\n"
                            f"[기존 블록]\n{detail}"
                        )},
                    ]
                    resp = client.chat.completions.create(
                        model="gpt-4o-mini", messages=messages, temperature=0.3,
                    )
                    patched = (resp.choices[0].message.content or "").strip()
                    if patched:
                        detail = _normalize_gpt_text(patched)
                except Exception:
                    pass

            # (2) 플레이스홀더 줄만 실제 상호/주소로 보강
            fixed_lines: list[str] = []
            for line in (detail.splitlines() or []):
                if line_has_address(line) or line_has_cost(line):
                 fixed_lines.append(line)
                elif line_looks_like_placeholder(line):
                    fixed_lines.append(_replace_line_with_real_place(line, req.location))
                else:
                    fixed_lines.append(line)
            detail = verify_and_enrich_block(detail, req.location)

            # (3) 품질 가드(너무 짧거나 '...' 위주, 시간 구간 부족, 날짜 미포함 등)
            time_spans = _TIME_RE.findall(detail)
            has_any_date = any((fd in detail) or (sd in detail) for fd, sd in zip(full_dates, short_dates))
            if (len(detail) < 140) or (len(time_spans) < 2) or ("..." in detail) or ("…") in detail or (not has_any_date):
                detail = verify_and_enrich_block(detail, req.location)

            # (4) 총비용 문구 제거 → 재계산 후 1회만 표기
            detail = re.sub(r"총 예상 비용.*?원\W*", "", detail)
            cost = parse_total_cost(detail)
            detail += f"\n\n총 예상 비용은 약 {cost:,}원으로, 입력 예산인 {req.budget:,}원 내에서 잘 계획되었어요."

            schedules.append(ScheduleItem(title=title, detail=detail))

            # (5) base_point: 첫 일정의 첫 타임라인 줄에서 장소 좌표
            if (not first_point_locked) and i == 0:
                for line in detail.splitlines():
                    m = re.search(r"\b\d{2}:\d{2}\s*~\s*\d{2}:\d{2}\s*([^(]+)", line)
                    if not m:
                        continue
                    place_name = m.group(1).strip()
                    sp = search_place(f"{req.location} {place_name}") or {}
                    try:
                        lat, lng = float(sp.get("lat")), float(sp.get("lng"))
                        base_point = (lat, lng)
                        first_point_locked = True
                    except Exception:
                        pass
                    break

        return ScheduleResponse(schedules=schedules, base_point=base_point)

    except Exception as e:
        # 최후 방어: 샘플 3개라도 반환(프론트 빨간 경고 방지)
        print("[/api/plan][FATAL]", e)
        traceback.print_exc()
        fallback: List[ScheduleItem] = []
        for i in range(3):
            title = f"일정추천 {i+1}: {req.location} {req.days}일 샘플"
            body = _build_sample_itinerary(req.location, req.travel_date, req.days, title)
            cost = parse_total_cost(body)
            body += f"\n\n총 예상 비용은 약 {cost:,}원으로, 입력 예산인 {req.budget:,}원 내에서 잘 계획되었어요."
            fallback.append(ScheduleItem(title=title, detail=body))
        return ScheduleResponse(schedules=fallback, base_point=None)

# ========= 관광지 추천(친구 코드 유지) =========
@app.post("/api/recommend/attractions", response_model=RecommendResponse)
def recommend_attractions(req: RecommendRequest):
    try:
        print("\n[REQ] /api/recommend/attractions", _model_to_dict(req))
        try:
            prompt = generate_schedule_gpt(
                location=req.destination,
                days=len(req.dates) if req.dates else 3,
                style=", ".join(req.styles) if req.styles else "자유 여행",
                companions=", ".join(req.companions) if req.companions else "없음",
                budget=req.budget or 0,
                selected_places=req.selected_places,
                travel_date=req.dates[0] if req.dates else str(date.today()),
            )
        except Exception as e:
            print("[ERROR] generate_schedule_gpt:", e); traceback.print_exc()
            return RecommendResponse(places=[])

        try:
            gpt_text = ask_gpt_safe(prompt, req.destination)
        except Exception as e:
            print("[ERROR] ask_gpt:", e); traceback.print_exc()
            return RecommendResponse(places=[])

        try:
            sightseeing, _ = extract_places(gpt_text or "")
        except Exception as e:
            print("[ERROR] extract_places:", e); traceback.print_exc()
            return RecommendResponse(places=[])

        places: List[Place] = []
        for raw in sightseeing:
            try:
                cleaned = re.sub(r"^\d+\.\s*", "", raw or "")
                name = (cleaned.split("-")[0] if cleaned else "").strip()
                if not name:
                    continue
                info = search_place(name) or {}
                addr = info.get("address")
                url = generate_naver_map_url(name, req.destination, addr)
                img = None
                iq = f"{name} {req.destination} 관광지"
                if addr:
                    iq += f" {addr.split()[0]}"
                img = _safe_search_image(iq, prefer_food=False, strict=True)
                places.append(Place(
                    name=name, category="관광지", address=addr,
                    rating=info.get("rating"), review_count=info.get("review_count"),
                    naver_url=url, image_url=img, reviews=[]
                ))
            except Exception as loop_e:
                print("[WARN] attractions loop:", loop_e); traceback.print_exc()
                continue
        return RecommendResponse(places=places)
    except Exception as e:
        print("[FATAL] attractions:", e); traceback.print_exc()
        return RecommendResponse(places=[])

# ========= 음식점 추천(친구 코드 유지) =========
FOOD_BROAD = {
    "한식": ["한식","백반","한정식","국밥","비빔밥","갈비","불고기","냉면","순대","곱창","족발","막창","삼겹","한우","곰탕","칼국수","전골"],
    "양식": ["양식","스테이크","파스타","피자","브런치","버거","샐러드","그릴","비스트로","수제버거","리조또","스페인","이탈리안"],
    "중식": ["중식","짜장","자장","짬뽕","탕수육","중화","딤섬","마라","훠궈","양꼬치","마라탕","마라상궈"],
    "일식": ["일식","스시","초밥","오마카세","라멘","우동","돈카츠","텐동","야키니쿠","사시미","이자카야"],
    "카페": ["카페","디저트","커피","베이커리","케이크","빵집","브런치카페","티룸","dessert","coffee","bakery"],
    "패스트푸드": ["분식","떡볶이","김밥","라볶이","튀김","순대","치킨","피자","버거","핫도그","샌드위치","kfc","맥도날드","롯데리아"]
}
def _guess_broad_category(name: str, cat_str: str) -> Optional[str]:
    s = f"{name or ''} {cat_str or ''}".lower()
    for broad, kws in FOOD_BROAD.items():
        for kw in kws:
            if kw.lower() in s:
                return broad
    return None
def _want_category(name: str, cat_str: str, wanted: List[str]) -> bool:
    if not wanted:
        return True
    broad = _guess_broad_category(name, cat_str)
    if broad and broad in wanted:
        return True
    s = f"{name or ''} {cat_str or ''}".lower()
    for w in wanted:
        if w in FOOD_BROAD:
            if any(kw.lower() in s for kw in FOOD_BROAD[w]):
                return True
        else:
            if w.lower() in s:
                return True
    return False

@app.post("/api/recommend/restaurants", response_model=RecommendResponse)
def recommend_restaurants(req: RecommendRequest):
    try:
        print("\n[REQ] /api/recommend/restaurants", _model_to_dict(req))
        try:
            prompt = generate_schedule_gpt(
                location=req.destination,
                days=len(req.dates) if req.dates else 3,
                style=", ".join(req.styles) if req.styles else "자유 여행",
                companions=", ".join(req.companions) if req.companions else "없음",
                budget=req.budget or 0,
                selected_places=req.selected_places,
                travel_date=req.dates[0] if req.dates else str(date.today()),
            )
        except Exception as e:
            print("[ERROR] generate_schedule_gpt:", e); traceback.print_exc()
            return RecommendResponse(places=[])

        try:
            gpt_text = ask_gpt_safe(prompt, req.destination)
        except Exception as e:
            print("[ERROR] ask_gpt:", e); traceback.print_exc()
            return RecommendResponse(places=[])

        try:
            _, restaurants = extract_places(gpt_text or "")
        except Exception as e:
            print("[ERROR] extract_places:", e); traceback.print_exc()
            return RecommendResponse(places=[])

        wanted = list(dict.fromkeys(req.food_categories or []))  # 중복 제거
        places: List[Place] = []
        for raw in restaurants:
            try:
                cleaned = re.sub(r"^\d+\.\s*", "", raw or "")
                name = (cleaned.split("-")[0] if cleaned else "").strip()
                if not name:
                    continue
                info = search_place(name) or {}
                addr = info.get("address")
                cat_str = info.get("category") or ""
                if not _want_category(name, cat_str, wanted):
                    continue
                url = generate_naver_map_url(name, req.destination, addr)
                iq = f"{name} {req.destination}"
                if addr:
                    iq += f" {addr.split()[0]}"
                img = _safe_search_image(iq, prefer_food=True, strict=True)
                places.append(Place(
                    name=name, category="음식점", address=addr,
                    rating=info.get("rating"), review_count=info.get("review_count"),
                    naver_url=url, image_url=img, reviews=[]
                ))
            except Exception as loop_e:
                print("[WARN] restaurants loop:", loop_e); traceback.print_exc()
                continue
        return RecommendResponse(places=places)
    except Exception as e:
        print("[FATAL] restaurants:", e); traceback.print_exc()
        return RecommendResponse(places=[])

# ========= (호환) 통합 장소 추천 =========
@app.post("/api/recommend/places", response_model=RecommendResponse)
def recommend_places(req: RecommendRequest):
    """
    관광지+맛집을 한 번에. 새 프론트는 분리 호출 권장.
    """
    try:
        prompt = generate_schedule_gpt(
            location=req.destination,
            days=len(req.dates) if req.dates else 3,
            style=", ".join(req.styles) if req.styles else "자유 여행",
            companions=", ".join(req.companions) if req.companions else "없음",
            budget=req.budget or 0,
            selected_places=req.selected_places,
            travel_date=req.dates[0] if req.dates else str(date.today()),
        )
        gpt_text = ask_gpt_safe(prompt, req.destination)
        sightseeing, restaurants = extract_places(gpt_text or "")

        places: List[Place] = []

        # 관광지
        for raw in sightseeing:
            try:
                cleaned = re.sub(r"^\d+\.\s*", "", raw or "")
                name = (cleaned.split("-")[0] if cleaned else "").strip()
                if not name:
                    continue
                info = search_place(name) or {}
                addr = info.get("address")
                url = generate_naver_map_url(name, req.destination, addr)
                iq = f"{name} {req.destination} 관광지"
                if addr:
                    iq += f" {addr.split()[0]}"
                img = _safe_search_image(iq, prefer_food=False, strict=True)
                places.append(Place(
                    name=name, category="관광지", address=addr,
                    rating=info.get("rating"), review_count=info.get("review_count"),
                    naver_url=url, image_url=img, reviews=[]
                ))
            except Exception:
                traceback.print_exc()
                continue

        # 맛집
        for raw in restaurants:
            try:
                cleaned = re.sub(r"^\d+\.\s*", "", raw or "")
                name = (cleaned.split("-")[0] if cleaned else "").strip()
                if not name:
                    continue
                info = search_place(name) or {}
                addr = info.get("address")
                url = generate_naver_map_url(name, req.destination, addr)
                iq = f"{name} {req.destination}"
                if addr:
                    iq += f" {addr.split()[0]}"
                img = _safe_search_image(iq, prefer_food=True, strict=True)
                places.append(Place(
                    name=name, category="음식점", address=addr,
                    rating=info.get("rating"), review_count=info.get("review_count"),
                    naver_url=url, image_url=img, reviews=[]
                ))
            except Exception:
                traceback.print_exc()
                continue

        return RecommendResponse(places=places)

    except Exception as e:
        print("[FATAL] places:", e); traceback.print_exc()
        return RecommendResponse(places=[])

# ========= 채팅 편집(JSON 강제 + 룰기반 백업) =========
class ChatRequest(BaseModel):
    message: str
    itineraryIndex: int
    itineraryText: Optional[str] = None
    context: Optional[Dict] = None  # {"budget": 300000} 등

class ChatResponse(BaseModel):
    reply: str
    updatedItinerary: Optional[str] = None

SYSTEM_EDIT = """
너는 여행 일정 '편집자'다. 반드시 아래 규칙을 지켜라.
출력 형식: 오직 JSON 한 줄만! (코드블록/설명/마크다운 금지)
{
  "reply": "<간단한 한국어 답변 한 문장>",
  "updated_itinerary": "<수정이 반영된 전체 일정 텍스트(제목 포함 원래 형식 유지)>"
}
편집 원칙:
- 사용자가 준 '현재 일정' 텍스트를 기계적으로 수정해서 반환한다(새로 생성하지 말 것).
- 날짜/시간 포맷, 라인 순서, 전체 형식은 그대로 유지.
- 시간이 바뀌면 '09:00 ~ 10:30' 같은 라인을 실제로 수정.
- '저녁을 더 가볍게' → 저녁 라인의 장소/설명을 가벼운 식사로 바꾸고 비용을 6,000~10,000원대로 낮춘다.
- '시간을 X시에' → 해당 구간 시작 시간을 X시로 바꾸고, 종료 시각도 기존 소요시간을 유지하도록 조정한다.
- 예산 관련 요청은 해당 라인의 '약 xx,xxx원' 숫자도 일관되게 조정.
- 수정이 없으면 updated_itinerary에 원문을 그대로 넣는다.
"""

_HOUR_IN_MSG = re.compile(r"(\d{1,2})\s*시")

def _shift_time_span(span: str, new_start_hour: int) -> str:
    m = re.search(r"(\d{2}):(\d{2})\s*~\s*(\d{2}):(\d{2})", span)
    if not m:
        return span
    sH, sM, eH, eM = map(int, m.groups())
    dur = (eH*60+eM) - (sH*60+sM)
    if dur <= 0:
        dur = 90
    start = new_start_hour*60 + sM
    end = start + dur
    eH2, eM2 = (end//60)%24, end%60
    return f"{new_start_hour:02d}:{sM:02d} ~ {eH2:02d}:{eM2:02d}"

def _lighten_dinner(line: str) -> str:
    line = re.sub(r"저녁[^\(]*", "저녁(가벼운 간단식/분식/샐러드)", line)
    if re.search(r"\d+\s*원", line):
        line = re.sub(r"(약\s*)?(\d{1,3}(?:,\d{3})+|\d+)\s*원", "약 8,000원", line)
    else:
        line += " (약 8,000원)"
    return line

def _edit_itinerary_rules(text: str, message: str) -> tuple[str, str]:
    lines = text.splitlines()
    edited = False
    reply = "요청을 반영했습니다."
    m_hour = _HOUR_IN_MSG.search(message)
    want_hour = None
    if m_hour:
        try:
            h = int(m_hour.group(1))
            if 0 <= h <= 23:
                want_hour = h
        except Exception:
            pass
    want_lighter = bool(re.search(r"(가볍게|라이트|light)", message, re.I))

    for i, line in enumerate(lines):
        if "저녁" not in line:
            continue
        if want_hour is not None and re.search(r"\d{2}:\d{2}\s*~\s*\d{2}:\d{2}", line):
            lines[i] = re.sub(r"\d{2}:\d{2}\s*~\s*\d{2}:\d{2}", lambda m: _shift_time_span(m.group(0), want_hour), line)
            line = lines[i]
            edited = True
            reply = f"저녁 시작 시간을 {want_hour}시로 조정했어요."
        if want_lighter:
            lines[i] = _lighten_dinner(line)
            edited = True
            reply = "저녁을 가벼운 식사로 바꿨어요(비용도 줄였어요)."
    return reply, ("\n".join(lines) if edited else text)

@app.post("/api/chat", response_model=ChatResponse)
def chat_edit(req: ChatRequest):
    original = req.itineraryText or ""
    backup_reply, backup_text = _edit_itinerary_rules(original, req.message)

    if client is None:
        return ChatResponse(reply=backup_reply, updatedItinerary=backup_text)

    try:
        out = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_EDIT},
                {"role": "user", "content":
                    f"[선택 인덱스] {req.itineraryIndex}\n\n"
                    f"[현재 일정]\n{original}\n\n"
                    f"[사용자 요청]\n{req.message}\n\n"
                    f"[예산]\n{(req.context or {}).get('budget', '알 수 없음')}"
                },
            ],
            temperature=0.3,
            response_format={"type": "json_object"},  # JSON 강제
        )
        content = (out.choices[0].message.content or "").strip()
        try:
            data = json.loads(content)
            reply = (data.get("reply") or "").strip() or backup_reply
            updated = (data.get("updated_itinerary") or "").strip()
            if updated:
                return ChatResponse(reply=reply, updatedItinerary=updated)
            return ChatResponse(reply=backup_reply, updatedItinerary=backup_text)
        except Exception:
            return ChatResponse(reply=backup_reply, updatedItinerary=backup_text)
    except Exception as e:
        return ChatResponse(reply=f"{backup_reply} (모델 오류: {e})", updatedItinerary=backup_text)
