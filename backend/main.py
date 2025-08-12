import streamlit as st
import time
import re
from datetime import date, timedelta, datetime
from gpt_client import generate_schedule_gpt, client
from naver_api import search_and_rank_places, search_place  # ✅ 네이버 기반

# ✅ 외부 스타일 적용
with open("../frontend/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("🌍 JustGo 여행플래너")

# ✅ 입력 UI
destination = st.selectbox("어디로 여행 가시나요?", [
    "강릉", "경주", "광주", "대구", "대전", "부산", "서울",
    "속초", "여수", "울산", "인천", "전주", "제주도", "직접 입력"
])
if destination == "직접 입력":
    destination = st.text_input("여행지를 직접 입력해주세요")

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("여행 시작일", value=date.today())
with col2:
    end_date = st.date_input("여행 종료일", value=date.today() + timedelta(days=2))

days = (end_date - start_date).days + 1
if days < 1:
    st.error("⚠️ 종료일은 시작일보다 같거나 이후여야 해요.")
    st.stop()

budget = st.number_input("여행 예산 (원)", min_value=10000, step=10000, value=300000)
travel_type = st.selectbox("여행 스타일을 선택하세요", ["휴식 중심", "액티비티 중심", "맛집 탐방", "역사 탐방"])

with st.expander("추가 옵션"):
    with_friends = st.checkbox("친구랑 함께")
    with_family = st.checkbox("가족과 함께")
    selected_places = st.text_area(
        "방문하고 싶은 장소 (관광지나 맛집 등)",
        placeholder="예: 불국사, 황리단길, 경주월드 등"
    ).split(',')

# ✅ 세션 상태
if "schedule_result" not in st.session_state: st.session_state.schedule_result = []
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "last_point" not in st.session_state:   st.session_state.last_point = None  # (lat, lng)

# ✅ 유틸
def parse_total_cost(text: str) -> int:
    prices = re.findall(r'약\s*([\d,]+)원', text)
    return sum(int(p.replace(',', '')) for p in prices)

def expected_date_strings(start: date, num_days: int):
    # "YYYY-MM-DD (Tue)" 형태와 "YYYY-MM-DD" 둘 다 체크
    dts = [(datetime.combine(start, datetime.min.time()) + timedelta(days=i)) for i in range(num_days)]
    full = [dt.strftime("%Y-%m-%d (%a)") for dt in dts]
    short = [dt.strftime("%Y-%m-%d") for dt in dts]
    return full, short

def block_has_all_dates(block_text: str, full_dates: list[str], short_dates: list[str]) -> bool:
    return all((fd in block_text) or (sd in block_text) for fd, sd in zip(full_dates, short_dates))

def repair_block_with_missing_dates(block_text: str, missing_dates: list[str]) -> str:
    """날짜가 누락된 일정 블록을 한 번 더 요청해서 보완."""
    try:
        messages = [
            {"role": "system", "content":
             "너는 여행 일정 전문가야. 반드시 모든 날짜(아침/점심/저녁 포함)를 작성하고, "
             "실제 존재하는 상호명과 도로명 주소를 포함하며, 총 예상비용은 마지막에만 1회 작성한다."},
            {"role": "user", "content":
             "아래 일정 블록에서 일부 날짜가 누락되었습니다. 누락된 날짜를 포함해서 동일 형식으로 다시 작성하세요.\n\n"
             f"[누락된 날짜]: {', '.join(missing_dates)}\n\n[기존 블록]\n{block_text}"}
        ]
        resp = client.chat.completions.create(
            model="gpt-4o-mini",  # 사용 모델에 맞게 조정
            messages=messages,
            temperature=0.3
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # 실패 시 원문 유지
        return block_text

# ✅ 일정 생성
if st.button("일정 추천 받기"):
    companions = []
    if with_friends: companions.append("친구")
    if with_family: companions.append("가족")

    st.success(f"{destination}에서 {start_date}부터 {end_date}까지 '{travel_type}' 여행 일정을 준비 중이에요!")

    full_dates, short_dates = expected_date_strings(start_date, days)

    with st.spinner("AI가 여행 일정을 생성 중입니다..."):
        result = generate_schedule_gpt(
            location=destination, days=days, style=travel_type,
            companions=companions, budget=budget,
            selected_places=selected_places, travel_date=str(start_date), count=3
        )

        # 일정 추천 분리
        raw_blocks = re.split(r"(?:---)?\s*일정추천\s*\d+:", result.strip())
        titles = re.findall(r"(일정추천\s*\d+:\s*[^\n]+)", result.strip())
        cleaned_schedules = []

        # ✅ 첫 일정의 첫 장소 → 좌표 자동 추출
        first_place_locked = False

        for i, block in enumerate(raw_blocks[1:]):
            title = titles[i] if i < len(titles) else f"일정추천 {i+1}"
            detail = block.strip()

            # --- 날짜 검증 & 1회 보정 ---
            if not block_has_all_dates(detail, full_dates, short_dates):
                missing = [sd for fd, sd in zip(full_dates, short_dates)
                           if (fd not in detail) and (sd not in detail)]
                detail = repair_block_with_missing_dates(detail, missing)

            # 총비용 문구 제거 후 재계산
            detail = re.sub(r"총 예상 비용.*?원\W*", "", detail)
            cost = parse_total_cost(detail)
            detail += f"\n\n총 예상 비용은 약 {cost:,}원으로, 입력 예산인 {budget:,}원 내에서 잘 계획되었어요."
            cleaned_schedules.append((title, detail))

            # 🔎 첫 일정(추천1)에서 '시간 패턴' 줄에서 장소 추출 → 좌표 저장
            if not first_place_locked and i == 0:
                for line in detail.splitlines():
                    m = re.search(r"\b\d{2}:\d{2}\s*~\s*\d{2}:\d{2}\s*([^(]+)", line)
                    if m:
                        query_name = m.group(1).strip()
                        sp = search_place(f"{destination} {query_name}")
                        if sp and sp.get("lat") and sp.get("lng"):
                            try:
                                st.session_state.last_point = (float(sp["lat"]), float(sp["lng"]))
                                first_place_locked = True
                            except Exception:
                                pass
                        break

        st.session_state.schedule_result = cleaned_schedules
        full_text = "\n\n".join([f"{t}\n{d}" for t, d in cleaned_schedules])

        st.session_state.chat_history = [
            {"role": "system", "content": "너는 여행 일정 전문가야. 아래 일정에 대해 사용자의 수정 요청에 응답해줘."},
            {"role": "user", "content": f"기존 일정:\n{full_text}"}
        ]
        time.sleep(0.5)

# ✅ 일정 출력 & 수정
if st.session_state.schedule_result:
    st.subheader("📅 추천 일정")
    for title, detail in st.session_state.schedule_result:
        with st.expander(title):
            st.markdown(f'<div class="chat-bubble-assistant">{detail}</div>', unsafe_allow_html=True)

    st.subheader("✏️ 일정 수정 요청하기")
    for chat in st.session_state.chat_history:
        style = "chat-bubble-user" if chat["role"] == "user" else "chat-bubble-assistant"
        st.markdown(f'<div class="{style}">{chat["content"]}</div>', unsafe_allow_html=True)

    user_msg = st.chat_input("수정하고 싶은 내용을 입력하세요!")
    if user_msg:
        st.markdown(f'<div class="chat-bubble-user">{user_msg}</div>', unsafe_allow_html=True)
        st.session_state.chat_history.append({"role": "user", "content": user_msg})

        # 🧭 맛집/관광지 요청은 네이버 지역검색 사용 (없는 장소 금지)
        need_place = any(k in user_msg for k in
            ["맛집","식당","카페","관광지","명소","여행지","점심","저녁","아침","브런치","조식",
             "일식","한식","중식","양식","초밥","라멘","파스타","고기","해산물"]
        )
        if need_place:
            try:
                base = st.session_state.last_point
                if base is None:
                    sp_city = search_place(destination)  # 도시 대표 지점 시도
                    base = (float(sp_city["lat"]), float(sp_city["lng"])) if sp_city else (37.5665, 126.9780)

                with st.spinner("네이버에서 주변 후보 검색 중..."):
                    ranked = search_and_rank_places(base[0], base[1], f"{destination} {user_msg}", max_distance_km=5.0)

                if ranked:
                    top = ranked[0]
                    reply = f"**추천:** [{top['name']}]({top['naver_url']}) · {top['distance_km']}km\n주소: {top['address']}"
                    if len(ranked) > 1:
                        reply += "\n\n**다른 후보:**\n" + "\n".join(
                            [f"- [{x['name']}]({x['naver_url']}) · {x['distance_km']}km" for x in ranked[1:5]]
                        )
                    st.markdown(f'<div class="chat-bubble-assistant">{reply}</div>', unsafe_allow_html=True)
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})
                else:
                    st.info("주변에서 조건에 맞는 후보를 찾지 못했어요. 반경을 넓혀볼까요?")
            except Exception as e:
                st.error(f"네이버 검색 오류: {e}")
        else:
            # 일반 일정 수정은 GPT 처리
            try:
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=st.session_state.chat_history,
                    temperature=0.5
                )
                ai_msg = response.choices[0].message.content
                st.markdown(f'<div class="chat-bubble-assistant">{ai_msg}</div>', unsafe_allow_html=True)
                st.session_state.chat_history.append({"role": "assistant", "content": ai_msg})
            except Exception as e:
                st.error(f"⚠️ 에러 발생: {e}")
