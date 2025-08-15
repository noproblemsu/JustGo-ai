# api_server.py (통합/호환/로깅/타임아웃)
from __future__ import annotations
from typing import List, Optional
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import time
import re
from datetime import datetime, date

# .env 로드 (루트 또는 이 파일 옆의 .env 선택)
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
# 필요하면 프로젝트 루트의 backend/.env도 같이 시도
load_dotenv(dotenv_path=Path(__file__).resolve().parent / "backend" / ".env")

app = FastAPI(title="JustGo API", version="1.0.0")

# --- CORS (Live Server / VSCode) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class PlanRequest(BaseModel):
    destination: str
    start_date: Optional[str] = None  # "YYYY-MM-DD"
    end_date: Optional[str] = None    # "YYYY-MM-DD"
    companions: List[str] = []
    styles: List[str] = []
    budget: Optional[int] = None
    has_pet: Optional[bool] = None

# --- Utils: '일정추천 1~3' 텍스트 분리 ---
_HEADING_RE = re.compile(
    r"(?im)^\s*일정\s*추천\s*(\d+)\b|^\s*일정추천\s*(\d+)\b"
)

def split_itineraries(full_text: str) -> List[str]:
    if not isinstance(full_text, str) or not full_text.strip():
        return []
    indices = [m.start() for m in _HEADING_RE.finditer(full_text)]
    if not indices:
        return [full_text.strip()]
    pieces: List[str] = []
    for i, start in enumerate(indices):
        end = indices[i + 1] if i + 1 < len(indices) else len(full_text)
        chunk = full_text[start:end].strip()
        if chunk:
            chunk = re.sub(r"\n?^ *[-—_]{3,} *\n?", "\n", chunk, flags=re.MULTILINE)
            pieces.append(chunk)
    return pieces[:3] if pieces else [full_text.strip()]

def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d").date()
    except Exception:
        return None

def _calc_days(sd: Optional[date], ed: Optional[date]) -> int:
    if sd and ed and ed >= sd:
        return (ed - sd).days + 1
    # fallback: 3일
    return 3

# --- GPT 호출을 별도 스레드에서 실행(블로킹 방지) ---
GPT_TIMEOUT_SEC = 20

async def _run_gpt_blocking(
    destination: str,
    start_date: Optional[str],
    end_date: Optional[str],
    budget: int,
    companions: List[str],
    styles: List[str],
    has_pet: bool,
) -> dict:
    def _blocking() -> dict:
        print("[GPT] blocking-start")
        # ── 의존 모듈 가져오기 (지연 import로 에러 메시지를 명확히)
        try:
            from gpt_client import generate_schedule_gpt
        except Exception as ie:
            raise RuntimeError(f"generate_schedule_gpt import 실패: {ie}")
        try:
            from gpt_places_recommender import ask_gpt, extract_places
        except Exception as ie:
            # 만약 파일명이 다르면 여기서 바꿔주세요.
            raise RuntimeError(f"ask_gpt/extract_places import 실패: {ie}")

        # 날짜/일수/스타일 정규화
        sd = _parse_date(start_date)
        ed = _parse_date(end_date)
        days = _calc_days(sd, ed)
        style = styles[0] if styles else "자유 여행"
        travel_date = sd.strftime("%Y-%m-%d") if sd else datetime.today().strftime("%Y-%m-%d")

        # 기존 generate_schedule_gpt 시그니처에 맞춰 전달
        # selected_places는 설문에서 받으면 넣고, 없으면 [] 유지
        prompt_text = generate_schedule_gpt(
            location=destination,
            days=days,
            style=style,
            companions=companions,
            budget=budget,
            selected_places=[],
            travel_date=travel_date,
            count=3,
        )

        # GPT에게 실제 답변 받기
        gpt_text = ask_gpt(prompt_text, destination)

        # 장소 추출은 실패해도 전체는 계속
        try:
            sightseeing, restaurants = extract_places(gpt_text)
        except Exception as pe:
            print("[GPT] parse-error:", pe)
            sightseeing, restaurants = [], []

        # 일정 1~3 분리
        itineraries = split_itineraries(gpt_text) or [
            "일정추천 1 생성에 실패했습니다. 다시 시도해주세요."
        ]

        print("[GPT] blocking-end")
        return {
            "ok": True,
            "dummy_result": {
                "destination": destination,
                "start": start_date,
                "end": end_date,
                "budget": budget,
                "styles": styles,
                "companions": companions,
                "has_pet": has_pet,
                "itineraries": itineraries,
                "sightseeing": sightseeing,
                "restaurants": restaurants,
            },
        }

    return await asyncio.to_thread(_blocking)

# --- 기본 엔드포인트 ---
@app.get("/")
def root():
    return {"message": "FastAPI 서버 정상 작동 중!"}

@app.get("/health")
def health():
    return {"status": "ok"}

# --- Core Endpoint (항상 응답 보장: 타임아웃/에러 처리) ---
@app.post("/api/plan")
async def create_plan(req: PlanRequest, request: Request):
    ts = time.time()
    print(f"[API] START /api/plan from {request.client.host} at {ts:.3f}")
    print("[API] req:", req.model_dump())

    # 기본값 보정
    destination = (req.destination or "").strip() or "부산"
    start_date = req.start_date
    end_date = req.end_date
    budget = req.budget if req.budget is not None else 300_000
    companions = req.companions or []
    styles = req.styles or []
    has_pet = bool(req.has_pet) if req.has_pet is not None else False

    try:
        result = await asyncio.wait_for(
            _run_gpt_blocking(
                destination, start_date, end_date, budget, companions, styles, has_pet
            ),
            timeout=GPT_TIMEOUT_SEC,
        )
        print(f"[API] END 200 in {(time.time()-ts):.3f}s")
        return result

    except asyncio.TimeoutError:
        print(f"[API] TIMEOUT in {(time.time()-ts):.3f}s")
        return {
            "ok": False,
            "message": f"GPT 처리 타임아웃({GPT_TIMEOUT_SEC}s)",
            "dummy_result": {
                "destination": destination,
                "start": start_date,
                "end": end_date,
                "budget": budget,
                "styles": styles,
                "companions": companions,
                "has_pet": has_pet,
                "itineraries": ["일정추천 1 샘플", "일정추천 2 샘플", "일정추천 3 샘플"],
                "sightseeing": [],
                "restaurants": [],
            },
        }
    except Exception as e:
        print(f"[API] ERROR {e} in {(time.time()-ts):.3f}s")
        return {
            "ok": False,
            "message": f"GPT 처리 실패: {e}",
            "dummy_result": {
                "destination": destination,
                "start": start_date,
                "end": end_date,
                "budget": budget,
                "styles": styles,
                "companions": companions,
                "has_pet": has_pet,
                "itineraries": ["일정추천 1 샘플", "일정추천 2 샘플", "일정추천 3 샘플"],
                "sightseeing": [],
                "restaurants": [],
            },
        }
