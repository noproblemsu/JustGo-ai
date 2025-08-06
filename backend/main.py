import streamlit as st
import time
from datetime import date, timedelta
from gpt_client import generate_schedule_gpt

# ✅ 외부 스타일 적용
with open("../frontend/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.title("🌏 JustGo 여행플래너")

# ✅ 사용자 입력 받기
destination = st.selectbox("어디로 여행 가시나요?", [
    "강릉", "경주", "광주", "대구", "대전", "부산", "서울", "속초", "여수",
    "울산", "인천", "전주", "제주도", "직접 입력"
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
    st.error("🚨 종료일은 시작일보다 같거나 이후여야 해요.")
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
if "schedules" not in st.session_state:
    st.session_state.schedules = []
if "selected_schedule" not in st.session_state:
    st.session_state.selected_schedule = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ✅ 일정 추천 받기 버튼
if st.button("일정 추천 받기"):
    companions = []
    if with_friends: companions.append("친구")
    if with_family: companions.append("가족")

    with st.spinner("GPT가 3개의 서로 다른 여행 일정을 생성 중입니다..."):
        result = generate_schedule_gpt(
            location=destination,
            days=days,
            style=travel_type,
            companions=companions,
            budget=budget,
            selected_places=selected_places,
            travel_date=str(start_date),
            count=3  # GPT에게 3개 요청
        )
        st.session_state.schedules = result.split("\n\n")  # 일정 A, B, C로 분리
        st.session_state.selected_schedule = None

# ✅ 일정 선택 화면
if st.session_state.schedules and not st.session_state.selected_schedule:
    st.subheader("🗓️ 아래 일정 중 하나를 선택하세요!")
    for i, schedule in enumerate(st.session_state.schedules):
        with st.expander(f"일정 {chr(65+i)} 보기"):
            st.markdown(schedule, unsafe_allow_html=True)
        if st.button(f"✅ 일정 {chr(65+i)} 선택", key=f"select_{i}"):
            st.session_state.selected_schedule = schedule
            st.session_state.chat_history = [
                {"role": "system", "content": "너는 여행 일정 전문가야. 아래 일정에 대해 사용자의 수정 요청에 응답해줘."},
                {"role": "user", "content": f"기존 일정:\n{schedule}"}
            ]
            st.rerun()
    if st.button("🔄 마음에 드는 게 없어요. 다시 추천받기"):
        st.session_state.schedules = []
        st.rerun()

# ✅ 선택된 일정 → 수정 요청 인터페이스
if st.session_state.selected_schedule:
    st.subheader("✏️ 일정 수정 요청하기")

    for chat in st.session_state.chat_history:
        role = chat["role"]
        bubble_class = "chat-bubble-user" if role == "user" else "chat-bubble-assistant"
        st.markdown(f'<div class="{bubble_class}">{chat["content"]}</div>', unsafe_allow_html=True)

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
