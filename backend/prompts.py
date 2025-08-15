from datetime import datetime, date, timedelta
from typing import List, Union


def build_prompt(
    location: str,
    days: Union[int, str],
    budget: Union[int, str],
    companions: Union[List[str], str, None],
    style: str,
    selected_places: Union[List[str], None],
    travel_date: Union[str, date, datetime],
    count: int = 1,
) -> str:
    # ---- 입력값 정리 ----
    days = int(days)
    budget = int(budget)

    if companions is None:
        companions = []
    elif isinstance(companions, str):
        companions = [companions]
    companion_str = ", ".join([c for c in companions if str(c).strip()]) or "없음"

    selected_places = selected_places or []
    selected_str = "\n".join(
        [f"- {str(place).strip()}" for place in selected_places if str(place).strip()]
    ) or "없음"

    # travel_date -> datetime 보정
    if isinstance(travel_date, str):
        start_dt = datetime.strptime(travel_date.strip(), "%Y-%m-%d")
    elif isinstance(travel_date, date) and not isinstance(travel_date, datetime):
        start_dt = datetime.combine(travel_date, datetime.min.time())
    else:
        start_dt = travel_date
    if not isinstance(start_dt, datetime):
        start_dt = datetime.today()

    # 날짜 리스트
    date_list = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d (%a)") for i in range(days)]
    date_only = [d.split(" ")[0] for d in date_list]  # YYYY-MM-DD만
    date_str = "\n".join([f"- {d}" for d in date_list])

    # ---- 프롬프트 본문 ----
    return f"""
너는 여행 일정 전문 플래너야.

여행지는 {location}이고, 여행 기간은 총 {days}일이야.
여행 날짜는 다음과 같아:
{date_str}

각 날짜는 요일이 함께 포함되어 있고, **각 날짜마다 아침, 점심, 저녁 일정**을 모두 구성해줘.

여행 예산은 {budget:,}원이야.
동반자는 {companion_str}이고, 여행 스타일은 '{style}'이야.

아래는 사용자가 선호하는 장소 목록이야:
{selected_str}

다만 사용자가 선택한 장소가 부족하거나 많을 경우, 적절히 추가하거나 줄여도 괜찮아.

---

### ✅ 반드시 지켜야 할 일정 작성 규칙

1. 각 날짜는 **아침, 점심, 저녁 3개의 활동**으로 구성할 것.
2. 각 날짜는 반드시 아래 형식으로 구분해:
   - `YYYY-MM-DD (요일)` 제목 형태로 날짜를 명시할 것 (예: `2025-08-08 (Fri)`)
2-1. **아래 날짜들이 모두 본문에 반드시 등장**해야 함: {", ".join(date_only)}
     한 날짜라도 빠지면 **전체 답변을 다시 작성**할 것.
3. 각 활동에는 다음 항목이 필수야:
   - 활동 시간 (예: `09:00~10:30`)
   - 활동 설명
   - 예상 소요 시간 (예: 약 1시간 30분)
   - 예상 비용 (예: 약 15,000원)
   예시: `09:00~10:30 불국사 관람 (경북 경주시 불국로 385, 약 1시간 30분, 약 3,000원)`
4. 일정은 **동선 고려**, 자동차로 **1시간 이내 거리**로 무리하지 않게 구성할 것.
4-1. **총 예상 비용은 해당 일정추천의 모든 날짜별 예상 비용을 합산한 값**이어야 함.
4-2. 일정에 나오는 **모든 장소**는 실제 존재하는 구체적인 상호명과 **도로명 주소**를 반드시 포함할 것.
   - 예시: "속초맛집투어" 대신 `"속초 ○○횟집 (강원 속초시 중앙로 123)"` 처럼 작성.

5. ⚠️ **각 일정 추천 하나당 총 예상 비용은 반드시 예산의 ±15% 이내**여야 해.
   - 예산이 {budget:,}원이면, 각 일정별 총 비용은 반드시 **{int(budget*0.85):,}원 ~ {int(budget*1.15):,}원** 범위 내여야 해.
6. 날짜는 {days}일 **모두 빠짐없이** 작성해. **하루라도 누락되면 틀린 일정**이야.
7. 각 날짜 마지막에는 **간단한 마무리 문장**을 넣을 것.
8. 출력은 **마크다운 형식**으로 정리할 것.
9. ⚠️ **총 예상 비용은 일정 마지막에 단 1번만 작성**할 것.
   - 하루마다 쓰지 마. 오직 마지막에만 아래 형식으로 써:
   - `총 예상 비용은 약 289,000원으로, 입력 예산인 300,000원 내에서 잘 계획되었어요.`
11. 각 일정은 아래 형식으로 시작
    - 일정추천 1: 힐링중심
12. 일정 본문에는 `"일정추천"`이라는 단어를 다시 쓰지 마.
13. 출력 형식을 어기면 안 돼. 반드시 위 규칙을 모두 지켜.
"""
