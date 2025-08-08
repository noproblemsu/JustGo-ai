import streamlit as st
import time
import re
from datetime import date, timedelta
from gpt_client import generate_schedule_gpt

# ✅ 외부 스타일 적용 (frontend/style.css)
with open("../frontend/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("\U0001F30F JustGo 여행플래너")

# ✅ 여행지 입력
destination = st.selectbox("어디로 여행 가시나요?", [
    "강릉", "경주", "광주", "대구", "대전", "부산", "서울",
    "속초", "여수", "울산", "인천", "전주", "제주도", "직접 입력"
])
if destination == "직접 입력":
    destination = st.text_input("여행지를 직접 입력해주세요")

# ✅ 날짜 입력
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("여행 시작일", value=date.today())
with col2:
    end_date = st.date_input("여행 종료일", value=date.today() + timedelta(days=2))

days = (end_date - start_date).days + 1
if days < 1:
    st.error("⚠️ 종료일은 시작일보다 같거나 이후여야 해요.")
    st.stop()

# ✅ 예산과 스타일
budget = st.number_input("여행 예산 (원)", min_value=10000, step=10000, value=300000)
travel_type = st.selectbox("여행 스타일을 선택하세요", ["휴식 중심", "액티비티 중심", "맛집 탐방", "역사 탐방"])

# ✅ 추가 옵션
with st.expander("추가 옵션"):
    with_friends = st.checkbox("친구랑 함께")
    with_family = st.checkbox("가족과 함께")
    selected_places = st.text_area(
        "방문하고 싶은 장소 (관광지나 맛집 등)",
        placeholder="예: 불국사, 황리단길, 경주월드 등"
    ).split(',')

# ✅ 세션 상태 초기화
if "schedule_result" not in st.session_state:
    st.session_state.schedule_result = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ✅ 일정 생성 버튼 클릭 시
if st.button("일정 추천 받기"):
    companions = []
    if with_friends: companions.append("친구")
    if with_family: companions.append("가족")

    st.success(f"{destination}에서 {start_date}부터 {end_date}까지 '{travel_type}' 여행 일정을 준비 중이에요!")

    with st.spinner("AI가 여행 일정을 생성 중입니다..."):
        result = generate_schedule_gpt(
            location=destination,
            days=days,
            style=travel_type,
            companions=companions,
            budget=budget,
            selected_places=selected_places,
            travel_date=start_date,  # 날짜 그대로 넘김
            count=3
        )

       raw_blocks = re.split(r"(?=일정추천\s*\d+:)", result.strip())
unique_titles = set()
cleaned_schedules = []

for block in raw_blocks:
    lines = block.strip().split("\n", 1)
    if len(lines) < 2:
        continue
    title = lines[0].strip()
    detail = lines[1].strip()

    if title not in unique_titles:
        unique_titles.add(title)
        cleaned_schedules.append((title, detail))

st.session_state.schedule_result = cleaned_schedules

        full_result_for_gpt = "\n\n".join([f"{title}\n{detail}" for title, detail in cleaned_schedules])
        st.session_state.chat_history = [
            {"role": "system", "content": "너는 여행 일정 전문가야. 아래 일정에 대해 사용자의 수정 요청에 응답해줘."},
            {"role": "user", "content": f"기존 일정:\n{full_result_for_gpt}"}
        ]
        time.sleep(1)

# ✅ 일정 출력 (카드 토글 방식 적용)
if st.session_state.schedule_result:
    st.subheader("\U0001F4C5 추천 일정")

    for title, detail in st.session_state.schedule_result:
        with st.expander(title):
            st.markdown(f'<div class="chat-bubble-assistant">{detail}</div>', unsafe_allow_html=True)

    st.subheader("✏️ 일정 수정 요청하기")

    for chat in st.session_state.chat_history:
        role = chat["role"]
        content = chat["content"]
        if role == "user":
            st.markdown(f'<div class="chat-bubble-user">{content}</div>', unsafe_allow_html=True)
        elif role == "assistant":
            st.markdown(f'<div class="chat-bubble-assistant">{content}</div>', unsafe_allow_html=True)

    user_msg = st.chat_input("수정하고 싶은 내용을 입력하세요!")

    if user_msg:
        st.markdown(f'<div class="chat-bubble-user">{user_msg}</div>', unsafe_allow_html=True)
        st.session_state.chat_history.append({"role": "user", "content": user_msg})

        from gpt_client import client
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=st.session_state.chat_history
            )
            ai_msg = response.choices[0].message.content
            st.markdown(f'<div class="chat-bubble-assistant">{ai_msg}</div>', unsafe_allow_html=True)
            st.session_state.chat_history.append({"role": "assistant", "content": ai_msg})
        except Exception as e:
            st.error(f"⚠️ 에러 발생: {e}")
