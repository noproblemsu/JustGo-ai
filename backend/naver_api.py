# backend/naver_api.py
from __future__ import annotations

import os
import re
import time
import json
import math
import requests
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=(Path(__file__).resolve().parent / ".env"))
except Exception:
    pass

CID = os.getenv("NAVER_CLIENT_ID")
CSEC = os.getenv("NAVER_CLIENT_SECRET")

NAVER_LOCAL_URL = "https://openapi.naver.com/v1/search/local.json"
NAVER_IMAGE_URL = "https://openapi.naver.com/v1/search/image"
NAVER_BLOG_URL  = "https://openapi.naver.com/v1/search/blog.json"

DEFAULT_TIMEOUT = 8
USER_AGENT = "JustGo/1.0 (+https://example.com)"

# --- 간단 캐시 & 폴라이트 딜레이(429 예방) ---
_CACHE: dict[str, dict] = {}
_LAST_CALL_TS = 0.0
_COOLDOWN_SEC = 0.10  # API 사이 100ms 정도 텀

def _headers() -> Dict[str, str]:
    if not CID or not CSEC:
        raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET not set")
    return {
        "X-Naver-Client-Id": CID,
        "X-Naver-Client-Secret": CSEC,
        "User-Agent": USER_AGENT,
    }

def _wait_politely():
    global _LAST_CALL_TS
    now = time.time()
    if now - _LAST_CALL_TS < _COOLDOWN_SEC:
        time.sleep(_COOLDOWN_SEC - (now - _LAST_CALL_TS))
    _LAST_CALL_TS = time.time()

# ============== 공통 유틸 ==============
_TAG_RE = re.compile(r"</?b>")
_HTML_RE = re.compile(r"<[^>]+>")

def _strip_tags(s: str) -> str:
    return _TAG_RE.sub("", s or "").strip()

def _clean_html(s: str) -> str:
    return _HTML_RE.sub("", s or "").strip()

def _safe_get(d: dict, *keys, default=None):
    for k in keys:
        if d.get(k):
            return d[k]
    return default

def _dedupe_by_name(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        key = re.sub(r"\s+", " ", (it.get("name") or "").lower()).strip()
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out

def naver_map_link(name: str) -> str:
    return f"https://map.naver.com/v5/search/{quote(name)}"

# ============== 로컬 검색 ==============
def _search_local_raw(query: str, display: int = 10, start: int = 1) -> Dict:
    _wait_politely()
    try:
        r = requests.get(
            NAVER_LOCAL_URL,
            headers=_headers(),
            params={"query": query, "display": max(1, min(display, 30)), "start": max(1, start)},
            timeout=DEFAULT_TIMEOUT,
        )
        if r.status_code == 429:
            raise RuntimeError("NAVER 429 Rate limit")
        r.raise_for_status()
        return r.json()
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            raise RuntimeError("NAVER 429 Rate limit")
        raise
    except Exception:
        raise

def _map_local_item(it: Dict) -> Dict:
    # 네이버 로컬 응답 -> 표준 필드 매핑
    title = _strip_tags(_safe_get(it, "title", default="")).strip()
    addr = _safe_get(it, "roadAddress", "address", default="").strip()
    cat = (it.get("category") or "").strip()
    tel = (it.get("telephone") or "").strip()
    # v1 로컬은 위경도 직접 제공 안함(별도 좌표계 케이스는 생략)
    return {
        "name": title,
        "title": title,          # 호환
        "address": addr,
        "category": cat,
        "telephone": tel,
        "lat": None,
        "lng": None,
        "rating": None,          # 오픈 API에 없음
        "review_count": None,    # 오픈 API에 없음
        "map_link": naver_map_link(title) if title else None,
        "image_url": None,       # 이미지 URL 보강용
        "raw": it,
    }

def search_place(query: str) -> Dict:
    """
    단일 장소 추출(최상위 1개). 실패시 {}.
    """
    data = _search_local_raw(query, display=1, start=1)
    items = data.get("items", [])
    if not items:
        return {}
    return _map_local_item(items[0])

# ============== 블로그 수(= 리뷰수 프록시) ==============
def _blog_total(query: str) -> int:
    """
    네이버 블로그 검색 total 값을 리뷰 수 프록시로 사용.
    캐시 / 폴라이트 콜 적용.
    """
    key = f"blog_total::{query}"
    if key in _CACHE:
        return int(_CACHE[key]["total"])
    _wait_politely()
    try:
        r = requests.get(
            NAVER_BLOG_URL,
            headers=_headers(),
            params={"query": query, "display": 1, "start": 1, "sort": "sim"},
            timeout=DEFAULT_TIMEOUT,
        )
        if r.status_code == 429:
            raise RuntimeError("NAVER 429 Rate limit")
        r.raise_for_status()
        data = r.json() or {}
        total = int(data.get("total") or 0)
        _CACHE[key] = {"total": total, "ts": time.time()}
        return total
    except Exception:
        return 0

# ============== 이미지 검색(옵션) ==============
TRUSTED_IMAGE_HOSTS = (
    "blog.naver.com", "post.naver.com", "naver.net",
    "mp-seoul-image-production-s3.mangoplate.com", "img.siksinhot.com",
    "staticflickr.com", "pinimg.com",
)

def _host_ok(url: str, prefer_food: bool) -> bool:
    if not url:
        return False
    if any(h in url for h in TRUSTED_IMAGE_HOSTS):
        return True
    if prefer_food and re.search(r"(food|dish|menu|meal|plate|burger|pizza|sushi|ramen|pasta|bbq|korean)", url, re.I):
        return True
    return False

def search_image(query: str, prefer_food: bool = False, strict: bool = True) -> Optional[str]:
    """
    네이버 이미지 검색 상위 1~N에서 신뢰 호스트 우선 반환.
    실패/제한 시 None.
    """
    _wait_politely()
    try:
        r = requests.get(
            NAVER_IMAGE_URL,
            headers=_headers(),
            params={"query": query, "display": 15, "sort": "sim", "filter": "all"},
            timeout=DEFAULT_TIMEOUT,
        )
        if r.status_code == 429:
            raise RuntimeError("NAVER 429 Rate limit")
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [])
        for it in items:
            link = it.get("link") or it.get("thumbnail") or ""
            if _host_ok(link, prefer_food):
                return link
        if not strict and items:
            return items[0].get("link") or items[0].get("thumbnail")
        return None
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 429:
            raise RuntimeError("NAVER 429 Rate limit")
        return None
    except Exception:
        return None

# ====== 이미지 보강용 미니 캐시 & 헬퍼 ======
_IMG_CACHE: dict[str, str] = {}

def _image_for_place(name: str, address: Optional[str], category: Optional[str], prefer_food: bool=False) -> Optional[str]:
    """
    장소명(+주소 앞토막/카테고리)로 이미지 1장을 찾아서 URL을 반환.
    내부 캐시 사용, 신뢰 호스트 우선.
    """
    base = (name or "").strip()
    if not base:
        return None
    head_addr = (address or "").split()[0] if address else ""
    cat = (category or "").split(",")[0] if category else ""
    # 검색 후보를 구체도 높은 순으로 시도
    candidates = [
        f"{base} {head_addr} {cat}".strip(),
        f"{base} {head_addr}".strip(),
        f"{base} {cat}".strip(),
        base,
    ]
    for q in candidates:
        if not q:
            continue
        key = f"img::{q}::food={prefer_food}"
        if key in _IMG_CACHE:
            return _IMG_CACHE[key]
        url = search_image(q, prefer_food=prefer_food, strict=True)
        if url:
            _IMG_CACHE[key] = url
            return url
    # 마지막 폴백(엄격 X)
    for q in candidates:
        if not q:
            continue
        key = f"img_soft::{q}::food={prefer_food}"
        if key in _IMG_CACHE:
            return _IMG_CACHE[key]
        url = search_image(q, prefer_food=prefer_food, strict=False)
        if url:
            _IMG_CACHE[key] = url
            return url
    return None

# ============== 다건 검색 + 정렬 ==============
def _score_token_match(name: str, category: str, toks: List[str]) -> float:
    score = 0.0
    for t in toks:
        if t and t in name:
            score += 1.2
        if t and t in category:
            score += 0.7
    return score

def search_and_rank_places(query: str, limit: int = 20, sort: str = "review_desc") -> List[Dict]:
    """
    다건 검색 + 정렬.
    - 리뷰 많은 순: 네이버 블로그 total을 리뷰 수 프록시로 사용
    - 별점 높은 순: Local API가 별점을 주지 않으므로 리뷰 수/키워드 점수로 보조 정렬
    - 이미지: search_image()로 연관 이미지 보강 (신뢰 호스트 우선)
    """
    limit = max(1, min(int(limit or 20), 50))
    data = _search_local_raw(query, display=min(30, limit), start=1)
    items = [_map_local_item(it) for it in data.get("items", [])]

    items = _dedupe_by_name(items)

    toks = [t for t in query.split() if len(t) >= 2]
    for it in items:
        name = (it.get("name") or "")
        addr = (it.get("address") or "")
        cat  = (it.get("category") or "")
        # 키워드 적합도
        score = _score_token_match(name, cat, toks)
        if addr:
            score += 0.3
        it["score"] = score

        # 블로그 total을 "review_count" 프록시로 채움
        blog_q = f"{name} {addr.split()[0] if addr else ''}".strip() or name
        try:
            it["review_count"] = _blog_total(blog_q)
        except Exception:
            it["review_count"] = it.get("review_count") or 0

        # rating은 Local API에 없어 None 유지(후순위 키로 score 사용)
        it["rating"] = it.get("rating") or None

        # 네이버 지도 링크 보강(없으면 생성)
        if not it.get("map_link") and name:
            it["map_link"] = naver_map_link(name)

        # ✅ 이미지 보강
        if not it.get("image_url"):
            # 음식/카페류는 음식 사진 우선 탐색
            is_food = bool(re.search(r"(맛집|음식|식당|카페|디저트|베이커리|coffee|bakery)", cat, re.I))
            it["image_url"] = _image_for_place(name, addr, cat, prefer_food=is_food) or None

    s = (sort or "review_desc").strip()
    if s == "rating_desc":
        # rating 없음 → 리뷰/스코어 보조
        items.sort(key=lambda x: (x.get("rating") or 0.0,
                                  x.get("review_count") or 0,
                                  x.get("score") or 0.0),
                   reverse=True)
    elif s == "distance_asc":
        items.sort(key=lambda x: (x.get("distance_km") or 9e9, -(x.get("score") or 0.0)))
    else:
        # 기본: 리뷰 많은 순 (블로그 total 기반)
        items.sort(key=lambda x: (x.get("review_count") or 0,
                                  x.get("score") or 0.0),
                   reverse=True)

    return items[:limit]
