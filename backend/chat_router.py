# backend/chat_router.py
from __future__ import annotations
import json, os
from typing import Optional, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
router = APIRouter(tags=["chat"])

class ChatRequest(BaseModel):
    message: str = Field(..., description="사용자 입력")
    itineraryIndex: int = Field(..., ge=0, description="선택 일정 인덱스(0-base)")
    itineraryText: Optional[str] = None
    context: Optional[Dict] = None  # {"budget": 300000} 등

class ChatResponse(BaseModel):
    reply: str
    updatedItinerary: Optional[str] = None

SYSTEM_KO = """너는 여행 일정 편집자다.
입력으로 현재 일정 마크다운과 사용자 수정요청을 받으면,
1) reply: 간단한 답변
2) updated_itinerary: 수정된 '전체 일정 마크다운'(필요할 때만)
을 포함한 JSON 문자열만 출력해.

규칙:
- 한국어
- 3일 일정(아침/점심/저녁) 형식 유지
- 총 예상 비용은 예산의 ±15% 범위 내에서 일정 마지막에 한 번만 표기
- 머리글 예시: '일정추천 N' 다음 줄에 --- 구분선
- JSON 외 추가 텍스트 금지 (키: reply, updated_itinerary)
"""

def _user_prompt(req: ChatRequest) -> str:
    budget = None
    if isinstance(req.context, dict):
        budget = req.context.get("budget")
    return (
        f"[선택 인덱스] {req.itineraryIndex}\n\n"
        f"[현재 일정]\n{req.itineraryText or '(없음)'}\n\n"
        f"[사용자 요청]\n{req.message}\n\n"
        f"[예산]\n{budget if budget is not None else '알 수 없음'}"
    )

@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message가 비어 있습니다.")

    messages = [
        {"role": "system", "content": SYSTEM_KO},
        {"role": "user", "content": _user_prompt(req)},
    ]
    try:
        out = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
        )
        content = out.choices[0].message.content or ""
        try:
            data = json.loads(content)
            reply = (data.get("reply") or "").strip() or "수정했습니다."
            updated = data.get("updated_itinerary")
            if isinstance(updated, str):
                updated = updated.strip() or None
            return ChatResponse(reply=reply, updatedItinerary=updated)
        except Exception:
            # 모델이 JSON 이외를 내보낸 예외 대응
            return ChatResponse(reply=content.strip() or "응답 해석 실패")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")
