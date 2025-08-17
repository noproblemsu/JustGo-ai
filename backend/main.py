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
import time
import random
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any, Set

from fastapi import FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ========= 내부 모듈(상대/절대 모두 허용) =========
try:
    # 패키지 실행(권장): python -m uvicorn backend.main:app ...
    from .gpt_client import generate_schedule_gpt, client
except Exception:
    # app-dir 방식 실행 대비
    from gpt_client import generate_schedule_gpt, client  # type: ignore

try:
    from .gpt_places_recommender import ask_gpt, extract_places
except Exception:
    try:
        from gpt_places_recommender import ask_gpt, extract_places  # type: ignore
    except Exception:
        # 없으면 더미
        def ask_gpt(prompt: str, destination: str | None = None) -> str:
            return prompt
        def extract_places(text: str):
            return [], []

try:
    from .naver_api import search_place, search_and_rank_places, search_image as _search_image, naver_map_link
except Exception:
    try:
        from naver_api import search_place, search_and_rank_places, search_image as _search_image, naver_map_link  # type: ignore
    except Exception:
        _search_image = None  # 이미지 검색이 없더라도 서버가 떠야 함
        def search_place(q: str) -> Dict[str, Any]: return {}
        def search_and_rank_places(query: str, limit: int = 20, sort: str = "review_desc", **kw): return []
        def naver_map_link(name: str) -> str: return ""

# ========= FastAPI =========
app = FastAPI(title="JustGo API (Unified)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 간단 요청 로깅
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

# 날짜 헤더/시간 라인 정리 유틸 
_DATE_HDR = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*\(.*\)")

def fix_header_order(detail: str) -> str:
    """
    [시간 라인] 바로 다음 줄이 [날짜 헤더] 라인이면 두 줄의 순서를 바꿔서
    '날짜 → 시간'이 되도록 고친다.
    (스크린샷의 빨강/파랑 케이스를 정확히 처리)
    """
    if not detail:
        return detail
    lines = detail.splitlines()
    out = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        if _TIME_RE.search(cur) and i + 1 < len(lines) and _DATE_HDR.match(lines[i + 1].strip()):
            # swap: [시간] [날짜] -> [날짜] [시간]
            out.append(lines[i + 1])
            out.append(cur)
            i += 2
            continue
        out.append(cur)
        i += 1
    return "\n".join(out).strip()
    # 날짜 헤더 인식
_DATE_HDR_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*\(.*\)\s*$")

# ====== Chat 편집용: 장소 교체 규칙 ======
_REP_PATTERNS = [
    # "불국사를 빼고 경주월드를 넣어줘"
    re.compile(r"(?P<rm>[\w가-힣\s]+?)(?:을|를)?\s*(?:빼|삭제|제외)\w*\s*(?:하고|,|그리고|및)?\s*(?P<add>[\w가-힣\s]+?)(?:을|를)?\s*(?:넣|추가|대체|교체)\w*", re.I),
    # "불국사를 경주월드로 바꿔줘"
    re.compile(r"(?P<rm>[\w가-힣\s]+?)(?:을|를)?\s*(?P<add>[\w가-힣\s]+?)\s*로\s*(?:바꾸|변경|교체)\w*", re.I),
    # "불국사 대신 경주월드"
    re.compile(r"(?P<rm>[\w가-힣\s]+?)\s*대신\s*(?P<add>[\w가-힣\s]+)", re.I),
]

def _extract_replace_intent(msg: str) -> list[tuple[str, str]]:
    msg = (msg or "").strip()
    out = []
    for rx in _REP_PATTERNS:
        m = rx.search(msg)
        if m:
            rm = (m.group("rm") or "").strip()
            add = (m.group("add") or "").strip()
            if rm and add:
                out.append((rm, add))
    return out

def _guess_city_from_itinerary(text: str) -> str:
    # "일정추천 1: 경주 3일 샘플" → 경주
    m = re.search(r"일정추천\s*\d+\s*[:：]\s*([^\s\d]+)\s*\d+일", text)
    if m:
        return (m.group(1) or "").strip()
    # 주소 내 "...시" 추출 → "경주시" → "경주"
    m = re.search(r"\((?:[^()]*?)([가-힣]{2,6}시)\b", text)
    if m:
        return re.sub(r"(시|군|구)$", "", m.group(1))
    return ""

def _apply_place_replacements(text: str, message: str, budget: int | None = None) -> tuple[str, str] | None:
    """
    message에서 'A 빼고 B 넣어' / 'A를 B로 바꿔' / 'A 대신 B' 를 찾아
    일정 텍스트의 '시간줄'에서 장소명을 교체한다.
    - 시간 범위/식사 라벨은 그대로 유지
    - 주소는 가능한 경우 채워 넣음
    - 비용 라벨 다시 계산, 총액도 재계산
    """
    pairs = _extract_replace_intent(message)
    if not pairs:
        return None

    city = _guess_city_from_itinerary(text)
    lines = text.splitlines()
    changed = 0

    for i, ln in enumerate(lines):
        if not _TIME_RE.search(ln):
            continue
        span, core = _place_core_from_line(ln)
        if not core:
            continue
        low = core.lower()
        for rm, add in pairs:
            if rm.lower() in low:  # 포함 매칭(정확 일치가 아니어도 교체)
                meal = _guess_meal_from_line(ln)
                label = "아침" if meal == "breakfast" else "점심" if meal == "lunch" else "저녁" if meal == "dinner" else None
                addr = _addr_for(city, add) if city else ""
                prefix = f"{label}: " if label else ""
                span = span or _extract_time_span(ln) or "14:00 ~ 18:00"
                lines[i] = f"{span} {prefix}{add}" + (f" ({addr})" if addr else "")
                changed += 1
                break

    if changed == 0:
        return None

    new_text = "\n".join(lines).strip()

    # 비용 라벨/총액 재계산
    new_text = ensure_costs_per_line(new_text, city, budget)
    new_text = re.sub(r"총 예상 비용.*?원\W*", "", new_text)
    total = parse_total_cost(new_text)
    new_text += f"\n\n총 예상 비용은 약 {total:,}원으로 조정했어요."

    # 요약 답변
    if len(pairs) == 1:
        rm, add = pairs[0]
        reply = f"'{rm}'를 '{add}'로 교체했어요."
    else:
        reply = f"{len(pairs)}건의 장소 교체를 반영했어요."
    return reply, new_text


def fix_header_time_swaps(detail: str) -> str:
    """
    '시간 라인' 다음 줄에 '날짜 헤더'가 오는 잘못된 순서를 발견하면
    두 줄을 스왑해서 헤더가 먼저 오게 고친다.
    (빨간/파란 표기처럼 헤더가 한 줄 아래로 밀린 케이스 교정)
    """
    if not detail:
        return detail
    lines = detail.splitlines()
    i = 0
    while i < len(lines) - 1:
        if _TIME_RE.search(lines[i]) and _DATE_HDR_RE.match(lines[i + 1]):
            # swap
            lines[i], lines[i + 1] = lines[i + 1], lines[i]
        i += 1
    return "\n".join(lines).strip()

def dedupe_time_and_place(detail: str) -> str:
    """
    일정 '전체'에서 같은 장소(핵심명)가 두 번 이상 나오면
    첫 발생만 남기고 나머지 라인을 제거한다.
    (노란색으로 표시한 반복 라인 제거)
    """
    if not detail:
        return detail
    out = []
    seen: set[str] = set()
    for ln in detail.splitlines():
        if _TIME_RE.search(ln):
            _, core = _place_core_from_line(ln)
            if core:
                key = core.lower()
                if key in seen:
                    # 중복 발견 → 해당 라인 제거(건너뛰기)
                    continue
                seen.add(key)
        out.append(ln)
    # 빈 줄 정리
    cleaned = []
    prev_blank = False
    for ln in out:
        if ln.strip() == "":
            if prev_blank:
                continue
            prev_blank = True
        else:
            prev_blank = False
        cleaned.append(ln)
    return "\n".join(cleaned).strip()


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

def _norm_place(p: str) -> str:
    return re.sub(r"\s+", " ", (p or "").strip())



# 전역 힌트(랜덤 후보 풀 생성 시 사용)
STYLE_HINTS_G = {
    "SNS": ["핫플", "포토스팟", "인스타", "뷰맛집", "전망대"],
    "핫플": ["핫플", "포토스팟", "인스타"],
    "자연": ["자연", "호수", "숲길", "해변", "산책"],
    "힐링": ["힐링", "온천", "스파", "정원", "산책"],
    "역사": ["유적지", "박물관", "고궁", "전시"],
    "체험": ["체험", "공방", "액티비티"],
    "맛집": ["맛집", "현지 맛집"],
}
COMP_HINTS_G = {
    "가족": ["아이와", "키즈", "체험", "박물관"],
    "아이": ["아이와", "키즈"],
    "친구": ["포토스팟", "핫플"],
    "연인": ["야경", "전망대", "산책"],
    "부모님": ["사찰", "정원", "유적지", "한옥"],
}

# ========= NAVER 호출 안전 래퍼/캐시 =========
_NAVER_CACHE: dict[str, dict] = {}
_NAVER_RATE_LIMIT_UNTIL = 0.0  # epoch seconds
_NAVER_COOLDOWN_SEC = 60       # 429 맞으면 60초 쉬기
_NAVER_POLITE_DELAY = 0.12     # 호출 간 딜레이

def _naver_ok() -> bool:
    return time.time() >= _NAVER_RATE_LIMIT_UNTIL

def _search_place_safe(q: str) -> dict:
    """캐시 + 429 쿨다운 + 소량 딜레이."""
    global _NAVER_RATE_LIMIT_UNTIL
    now = time.time()
    if now < _NAVER_RATE_LIMIT_UNTIL:
        return {}
    if q in _NAVER_CACHE:
        return _NAVER_CACHE[q]
    try:
        res = search_place(q) or {}
        _NAVER_CACHE[q] = res
        time.sleep(_NAVER_POLITE_DELAY)
        return res
    except RuntimeError as e:
        msg = str(e)
        if "429" in msg or "Rate limit" in msg:
            _NAVER_RATE_LIMIT_UNTIL = now + _NAVER_COOLDOWN_SEC
            print(f"[NAVER] rate-limited. cooling down {_NAVER_COOLDOWN_SEC}s")
        return {}
    except Exception:
        return {}

# ========= 패턴들 =========
PLACEHOLDER_PAT = re.compile(r"(주요명소|명소|관광|관광지|체험|산책|카페|휴식|식당|맛집|점심|저녁|아침)", re.I)
_ADDR_PAT = re.compile(r"\((?:[^()]*?(?:로|길|구|시|도|동|읍|면)[^()]*)\)")
_COST_PAT = re.compile(r"(?:약\s*)?(?:\d{1,3}(?:,\d{3})+|\d+)\s*원")
_TIME_RE = re.compile(r"\b\d{2}:\d{2}\s*~\s*\d{2}:\d{2}\b")
_TS_RE = re.compile(r"^\s*(\d{2}:\d{2}\s*~\s*\d{2}:\d{2})\s+(.+?)\s*$")
_MEAL_PREFIX = re.compile(r"^(?:아침|브런치|점심|런치|저녁|디너)\s*(?:[:：]\s*|\s+)", re.I)
_MEAL_PAT = re.compile(r"(아침|브런치|점심|런치|저녁|디너)", re.I)

# ========= 보조 유틸 =========
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

def _strip_meal_prefix(s: str) -> str:
    return _MEAL_PREFIX.sub("", s or "").strip()

def _place_name_from_line(line: str) -> str:
    m = _TS_RE.match(line)
    if not m:
        return ""
    _, rest = m.groups()
    core = rest.split("(")[0].strip()
    return _strip_meal_prefix(core)

def _extract_time_span(line: str) -> Optional[str]:
    m = re.match(r"^\s*(\d{2}:\d{2}\s*~\s*\d{2}:\d{2})\s+.*$", line.strip())
    return m.group(1) if m else None

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
        return _search_image(q, prefer_food=prefer_food, strict=strict)  # type: ignore
    except TypeError:
        try:
            return _search_image(q)  # type: ignore
        except Exception:
            return None
    except Exception:
        return None

def _clean_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()

def _best_place(city: str, name_or_keyword: str) -> dict:
    """네이버 장소 검색에서 첫 결과만 가져오되 None 안전."""
    try:
        q = f"{city} {name_or_keyword}".strip()
        info = _search_place_safe(q) or {}
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

# ========= 날짜 처리 =========
def expected_date_strings(start: date, num_days: int) -> tuple[list[str], list[str]]:
    dts = [(datetime.combine(start, datetime.min.time()) + timedelta(days=i)) for i in range(num_days)]
    full = [dts[i].strftime("%Y-%m-%d") + f" (Day{i+1})" for i in range(num_days)]
    short = [dt.strftime("%Y-%m-%d") for dt in dts]
    return full, short

def block_has_all_dates(block_text: str, full_dates: list[str], short_dates: list[str]) -> bool:
    return all((fd in block_text) or (sd in block_text) for fd, sd in zip(full_dates, short_dates))

def _day_template(date_label: str, city: str) -> list[str]:
    return [
        f"{date_label}",
        "08:00 ~ 09:30 아침",
        f"09:30 ~ 12:00 {city} 주요명소 A",
        "12:00 ~ 13:30 점심",
        f"14:00 ~ 18:00 {city} 체험/산책",
        "19:00 ~ 20:30 저녁",
        ""
    ]

def ensure_all_days(detail: str, full_dates: list[str], city: str) -> str:
    text = (detail or "").strip()
    lines = text.splitlines()
    body = "\n".join(lines).strip()
    missing: list[str] = []
    for d in full_dates:
        date_token = d[:10]
        if (d not in body) and (date_token not in body):
            missing.append(d)
    if not missing:
        return body
    if not body.endswith("\n\n"):
        body += "\n\n"
    for d in missing:
        body += "\n".join(_day_template(d, city)) + "\n"
    return body.strip()

# ========= 후보/선택 주입 =========
def _unique_list(seq: list[str]) -> list[str]:
    seen = set()
    out = []
    for s in seq or []:
        p = _norm_place(s)
        k = p.lower()
        if p and k not in seen:
            seen.add(k)
            out.append(p)
    return out

def _addr_for(city: str, name: str) -> str:
    try:
        info = _search_place_safe(f"{city} {name}") or {}
        return (info.get("address") or info.get("roadAddress") or info.get("addr") or "").strip()
    except Exception:
        return ""

def _collect_names(rows: list[dict]) -> list[str]:
    out, seen = [], set()
    for it in rows or []:
        name = _clean_html(it.get("name") or it.get("title") or it.get("place_name") or "")
        addr = (it.get("address") or it.get("road_address") or it.get("addr") or "").strip()
        k = f"{name}|{addr}"
        if name and k not in seen:
            seen.add(k)
            out.append(name)
    return out

def _build_candidate_pools(city: str, styles: list[str], companions: list[str],
                           budget: Optional[int], limit: int = 25) -> tuple[list[str], list[str]]:
    q_atr = [f"{city} 관광지"]
    q_rst = [f"{city} 맛집"]
    for s in styles or []:
        for key, hints in STYLE_HINTS_G.items():
            if key in s or s in key:
                for h in hints:
                    q_atr.append(f"{city} {h}")
    for c in companions or []:
        for key, hints in COMP_HINTS_G.items():
            if key in c or c in key:
                for h in hints:
                    q_atr.append(f"{city} {h}")
    if budget is not None and budget <= 100_000:
        q_atr += [f"{city} 무료", f"{city} 산책"]
        q_rst += [f"{city} 분식", f"{city} 가성비 맛집"]

    atr_names, rst_names = [], []
    try:
        for q in dict.fromkeys(q_atr).keys():
            rows = search_and_rank_places(query=q, limit=limit, sort="review_desc") or []
            atr_names += _collect_names(rows)
            if len(atr_names) >= limit: break
        for q in dict.fromkeys(q_rst).keys():
            rows = search_and_rank_places(query=q, limit=limit, sort="review_desc") or []
            rst_names += _collect_names(rows)
            if len(rst_names) >= limit: break
    except Exception:
        pass
    return _unique_list(atr_names), _unique_list(rst_names)

def inject_selected_once_and_fill(detail: str, city: str,
                                  styles: list[str], companions: list[str], budget: Optional[int],
                                  selected_attractions: list[str], selected_restaurants: list[str]) -> str:
    """
    - selected_* 는 일정 전체에서 각 1회만 사용
    - 나머지 슬롯은 스타일/동반자/예산 기반 후보에서 랜덤으로 채움
    - 오전/오후 슬롯은 날짜당 최대 한 번만 치환
    """
    text = (detail or "").strip()
    if not text:
        return text

    random.seed(hash((city, "|".join(styles or []), "|".join(companions or []), budget, len(text))) & 0xFFFFFFFF)
    cand_atr, cand_rst = _build_candidate_pools(city, styles, companions, budget)

    sel_atr = _unique_list(selected_attractions)
    sel_rst = _unique_list(selected_restaurants)
    random.shuffle(sel_atr)
    random.shuffle(sel_rst)

    lines = text.splitlines()
    date_idx = [i for i, ln in enumerate(lines) if re.match(r"^\d{4}-\d{2}-\d{2}\s*\(.*\)", ln.strip())]

    used_all: set[str] = set()
    for ln in lines:
        if _TIME_RE.search(ln):
            nm = _place_name_from_line(ln)
            if nm: used_all.add(nm.lower())

    def _pick(pool: list[str]) -> Optional[str]:
        while pool:
            n = pool.pop(0)
            if n.lower() not in used_all:
                used_all.add(n.lower())
                return n
        return None

    def _ensure_meal(block: list[str], label: str, default_span: str) -> int:
        idx = None
        for j, bl in enumerate(block):
            if label in bl: idx = j; break
        if idx is None:
            if label in ("아침","브런치"):
                block.insert(1, f"{default_span} 아침")
                idx = 1
            else:
                block.append(f"{default_span} {label}")
                idx = len(block)-1
        return idx

    for k in range(len(date_idx)):
        start = date_idx[k]
        end   = date_idx[k+1] if k+1 < len(date_idx) else len(lines)
        block = lines[start:end]

        # 필수 식사 라인 확보
        idx_breakfast = _ensure_meal(block, "아침",  "08:00 ~ 09:30")
        idx_lunch     = _ensure_meal(block, "점심",  "12:00 ~ 13:30")
        idx_dinner    = _ensure_meal(block, "저녁",  "19:00 ~ 20:30")

        # 오전/오후 슬롯 위치 탐색
        idx_0912 = None
        idx_1418 = None
        for j, bl in enumerate(block):
            s = bl.strip()
            if re.search(r"09:\d{2}\s*~\s*12:\d{2}", s): idx_0912 = j
            if re.search(r"14:\d{2}\s*~\s*18:\d{2}", s): idx_1418 = j

        # (1) 오전 슬롯 치환 (블록 스캔이 끝난 후 '한 번만' 수행)
        if idx_0912 is not None and (line_looks_like_placeholder(block[idx_0912]) or not line_has_address(block[idx_0912])):
            picked = _pick(sel_atr) or _pick(cand_atr)
            if picked:
                addr = _addr_for(city, picked)
                block[idx_0912] = f"09:30 ~ 12:00 {picked}" + (f" ({addr})" if addr else "")

        # (2) 오후 14~18 관광지 (없으면 추가, 있으면 치환)
        if idx_1418 is not None and (line_looks_like_placeholder(block[idx_1418]) or not line_has_address(block[idx_1418])):
            picked = _pick(sel_atr) or _pick(cand_atr)
            if picked:
                addr = _addr_for(city, picked)
                block[idx_1418] = f"14:00 ~ 18:00 {picked}" + (f" ({addr})" if addr else "")
        elif idx_1418 is None:
            picked = _pick(sel_atr) or _pick(cand_atr)
            if picked:
                addr = _addr_for(city, picked)
                ins_at = idx_dinner if idx_dinner is not None else len(block)
                block.insert(ins_at, f"14:00 ~ 18:00 {picked}" + (f" ({addr})" if addr else ""))

        # (3) 아침/점심/저녁 맛집 라인 채우기(플레이스홀더거나 주소 없으면 교체)
        for idx_meal, default_span, label in [
            (idx_breakfast, "08:00 ~ 09:30", "아침"),
            (idx_lunch,     "12:00 ~ 13:30", "점심"),
            (idx_dinner,    "19:00 ~ 20:30", "저녁"),
        ]:
            if idx_meal is None:
                continue
            line = block[idx_meal]
            if line_looks_like_placeholder(line) or not line_has_address(line):
                picked = _pick(sel_rst) or _pick(cand_rst)
                if picked:
                    span = _extract_time_span(line) or default_span
                    addr = _addr_for(city, picked)
                    block[idx_meal] = f"{span} {label}: {picked}" + (f" ({addr})" if addr else "")

        lines[start:end] = block  # 날짜 블록 반영

    return "\n".join(lines).strip()

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
        if re.search(r"(점심|아침|브런치|저녁|디너|런치)", rest, re.I):
            kw = "맛집"
        elif re.search(r"(카페|휴식|디저트|베이커리)", rest, re.I):
            kw = "카페"
        q = f"{city} {kw}"
        info = _search_place_safe(q) or {}
        cand_name = _clean_html(info.get("name") or info.get("title") or q)
        addr = info.get("address") or ""
        return f"{time_span} {cand_name}" + (f" ({addr})" if addr else "")
    except Exception:
        return line

def verify_and_enrich_block(detail: str, city: str) -> str:
    """일정 블록 전체를 실제 장소 기반으로 보강."""
    lines = (detail or "").splitlines()
    out = []
    for ln in lines:
        if _TIME_RE.search(ln):
            # _verify_and_enrich_line 내부에서 가격 보존/식사라벨 보존
            m = _TS_RE.match(ln)
            if not m:
                out.append(ln); continue
            span, rest = m.groups()
            core = rest.split("(")[0].strip()
            info = _best_place(city, core) or _best_place(city, _guess_keyword_from_line(rest))
            if not info:
                out.append(ln); continue
            name = info.get("__resolved_name") or core
            addr = (info.get("address") or "").strip()
            meal_label = None
            if re.search(r"(아침|브런치)", rest, re.I): meal_label = "아침"
            elif re.search(r"(점심|런치)", rest, re.I):   meal_label = "점심"
            elif re.search(r"(저녁|디너)", rest, re.I):  meal_label = "저녁"
            price_part = None
            m_price = re.search(r"(약\s*\d{1,3}(?:,\d{3})+|\d+)\s*원", rest)
            if m_price:
                price_txt = m_price.group(0)
                price_part = f" {price_txt}" if price_txt.startswith("약") else f" 약 {price_txt}"
            enriched = f"{span} {meal_label + ': ' if meal_label else ''}{name}" + (f" ({addr})" if addr else "")
            if price_part and price_part.strip():
                if "원)" not in enriched:
                    enriched = enriched + f" ({price_part.strip()})"
            out.append(enriched)
        else:
            out.append(ln)
    return "\n".join(out).strip()

def dedupe_places(detail: str, city: str,
                  cand_atr: Optional[list[str]] = None,
                  cand_rst: Optional[list[str]] = None) -> str:
    """
    같은 장소가 2번 이상 나오면 후보 풀에서 교체하고,
    실패 시 원문 유지. (식사 라벨 보존)
    """
    used = set()
    out = []

    if cand_atr is None or cand_rst is None:
        _atr, _rst = _build_candidate_pools(city, [], [], None, limit=30)
        cand_atr = cand_atr or _atr
        cand_rst = cand_rst or _rst
    cand_atr = list(dict.fromkeys(cand_atr or []))
    cand_rst = list(dict.fromkeys(cand_rst or []))



    def _take_from_pool(pool: list[str]) -> Optional[str]:
        while pool:
            cand = pool.pop(0)
            ck = _strip_meal_prefix(cand).lower()
            if ck and ck not in used:
                return cand
        return None

    for line in (detail or "").splitlines():
        m = _TS_RE.match(line)
        if not m:
            out.append(line); continue
        span, rest = m.groups()
        core_raw = rest.split("(")[0].strip()
        core = _strip_meal_prefix(core_raw)
        key = re.sub(r"\s+", " ", core.lower())
        meal_label = None
        if re.search(r"(아침|브런치)", rest): meal_label = "아침"
        elif re.search(r"(점심|런치)", rest):  meal_label = "점심"
        elif re.search(r"(저녁|디너)", rest):  meal_label = "저녁"

        if key in used:
            picked = _take_from_pool(cand_rst[:] if meal_label else cand_atr[:])
            if picked:
                addr = _addr_for(city, picked)
                prefix = (meal_label + ": ") if meal_label else ""
                out.append(f"{span} {prefix}{picked}" + (f" ({addr})" if addr else ""))
                used.add(_strip_meal_prefix(picked).lower())
            else:
                out.append(line)
        else:
            used.add(key)
            out.append(line)
    return "\n".join(out).strip()

def dedupe_time_and_place(detail: str) -> str:
    """
    날짜별로 동일한 (시간범위 + 장소핵심명) 중복 라인을 제거.
    """
    lines = (detail or "").splitlines()
    out: list[str] = []
    seen: set[Tuple[str, str]] = set()

    def normalize_name(rest: str) -> str:
        core = rest.split("(")[0]
        core = _strip_meal_prefix(core)
        return re.sub(r"\s+", " ", core).strip().lower()

    def reset_day():
        seen.clear()

    for ln in lines:
        if re.match(r"^\s*\d{4}-\d{2}-\d{2}\s*\(.*\)\s*$", ln.strip()):
            out.append(ln)
            reset_day()
            continue
        m = _TS_RE.match(ln)
        if not m:
            out.append(ln); continue
        span, rest = m.groups()
        key = (span, normalize_name(rest))
        if key in seen:
            # 중복 → 스킵
            continue
        seen.add(key)
        out.append(ln)
    return "\n".join(out).strip()

# ========= 비용 추정/부착 =========
_PRICE_KEYS_CANDIDATES = [
    "avg_price", "average_price", "menu_avg_price", "menu_price",
    "price", "price_range", "ticket_price", "ticket", "entry_fee",
    "admission", "admission_fee", "adult_price", "pay", "fee"
]
_PRICE_LEVEL_MAP = {  # ₩ 표시가 있을 때 대략 값
    "₩": 9000, "₩₩": 17000, "₩₩₩": 32000, "₩₩₩₩": 55000
}

def _first_int_in_text(s: str) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)\s*원?", str(s))
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except Exception:
        return None

def _price_from_info(info: dict) -> Optional[int]:
    if not info:
        return None
    for k in ("price_level", "priceLevel", "price_symbol", "priceSymbol"):
        v = info.get(k)
        if isinstance(v, str):
            v = v.strip()
            if v in _PRICE_LEVEL_MAP:
                return _PRICE_LEVEL_MAP[v]
    for k in _PRICE_KEYS_CANDIDATES:
        if k in info and info[k]:
            v = info[k]
            if isinstance(v, (int, float)) and v > 0:
                return int(v)
            if isinstance(v, str):
                n = _first_int_in_text(v)
                if n is not None:
                    return n
    for k in ("desc", "description", "summary", "snippet"):
        n = _first_int_in_text(info.get(k) or "")
        if n:
            return n
    return None

def _guess_meal_from_line(line: str) -> Optional[str]:
    # 1) 텍스트 라벨 우선
    if re.search(r"(아침|브런치)", line): return "breakfast"
    if re.search(r"(점심|런치)", line):   return "lunch"
    if re.search(r"(저녁|디너)", line):   return "dinner"
    # 2) 시간대로 판정
    m = re.search(r"(\d{2}):(\d{2})\s*~\s*(\d{2}):(\d{2})", line)
    if m:
        sh, sm, eh, em = map(int, m.groups())
        start = sh * 60 + sm
        if 7*60   <= start <= 10*60+30: return "breakfast"
        if 11*60  <= start <= 14*60+30: return "lunch"
        if 17*60  <= start <= 21*60+30: return "dinner"
    return None

def _guess_category_from_line(line: str) -> str:
    if re.search(r"(카페|커피|디저트|베이커리|티하우스)", line): return "cafe"
    if re.search(r"(사우나|온천|스파|찜질방)", line): return "spa"
    if re.search(r"(박물관|미술관|전시)", line): return "museum"
    if re.search(r"(아쿠아리움|수족관|타워|랜드|월드|파크|케이블카|스카이워크|전망대)", line): return "theme"
    return "sight"

def _fallback_price(line: str) -> int:
    meal = _guess_meal_from_line(line)
    if meal == "breakfast": return 10000
    if meal == "lunch":     return 14000
    if meal == "dinner":    return 18000
    cat = _guess_category_from_line(line)
    if cat == "cafe":   return 7000
    if cat == "spa":    return 15000
    if cat == "museum": return 5000
    if cat == "theme":  return 25000
    return 0

def _place_core_from_line(line: str) -> tuple[Optional[str], Optional[str]]:
    m = _TS_RE.match(line)
    if not m:
        return None, None
    span, rest = m.groups()
    core = _strip_meal_prefix(rest.split("(")[0].strip())
    return span, (core or None)

_PRICE_CACHE: dict[str, int] = {}

def ensure_costs_per_line(detail: str, city: str, budget: Optional[int] = None) -> str:
    """각 활동 라인 끝에 (약 xx,xxx원)을 실제 데이터 기반으로 부착. 없으면 합리적 기본값."""
    if not detail:
        return detail
    lines = detail.splitlines()
    for i, ln in enumerate(lines):
        if not _TIME_RE.search(ln):
            continue
        if line_has_cost(ln):
            continue  # 이미 비용 있음

        _, core = _place_core_from_line(ln)
        price: Optional[int] = None
        if core:
            key = f"{city}|{core}".lower()
            if key in _PRICE_CACHE:
                price = _PRICE_CACHE[key]
            else:
                info = _best_place(city, core)
                price = _price_from_info(info)
                if price is None and _naver_ok():
                    try:
                        kind = "restaurant" if _guess_meal_from_line(ln) else None
                        kwargs = dict(query=f"{city} {core}", limit=8, sort="review_desc")
                        rows = search_and_rank_places(**kwargs) or []
                        if kind is not None:
                            try:
                                rows = search_and_rank_places(kind=kind, **kwargs) or []
                            except TypeError:
                                pass
                        for it in rows or []:
                            price = _price_from_info(it)
                            if price: break
                    except Exception:
                        price = None
                if price is not None:
                    _PRICE_CACHE[key] = price
        if price is None:
            price = _fallback_price(ln)
        lines[i] = ln.rstrip() + f" (약 {price:,}원)"
    return "\n".join(lines).strip()

# ========= 설문에서 고른 장소 임시 저장소 =========
from threading import Lock
_SELECTIONS: dict[str, dict[str, list[str]]] = {}
_SEL_LOCK = Lock()

def _norm_dest_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"(특별자치도|특별자치시|광역시|특별시|자치구|도|시|군|구)$", "", s)
    return s or "_"

def _extend_unique(dst_list: list[str], items: list[str]) -> None:
    seen = {x.lower() for x in dst_list}
    for p in items or []:
        pn = re.sub(r"\s+", " ", (p or "").strip())
        if pn and pn.lower() not in seen:
            dst_list.append(pn)
            seen.add(pn.lower())

def _remember_selected(destination: str, places: list[str], category: Optional[str] = None) -> None:
    dest_key = _norm_dest_key(destination)
    cat = (category or "mixed").lower()
    if cat not in ("attraction", "restaurant", "mixed"):
        cat = "mixed"
    with _SEL_LOCK:
        bucket = _SELECTIONS.setdefault(dest_key, {"attraction": [], "restaurant": [], "mixed": []})
        _extend_unique(bucket[cat], places)

def _get_selected(destination: str, categories: Optional[list[str]] = None) -> list[str]:
    dest_key = _norm_dest_key(destination)
    cats = categories or ["attraction", "restaurant", "mixed"]
    with _SEL_LOCK:
        buckets = []
        if dest_key in _SELECTIONS:
            buckets.append(_SELECTIONS[dest_key])
        for k, b in _SELECTIONS.items():
            if k == dest_key:
                continue
            if k in dest_key or dest_key in k:
                buckets.append(b)
        out: list[str] = []
        seen: set[str] = set()
        for b in buckets:
            for c in cats:
                for p in b.get(c, []) or []:
                    pn = re.sub(r"\s+", " ", (p or "").strip())
                    key = pn.lower()
                    if pn and key not in seen:
                        out.append(pn)
                        seen.add(key)
        return out

# ========= 스키마 =========
class ScheduleRequest(BaseModel):
    location: str
    days: int
    style: str
    companions: List[str] = []
    budget: int
    selected_places: List[str] = []
    travel_date: str
    count: int = 1

class ScheduleItem(BaseModel):
    title: str
    detail: str

class ScheduleResponse(BaseModel):
    schedules: List[ScheduleItem]
    base_point: Optional[Tuple[float, float]] = None
    items: Optional[List[ScheduleItem]] = None

class RecommendRequest(BaseModel):
    destination: str
    dates: List[str] = Field(default_factory=list)
    companions: List[str] = Field(default_factory=list)
    styles: List[str] = Field(default_factory=list)
    hasPet: bool = False
    budget: Optional[int] = None
    selected_places: List[str] = Field(default_factory=list)
    sort: str = "review_desc"
    base_point: Optional[Tuple[float, float]] = None
    query: Optional[str] = None
    food_categories: List[str] = Field(default_factory=list)

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

class SelectedPlacesRequest(BaseModel):
    destination: str
    places: List[str] = Field(default_factory=list)
    category: Optional[str] = None  # "attraction" | "restaurant" | None(혼합)

class SelectedPlacesResponse(BaseModel):
    ok: bool = True
    destination: str
    saved_count: int
    places: List[str]
    gpt_note: Optional[str] = None

class FoodRequest(BaseModel):
    destination: str
    cuisine: str
    sort: str = "review"          # "review" | "rating" | "distance"
    limit: int = 12
    companions: List[str] = []
    styles: List[str] = []
    hasPet: bool = False
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None

# 데모 일정 목록
mock_schedules = [
    {"id": 1, "title": "제주도 여행", "dates": "2025.08.10 ~ 08.12"},
    {"id": 2, "title": "부산 가족여행", "dates": "2025.08.15 ~ 08.17"},
    {"id": 3, "title": "서울 데이트 코스", "dates": "2025.09.01"},
]

# ========= 파싱/백업 유틸 =========
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
            f"09:30 ~ 12:00 {location} 주요명소 A (약 0원)",
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

# ========= /api/plan =========
@app.post("/api/plan", response_model=ScheduleResponse)
def create_plan(req: ScheduleRequest):
    try:
        try:
            stored_selected = _get_selected(req.location)
        except Exception:
            stored_selected = []
        # ✅ 항상 초기화
        selected_union = list(dict.fromkeys([*(req.selected_places or []), *stored_selected]))

        try:
            raw = generate_schedule_gpt(
                location=req.location,
                days=req.days,
                style=req.style,
                companions=req.companions,
                budget=req.budget,
                selected_places=selected_union,
                travel_date=req.travel_date,
                count=req.count,
            ) or ""
        except Exception as e:
            print("[/api/plan] generate_schedule_gpt ERROR:", e)
            raw = ""

        raw = _normalize_gpt_text(raw)
        sections = _ensure_three(_extract_sections(raw), req)

        start_dt = datetime.strptime(req.travel_date, "%Y-%m-%d").date()
        full_dates, short_dates = expected_date_strings(start_dt, req.days)

        schedules: List[ScheduleItem] = []
        base_point: Optional[Tuple[float, float]] = None
        first_point_locked = False

        for i, (title, body) in enumerate(sections):
            detail = (body or "").strip()

            # (0) 날짜 강제 보강
            detail = ensure_all_days(detail, full_dates, req.location)

            # (1) 날짜 누락 보정 시도(선택)
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

            # (1.5) 보정 실패 대비 재보강
            detail = ensure_all_days(detail, full_dates, req.location)
            detail = fix_header_order(detail)  

            # (2) 선택 장소 1회 주입 + 랜덤 보강
            try:
                saved_attractions = _get_selected(req.location, ["attraction", "mixed"]) or []
                saved_restaurants = _get_selected(req.location, ["restaurant"]) or []
                attractions_for_inject = list(dict.fromkeys([*(req.selected_places or []), *saved_attractions]))
                restaurants_for_inject = list(dict.fromkeys(saved_restaurants))

                styles_list = []
                for t in re.split(r"[,\s/]+", (req.style or "")):
                    t = t.strip()
                    if t: styles_list.append(t)

                detail = inject_selected_once_and_fill(
                    detail=detail,
                    city=req.location,
                    styles=styles_list,
                    companions=req.companions or [],
                    budget=req.budget,
                    selected_attractions=attractions_for_inject,
                    selected_restaurants=restaurants_for_inject,
                )
            except Exception as _e:
                print("[inject once+fill error]", _e)

                        # (3) 플레이스홀더 줄 실제 상호/주소로 치환 + 품질 보강
            if _naver_ok():
                for line in (detail.splitlines() or []):
                    if line_looks_like_placeholder(line) and not (line_has_address(line) or line_has_cost(line)):
                        detail = detail.replace(line, _replace_line_with_real_place(line, req.location))
                detail = verify_and_enrich_block(detail, req.location)

            # (3.5) 날짜 헤더 ↔ 시간 라인 뒤집힘 교정  ← ★추가
            detail = fix_header_time_swaps(detail)

            # (4) 중복 장소 교체(가능하면 후보 풀로)   ← 후보 풀 없으면 그냥 넘어감
            try:
                detail = dedupe_places(detail, req.location)
            except Exception:
                pass

            # (5) 동일 장소 중복 라인 제거(일정 전체 기준) ← ★추가
            detail = dedupe_time_and_place(detail)

            # (6) 각 활동 라인 끝에 (약 xx,xxx원) 보강
            detail = ensure_costs_per_line(detail, req.location, req.budget)

            # (7) 총비용 문구 제거 → 재계산 후 1회만 표기
            detail = re.sub(r"총 예상 비용.*?원\W*", "", detail)
            cost = parse_total_cost(detail)
            detail += f"\n\n총 예상 비용은 약 {cost:,}원으로, 입력 예산인 {req.budget:,}원 내에서 잘 계획되었어요."

            schedules.append(ScheduleItem(title=title, detail=detail))

            # (8) base_point 추출(첫 일정 첫 장소의 좌표)
            if (not first_point_locked) and i == 0:
                for line in detail.splitlines():
                    m = re.search(r"\b\d{2}:\d{2}\s*~\s*\d{2}:\d{2}\s*([^(]+)", line)
                    if not m:
                        continue
                    place_name = m.group(1).strip()
                    sp = _search_place_safe(f"{req.location} {place_name}") or {}
                    try:
                        lat, lng = float(sp.get("lat")), float(sp.get("lng"))
                        base_point = (lat, lng)
                        first_point_locked = True
                    except Exception:
                        pass
                    break

        print(f"[/api/plan] schedules={len(schedules)}")
        return ScheduleResponse(schedules=schedules, base_point=base_point, items=schedules)

    except Exception as e:
        print("[/api/plan][FATAL]", e)
        traceback.print_exc()
        fallback: List[ScheduleItem] = []
        for i in range(max(1, req.count or 1)):
            title = f"일정추천 {i+1}: {req.location} {req.days}일 샘플"
            body = _build_sample_itinerary(req.location, req.travel_date, req.days, title)
            cost = parse_total_cost(body)
            body += f"\n\n총 예상 비용은 약 {cost:,}원으로, 입력 예산인 {req.budget:,}원 내에서 잘 계획되었어요."
            fallback.append(ScheduleItem(title=title, detail=body))
        print(f"[/api/plan] Fallback used, schedules={len(fallback)}")
        return ScheduleResponse(schedules=fallback, base_point=None, items=fallback)

# ========= 끼니 슬롯 보강(옵션) =========
_MEAL_SPANS = [
    ("아침",  r"08:\d{2}\s*~\s*09:\d{2}", "08:00 ~ 09:30 아침"),
    ("점심",  r"12:\d{2}\s*~\s*13:\d{2}", "12:00 ~ 13:30 점심"),
    ("저녁",  r"19:\d{2}\s*~\s*20:\d{2}", "19:00 ~ 20:30 저녁"),
]
def ensure_meal_slots(detail: str) -> str:
    lines = detail.splitlines()
    date_idx = [i for i, ln in enumerate(lines) if re.match(r"^\d{4}-\d{2}-\d{2}\s*\(.*\)", ln.strip())]
    if not date_idx:
        return detail
    for k in range(len(date_idx)):
        start = date_idx[k]
        end = date_idx[k+1] if k+1 < len(date_idx) else len(lines)
        block = lines[start:end]
        txt = "\n".join(block)
        changed = False
        for label, rx, default_line in _MEAL_SPANS:
            if not re.search(rx, txt):
                if "아침" in label:
                    block.insert(1, default_line)
                else:
                    block.append(default_line)
                changed = True
        if changed:
            lines[start:end] = block
    return "\n".join(lines)

# ========= 관광지 추천 =========
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
                count=1,
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

# ========= 선택 저장 =========
@app.post("/api/selection/places", response_model=SelectedPlacesResponse)
def save_selected_places(req: SelectedPlacesRequest):
    uniq: list[str] = []
    seen = set()
    for p in (req.places or []):
        name = re.sub(r"\s+", " ", (p or "").strip())
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(name)
    _remember_selected(req.destination, uniq, req.category)
    current_all = _get_selected(req.destination)
    return SelectedPlacesResponse(
        ok=True,
        destination=req.destination,
        saved_count=len(uniq),
        places=current_all,
        gpt_note=None,
    )

# ========= 음식점 추천 (GPT 추출 기반) =========
def _want_category(name: str, cat_str: str, wanted: list[str]) -> bool:
    """원하는 카테고리 필터(간단). wanted가 비면 모두 통과."""
    if not wanted:
        return True
    base = f"{name} {cat_str}".lower()
    return any(w.lower() in base for w in wanted)

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
                count=1,
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

        wanted = list(dict.fromkeys(req.food_categories or []))
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
    try:
        sort_map = {
            "review": "review_desc", "review_desc": "review_desc",
            "rating": "rating_desc", "rating_desc": "rating_desc",
            "distance": "distance_asc", "distance_asc": "distance_asc",
        }
        req.sort = sort_map.get((req.sort or "review_desc"), "review_desc")

        prompt = generate_schedule_gpt(
            location=req.destination,
            days=len(req.dates) if req.dates else 3,
            style=", ".join(req.styles) if req.styles else "자유 여행",
            companions=", ".join(req.companions) if req.companions else "없음",
            budget=req.budget or 0,
            selected_places=req.selected_places,
            travel_date=req.dates[0] if req.dates else str(date.today()),
            count=1,
        )
        gpt_text = ask_gpt_safe(prompt, req.destination)
        sightseeing, restaurants = extract_places(gpt_text or "")

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

        if not places:
            try:
                norm_sort = sort_map.get((req.sort or "review_desc"), "review_desc")
                kw = " ".join([req.destination or "", "관광지", *req.styles]).strip()
                sr = search_and_rank_places(query=kw, limit=20, sort=norm_sort) or []
                out: List[Place] = []
                for it in sr:
                    try:
                        out.append(Place(
                            name=it.get("name") or it.get("title") or it.get("place_name") or "이름 미상",
                            category=it.get("category") or it.get("category_name") or "관광지",
                            address=it.get("address") or it.get("road_address") or it.get("addr"),
                            rating=it.get("rating"),
                            review_count=it.get("review_count") or it.get("userRatingTotal"),
                            naver_url=it.get("naver_url") or it.get("map_link") or it.get("url") or it.get("link"),
                            image_url=it.get("image_url") or it.get("image"),
                            distance_km=it.get("distance_km"),
                            score=it.get("score"),
                            reviews=[]
                        ))
                    except Exception:
                        continue
                if out:
                    return RecommendResponse(places=out)
            except Exception:
                pass
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
# === 일정 수정 이후 품질 보정 + 비용 재계산 ===
def _postprocess_itinerary(text: str, fallback_city: Optional[str], budget: Optional[int]) -> str:
    t = (text or "").strip()
    city = (fallback_city or _guess_city_from_itinerary(t) or "").strip()

    # 헤더↔시간 줄 뒤집힘 교정
    try:
        t = fix_header_time_swaps(t)
    except Exception:
        pass

    # 중복 장소 교체/제거
    try:
        if city:
            t = dedupe_places(t, city)
    except Exception:
        pass
    try:
        t = dedupe_time_and_place(t)
    except Exception:
        pass

    # 각 활동 라인 비용 보강
    try:
        if city:
            t = ensure_costs_per_line(t, city, budget)
    except Exception:
        pass

    # 총액 문구는 항상 1회만
    t = re.sub(r"총 예상 비용.*?원\W*", "", t)
    total = parse_total_cost(t)
    if budget is not None:
        t += f"\n\n총 예상 비용은 약 {total:,}원으로, 입력 예산인 {budget:,}원 기준으로 조정했어요."
    else:
        t += f"\n\n총 예상 비용은 약 {total:,}원으로 조정했어요."
    return t

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
def chat_edit(req: "ChatRequest"):
    original = (req.itineraryText or "").strip()
    # 예산(있으면 int로)
    try:
        budget_ctx = (req.context or {}).get("budget", None)
        budget_val = None if budget_ctx in (None, "", "알 수 없음") else int(str(budget_ctx).replace(",", ""))
    except Exception:
        budget_val = None

    # 1) 규칙 기반: 'A 빼고 B 넣어/바꿔/대신' 우선 시도
    rule_reply: Optional[str] = None
    rule_text: Optional[str]  = None
    try:
        rep = _apply_place_replacements(original, req.message, budget=budget_val)
        if rep:
            rule_reply, rule_text = rep  # (reply, new_text)
    except Exception:
        rule_reply, rule_text = None, None

    # 2) 보조 규칙: '저녁 가볍게', '시작시간 X시' 등
    if rule_text is None:
        try:
            r2_reply, r2_text = _edit_itinerary_rules(original, req.message)
            rule_reply, rule_text = r2_reply, r2_text
        except Exception:
            rule_reply, rule_text = "요청을 반영했습니다.", original

    # LLM이 아예 없으면 규칙 결과 + 후처리로 반환
    if client is None:
        post = _postprocess_itinerary(rule_text or original, _guess_city_from_itinerary(original), budget_val)
        return ChatResponse(reply=rule_reply or "수정했습니다.", updatedItinerary=post)

    # 3) LLM 시도 (JSON 강제) — 실패 시 규칙 결과 사용
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
            response_format={"type": "json_object"},
        )
        content = (out.choices[0].message.content or "").strip()
        data = json.loads(content)
        llm_reply = (data.get("reply") or "").strip() or (rule_reply or "수정했습니다.")
        updated = (data.get("updated_itinerary") or "").strip()

        # LLM이 수정 못했으면 규칙 결과 사용
        final_text = updated if updated else (rule_text or original)

        # 후처리(형식 보존 + 비용/총액 재계산)
        final_text = _postprocess_itinerary(final_text, _guess_city_from_itinerary(original), budget_val)
        return ChatResponse(reply=llm_reply, updatedItinerary=final_text)

    except Exception as e:
        # LLM 에러 시 규칙 결과 후처리
        post = _postprocess_itinerary(rule_text or original, _guess_city_from_itinerary(original), budget_val)
        return ChatResponse(reply=f"{rule_reply or '수정했습니다.'} (모델 오류: {e})", updatedItinerary=post)

# ========= 유연 입력용(프론트 호환) =========
@app.post("/api/recommend/places_flex")
def recommend_places_flex(req: dict = Body(...)):
    def _s(x):
        return str(x).strip() if x is not None else ""
    def _as_list(x):
        if not x:
            return []
        if isinstance(x, list):
            return [_s(i) for i in x if _s(i)]
        s = _s(x)
        return [s] if s else []
    def _to_int(x):
        try:
            s = str(x).replace(",", "").strip()
            return int(s) if s != "" else None
        except Exception:
            return None

    location   = _s(req.get("location") or req.get("destination"))
    styles     = _as_list(req.get("styles"))
    companions = _as_list(req.get("companions"))
    has_pet    = bool(req.get("has_pet") or req.get("hasPet") or False)
    start_date = _s(req.get("start_date") or req.get("startDate") or "")
    end_date   = _s(req.get("end_date") or req.get("endDate") or "")
    budget     = _to_int(req.get("budget"))
    sort_map = {
        "review": "review_desc", "review_desc": "review_desc",
        "rating": "rating_desc", "rating_desc": "rating_desc",
        "distance": "distance_asc", "distance_asc": "distance_asc",
    }
    sort  = sort_map.get(_s(req.get("sort") or "review_desc"), "review_desc")
    try:
        limit = int(req.get("limit") or 20)
    except Exception:
        limit = 20

    STYLE_HINTS = {
        "SNS": ["핫플", "포토스팟", "인스타", "뷰맛집", "전망대"],
        "핫플": ["핫플", "포토스팟", "인스타"],
        "자연": ["자연", "호수", "숲길", "해변", "산책"],
        "힐링": ["힐링", "온천", "스파", "정원", "산책"],
        "역사": ["유적지", "박물관", "고궁", "전시"],
        "체험": ["체험", "공방", "액티비티"],
        "맛집": ["맛집", "현지 맛집"],
    }
    COMP_HINTS = {
        "가족": ["아이와", "키즈", "체험", "박물관"],
        "아이": ["아이와", "키즈"],
        "친구": ["포토스팟", "핫플"],
        "연인": ["야경", "전망대", "산책"],
        "부모님": ["사찰", "정원", "유적지", "한옥"],
    }

    queries: list[str] = []
    base = [location, "관광지"] if location else ["관광지"]
    queries.append(" ".join(base))
    for st in styles:
        for key, hints in STYLE_HINTS.items():
            if key in st or st in key:
                for h in hints:
                    queries.append(" ".join([location, h] if location else [h]))
    for cp in companions:
        for key, hints in COMP_HINTS.items():
            if key in cp or cp in key:
                for h in hints:
                    queries.append(" ".join([location, h] if location else [h]))
    if has_pet:
        for kw in ["애견동반", "반려견 동반", "애완견 동반"]:
            queries.append(" ".join([location, kw] if location else [kw]))
    if budget is not None and budget <= 100000:
        for kw in ["무료", "저렴", "산책"]:
            queries.append(" ".join([location, kw] if location else [kw]))

    if start_date:
        try:
            m = int(start_date.split("-")[1])
            season_kw = "벚꽃" if m in (3,4) else "여름" if m in (7,8) else "가을" if m in (9,10) else None
            if season_kw:
                queries.append(" ".join([location, season_kw] if location else [season_kw]))
        except Exception:
            pass

    seen_q = set()
    qlist = []
    for q in queries:
        q = " ".join([t for t in (q or "").split() if t])
        if q and q not in seen_q:
            seen_q.add(q)
            qlist.append(q)
        if len(qlist) >= 10:
            break

    results = []
    name_addr_seen = set()
    def _key(p: dict) -> str:
        n = (p.get("name") or p.get("title") or p.get("place_name") or "").strip()
        a = (p.get("address") or p.get("road_address") or p.get("addr") or "").strip()
        return f"{n}|{a}"

    try:
        for q in qlist:
            items = search_and_rank_places(query=q, limit=limit, sort=sort) or []
            for it in items:
                k = _key(it)
                if not k or k in name_addr_seen:
                    continue
                name_addr_seen.add(k)
                results.append(it)
            if len(results) >= limit * 2:
                break
    except Exception as e:
        print("[/api/recommend/places_flex] error:", e)

    if len(results) == 0 and location:
        try:
            items = search_and_rank_places(query=f"{location} 관광지", limit=limit, sort=sort) or []
            for it in items:
                k = _key(it)
                if k and k not in name_addr_seen:
                    name_addr_seen.add(k)
                    results.append(it)
        except Exception:
            pass

    results = results[:limit]
    return {"total": len(results), "places": results}

# ========= 네이버 지도 기반 음식점 추천 =========
def _cuisine_query(cuisine: str) -> str:
    m = {
        "한식": "한식",
        "양식": "양식 서양식 이탈리안 스테이크 파스타",
        "중식": "중식 중국집 마라탕 마라샹궈 딤섬",
        "일식": "일식 스시 라멘 우동 돈카츠",
        "카페": "카페 디저트 베이커리 커피",
        "패스트푸드": "패스트푸드 분식 치킨 피자 버거 샌드위치",
    }
    key = (cuisine or "").strip()
    return m.get(key, key)

@app.post("/api/food/recommend")
def api_food_recommend(req: FoodRequest):
    sort_key = {
        "review": "review_desc",
        "rating": "rating_desc",
        "distance": "distance_asc",
    }.get((req.sort or "review").lower(), "review_desc")

    terms = list(dict.fromkeys((_cuisine_query(req.cuisine) or req.cuisine or "").split()))
    if not terms:
        terms = [req.cuisine or "맛집"]

    collected: list[dict] = []
    seen: Set[Tuple[str, str]] = set()

    def add_rows(rows: list[dict]):
        for it in rows or []:
            name = (it.get("name") or it.get("title") or it.get("place_name") or "").strip()
            addr = (it.get("address") or it.get("road_address") or it.get("addr") or "").strip()
            if not name:
                continue
            key = (name, addr)
            if key in seen:
                continue
            seen.add(key)
            collected.append(it)

    for t in terms:
        q = f"{req.destination} {t} 맛집"
        try:
            rows = search_and_rank_places(
                query=q,
                limit=max(10, req.limit),
                sort=sort_key,
                center_lat=req.center_lat,
                center_lng=req.center_lng,
                kind="restaurant",
            ) or []
        except TypeError:
            rows = search_and_rank_places(query=q, limit=max(10, req.limit), sort=sort_key) or []
        add_rows(rows)
        if len(collected) >= req.limit * 2:
            break

    if not collected:
        try:
            rows = search_and_rank_places(
                query=f"{req.destination} 맛집",
                limit=max(20, req.limit),
                sort=sort_key,
            ) or []
            add_rows(rows)
        except Exception:
            pass

    def _normalize(p: Dict) -> Dict:
        name = p.get("name") or p.get("title") or ""
        rating = p.get("rating") or p.get("score") or p.get("star_score") or None
        reviews = p.get("review_count") or p.get("reviews") or p.get("blog_review_count") or 0
        addr = p.get("address") or p.get("roadAddress") or p.get("addr") or ""
        img = p.get("image_url") or p.get("image") or None
        phone = p.get("phone") or p.get("tel") or ""
        dist = p.get("distance_km")
        link = p.get("map_url") or (naver_map_link(name) if name else "")
        cat = p.get("category") or p.get("category_name") or ""
        return {
            "name": name,
            "rating": rating,
            "review_count": reviews,
            "address": addr,
            "image_url": img,
            "phone": phone,
            "map_url": link,
            "category": cat,
            "distance_km": dist
        }

    items = [_normalize(p) for p in collected]

    if req.sort == "rating":
        items.sort(key=lambda x: (x["rating"] or 0, x["review_count"] or 0), reverse=True)
    elif req.sort == "distance":
        items.sort(key=lambda x: (9999 if x.get("distance_km") is None else x["distance_km"]))
    else:
        items.sort(key=lambda x: (x["review_count"] or 0, x["rating"] or 0), reverse=True)

    return {"count": len(items[:req.limit]), "items": items[:req.limit]}

# ========= 자유 대화(여행 추천 전용) =========
class TalkMessage(BaseModel):
    role: str
    content: str

class TalkRequest(BaseModel):
    system: Optional[str] = None
    messages: List[TalkMessage] = Field(default_factory=list)
    destination: Optional[str] = None       # ✅ 선택: 지역명(예: "경주")
    limit: Optional[int] = 5                 # ✅ 선택: 추천 개수

class TalkResponse(BaseModel):
    reply: str

# ---- 여행 의도/키워드 판별 ----
_RE_INTENT_REST = re.compile(r"(맛집|식당|먹을|음식|카페|디저트|술집|바|포장|배달)", re.I)
_RE_INTENT_ATTR = re.compile(r"(관광지|명소|여행지|볼거리|코스|코스로|체험|액티비티|공원|전시|박물관|미술관|사찰|유적|야경)", re.I)
_RE_COUNT       = re.compile(r"(?:top|탑)?\s*(\d{1,2})\s*(?:곳|개|명소|식당|집)", re.I)

# 자주 쓰는 도시(간단 추론용)
_COMMON_CITIES = [
    "서울","부산","대구","인천","광주","대전","울산","세종",
    "제주","서귀포","경주","강릉","속초","춘천","양양","원주",
    "여수","순천","목포","전주","포항","통영","거제","창원",
    "천안","청주","수원","성남","용인","고양"
]
_RE_LOC_SUFFIX = re.compile(r"([가-힣A-Za-z]{2,10})(?:특별시|광역시|자치시|자치도|도|시|군|구)\b")

# 간단한 음식/관광 키워드 → 검색어 보조
CUISINE_MAP = {
    "한식":"한식", "중식":"중식 중국집", "양식":"양식 이탈리안 파스타 스테이크",
    "일식":"일식 스시 라멘 돈카츠", "카페":"카페 디저트 베이커리", "분식":"분식",
    "회":"회 물회", "물회":"물회", "국밥":"국밥", "막국수":"막국수", "초밥":"스시 초밥",
    "삼겹살":"삼겹살 고기집", "치킨":"치킨", "피자":"피자", "버거":"버거 햄버거"
}
SIGHT_MAP = {
    "사찰":"사찰 절", "박물관":"박물관 전시", "미술관":"미술관 전시",
    "전망대":"전망대 타워", "공원":"공원 산책", "야경":"야경 야경명소",
    "해변":"해변 바다 바닷가", "케이블카":"케이블카", "스카이워크":"스카이워크",
    "온천":"온천 스파", "체험":"체험 액티비티", "포토스팟":"포토스팟 인스타 핫플"
}

def _infer_destination_from_text(text: str) -> str:
    # 접미사(서울시/경주시…) 우선
    m = _RE_LOC_SUFFIX.search(text or "")
    if m:
        return re.sub(r"(특별시|광역시|자치시|자치도|도|시|군|구)$", "", m.group(1))
    # 일반 도시명
    for c in _COMMON_CITIES:
        if c in (text or ""):
            return c
    return ""

def _detect_intent(text: str) -> Optional[str]:
    if _RE_INTENT_REST.search(text or ""):
        return "restaurant"
    if _RE_INTENT_ATTR.search(text or ""):
        return "attraction"
    return None

def _extract_limit(text: str, default_n: int) -> int:
    m = _RE_COUNT.search(text or "")
    if m:
        try:
            n = int(m.group(1))
            return max(1, min(15, n))
        except:
            pass
    return default_n

def _uniq_name_addr(rows: list[dict]) -> list[dict]:
    seen = set(); out = []
    for it in rows or []:
        n = (it.get("name") or it.get("title") or it.get("place_name") or "").strip()
        a = (it.get("address") or it.get("road_address") or it.get("addr") or "").strip()
        k = f"{n}|{a}"
        if n and k not in seen:
            seen.add(k); out.append(it)
    return out

def _pick_keywords(text: str, mapping: dict) -> list[str]:
    found = []
    for k, v in mapping.items():
        if k in (text or ""):
            found.append(v)
    return found[:3]  # 너무 많으면 과도 호출

@app.post("/api/talk", response_model=TalkResponse)
def api_talk(req: TalkRequest):
    """
    자유 대화: 지역별 관광지/맛집 추천 특화.
    - intent/지역/키워드 추출 후 search_and_rank_places로 실제 상호 추천
    - 그 외 일반 대화는 LLM로 답변
    """
    # 대화 텍스트 합치기(최근 사용자 발화 위주)
    user_texts = [m.content for m in (req.messages or []) if m.role == "user" and (m.content or "").strip()]
    last_user  = (user_texts[-1] if user_texts else "").strip()

    # 의도/지역/개수 추출
    intent = _detect_intent(" ".join(user_texts))
    dest   = (req.destination or "").strip() or _infer_destination_from_text(" ".join(user_texts))
    limit  = _extract_limit(" ".join(user_texts), req.limit or 5)

    # ---- 여행 추천 루트 ----
    if intent in ("restaurant", "attraction"):
        if not dest:
            return TalkResponse(reply="어느 지역을 원하시는지 알려주세요! 예: “경주 물회 맛집 5곳 추천” 또는 “부산 관광지 추천”")

        results: list[dict] = []
        try:
            if intent == "restaurant":
                kws = _pick_keywords(" ".join(user_texts), CUISINE_MAP) or ["맛집"]
                # 키워드별로 모아서 중복 제거
                for kw in kws:
                    try:
                        rows = search_and_rank_places(
                            query=f"{dest} {kw}",
                            limit=max(10, limit),
                            sort="review_desc",
                            kind="restaurant",  # naver_api가 지원하면 사용
                        ) or []
                    except TypeError:
                        rows = search_and_rank_places(query=f"{dest} {kw}", limit=max(10, limit), sort="review_desc") or []
                    results += rows
                results = _uniq_name_addr(results)[:limit]

                if not results:
                    # 마지막 폴백
                    rows = search_and_rank_places(query=f"{dest} 맛집", limit=max(10, limit), sort="review_desc") or []
                    results = _uniq_name_addr(rows)[:limit]

                # 답안 구성
                lines = []
                for i, it in enumerate(results, 1):
                    name = it.get("name") or it.get("title") or "이름 미상"
                    addr = it.get("address") or it.get("road_address") or it.get("addr") or ""
                    rating = it.get("rating") or it.get("score") or None
                    reviews = it.get("review_count") or it.get("userRatingTotal") or None
                    link = it.get("map_url") or generate_naver_map_url(name, dest, addr)
                    meta = []
                    if rating:  meta.append(f"★{rating}")
                    if reviews: meta.append(f"리뷰 {reviews:,}개")
                    meta_txt = (" · ".join(meta)) if meta else ""
                    lines.append(f"{i}. {name} – {addr}{(' · '+meta_txt) if meta_txt else ''}\n   {link}")
                head = f"🍽 {dest} 맛집 추천 {len(lines)}곳"
                return TalkResponse(reply=head + "\n" + "\n".join(lines))

            else:  # attraction
                kws = _pick_keywords(" ".join(user_texts), SIGHT_MAP) or ["관광지", "명소"]
                for kw in kws:
                    rows = search_and_rank_places(query=f"{dest} {kw}", limit=max(10, limit), sort="review_desc") or []
                    results += rows
                results = _uniq_name_addr(results)[:limit]

                if not results:
                    rows = search_and_rank_places(query=f"{dest} 관광지", limit=max(10, limit), sort="review_desc") or []
                    results = _uniq_name_addr(rows)[:limit]

                lines = []
                for i, it in enumerate(results, 1):
                    name = it.get("name") or it.get("title") or "이름 미상"
                    addr = it.get("address") or it.get("road_address") or it.get("addr") or ""
                    rating = it.get("rating") or it.get("score") or None
                    reviews = it.get("review_count") or it.get("userRatingTotal") or None
                    link = it.get("map_url") or generate_naver_map_url(name, dest, addr)
                    meta = []
                    if rating:  meta.append(f"★{rating}")
                    if reviews: meta.append(f"리뷰 {reviews:,}개")
                    meta_txt = (" · ".join(meta)) if meta else ""
                    lines.append(f"{i}. {name} – {addr}{(' · '+meta_txt) if meta_txt else ''}\n   {link}")
                head = f"📍 {dest} 관광지 추천 {len(lines)}곳"
                return TalkResponse(reply=head + "\n" + "\n".join(lines))

        except Exception as e:
            # 추천 파이프라인 실패 → LLM 폴백
            print("[/api/talk] travel route error:", e)

    # ---- 일반 대화 루트(LLM) ----
    system_prompt = (
        req.system
        or "너는 한국어 여행 도우미다. 사용자가 지역·취향을 말하면 이에 맞춰 친절하고 실용적으로 답한다."
    ).strip()

    msgs: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for m in (req.messages or []):
        role = m.role if m.role in ("system","user","assistant") else "user"
        content = (m.content or "").strip()
        if content: msgs.append({"role": role, "content": content})

    if client is None:
        return TalkResponse(reply=f"(데모 응답) '{last_user}' 질문을 이해했어요. 모델 연결 후 자세히 도와드릴게요.")

    try:
        out = client.chat.completions.create(model="gpt-4o-mini", messages=msgs, temperature=0.3)
        reply = (out.choices[0].message.content or "").strip()
        return TalkResponse(reply=reply or "(응답 없음)")
    except Exception as e:
        return TalkResponse(reply=f"(서버 오류) {e}")
