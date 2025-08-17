# backend/prompts.py
from __future__ import annotations
from datetime import datetime, date, timedelta
from typing import List, Union
from textwrap import dedent

def build_prompt(
    location: str,
    days: Union[int, str],
    budget: Union[int, str],
    companions: Union[List[str], str, None],
    style: Union[List[str], str, None],
    selected_places: Union[List[str], None],
    travel_date: Union[str, date, datetime],
    count: int = 1,
) -> str:
    # ---- 입력 정리 ----
    days = int(days)
    budget = int(str(budget).replace(",", "").strip())

    if companions is None:
        companions = []
    if isinstance(companions, str):
        companions = [companions]
    companions = [c for c in companions if str(c).strip()]
    comp_str = ", ".join(companions) if companions else "없음"

    if style is None:
        style = []
    if isinstance(style, str):
        style = [style]
    styles = [s for s in style if str(s).strip()]
    style_str = ", ".join(styles) if styles else "자유 여행"

    sel = [str(p).strip() for p in (selected_places or []) if str(p).strip()]
    sel_str = "\n".join(f"- {p}" for p in sel) if sel else "없음"

    # 날짜 처리
    if isinstance(travel_date, str):
        start_dt = datetime.strptime(travel_date.strip(), "%Y-%m-%d")
    elif isinstance(travel_date, date) and not isinstance(travel_date, datetime):
        start_dt = datetime.combine(travel_date, datetime.min.time())
    else:
        start_dt = travel_date if isinstance(travel_date, datetime) else datetime.today()

    date_list = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d (%a)") for i in range(days)]
    date_only = [d.split(" ")[0] for d in date_list]  # YYYY-MM-DD
    date_lines = "\n".join(f"- {d}" for d in date_list)

    # ---- 프롬프트 ----
    return dedent(f"""
    너는 여행 일정 전문가다. 아래의 **하드 규칙**을 100% 준수하며 **{count}개의 서로 다른 일정안**을 한 번에 작성하라.
    출력은 **순수 텍스트**만 사용한다. (마크다운/코드블록/표/불릿 금지)

    [입력]
    - 여행지: {location}
    - 여행일수: {days}일
    - 여행 시작일: {date_list[0]}
    - 동반자: {comp_str}
    - 여행 스타일: {style_str}
    - 총 예산: {budget:,}원
    - 사용자 선택 장소(있으면 '각각 1회만' 반영):
    {sel_str}
    - 날짜 전체:
    {date_lines}

    [상위 제목 형식]
    각 일정안은 다음 제목으로 시작한다(번호 필수).
    - 일정추천 1: {location} {days}일 코스
    - 일정추천 2: {location} {days}일 코스
    ... (요청 개수만큼)
    각 일정안 사이는 **한 줄에 '---'** 만 넣어 구분한다.

    [하드 규칙]
    1) 날짜 헤더
       - 각 날짜는 헤더로 시작: "YYYY-MM-DD (DayN)"
       - 모든 날짜 헤더가 반드시 본문에 존재해야 한다: {", ".join(date_only)}
       - 헤더 아래에 바로 시간 라인이 이어지고, 헤더/시간 순서를 절대 바꾸지 말 것.

    2) 하루 슬롯(정확히 5줄, 시간 오름차순 고정)
       08:00 ~ 09:30 아침: <상호명> (<도로명 주소>) (약 <원>)
       09:30 ~ 12:00 <관광/명소 상호명> (<도로명 주소>) (약 <원>)
       12:00 ~ 13:30 점심: <상호명> (<도로명 주소>) (약 <원>)
       14:00 ~ 18:00 <관광/명소 상호명> (<도로명 주소>) (약 <원>)
       19:00 ~ 20:30 저녁: <상호명> (<도로명 주소>) (약 <원>)
       - 위 5개 시간대는 **모든 날짜에서 반드시 그대로 사용**한다(시간 겹침 금지).

    3) 플레이스홀더 금지
       - "주요명소/관광지/체험/카페/휴식" 같은 추상어만 쓰지 말 것.
       - 각 라인은 **실제 상호명 + '도로명 주소'**를 괄호로 적는다.
         예) "부산현대미술관 (부산광역시 강서구 낙동남로 1191)"

    4) 장소 중복 금지(한 일정안 전체 기준)
       - 같은 '핵심명'(괄호 앞 이름에서 '아침/점심/저녁/브런치/런치/디너' 같은 라벨 제거 후)을
         **그 일정안 전체에서 단 한 번만** 사용한다(다른 날이라도 중복 금지).
       - 체인점은 지점까지 포함해 핵심명을 구분한다(예: "OO커피 부산역점"과 "OO커피 서면점"은 다른 곳).
       - 사용자가 지정한 장소가 있으면 **각각 정확히 1회만** 배치한다.

    5) 비용 표기
       - **모든 시간 라인 끝**에 " (약 xx,xxx원)" 형식으로 비용을 표기한다(무료면 0원 표기).
       - **총 예상 비용 문구는 일정안 맨 마지막에 1회만** 작성한다.
       - 총액은 입력 예산의 **±15%** 범위 내에서 합리적으로 배분한다.
       - 총비용은 활동별 비용의 합과 일치해야 한다.

    6) 동선은 합리적으로(과도한 왕복/이동 금지), 실내·실외 균형.

    [출력 형식 스켈레톤(예시)]
    일정추천 1: {location} {days}일 코스

    {date_list[0]} (Day1)
    08:00 ~ 09:30 아침: <상호명> (<도로명 주소>) (약 <원>)
    09:30 ~ 12:00 <명소 상호명> (<도로명 주소>) (약 <원>)
    12:00 ~ 13:30 점심: <상호명> (<도로명 주소>) (약 <원>)
    14:00 ~ 18:00 <명소 상호명> (<도로명 주소>) (약 <원>)
    19:00 ~ 20:30 저녁: <상호명> (<도로명 주소>) (약 <원>)

    ---
    (다음 일정안도 같은 형식으로 이어서 작성)

    [내부 검증 체크리스트(모델이 스스로 확인 후 위반 시 수정할 것)]
    - 모든 날짜 헤더가 존재하는가? 헤더 바로 아래에 시간 라인이 왔는가?
    - 모든 날짜가 정확히 5개의 시간대 라인을 갖고, 시간이 오름차순인가?
    - 플레이스홀더 없이 모든 라인이 실제 상호+도로명 주소를 갖는가?
    - '핵심명'이 그 일정안 전체에서 단 한 번씩만 등장하는가? (중복이면 다른 실제 장소로 교체)
    - 총비용 문구가 맨 끝에 1회만 있고, 활동비 합과 일치하는가?
    """).strip()
