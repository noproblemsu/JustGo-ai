import streamlit as st
import time
from datetime import date, timedelta
import sys
import io

# 🔧 stdout 한글 인코딩 오류 방지용 설정 (Windows용)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from gpt_client import generate_schedule_gpt  # GPT 호출 함수

# ✅ 외부 스타일 적용 (frontend/style.css)
with open("../frontend/style.css", "r", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ✅ UI 구성
st.title("🌏 JustGo 여행플래너")

destination = st.selectbox("어디로 여행 가시나요?", 
    ["강릉", "경주", "광주", "대구", "대전", "부산", "서울", "속초", "여수", "울산", "인천", "전주", "제주도", "직접 입력"])

if destination == "직접 입력":
    destination = st.text_input("여행지를 직접 입력해주세요")

# ✅ 날짜 입력
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("여행 시작일", value=date.today())
with col2:
    end_date = st.date_input("여행 종료일", value=date.today() + timedelta(days=2))

# ✅ 여행일 수 계산
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

# ✅ 세션 상태 초기화
if "schedule_result" not in st.session_state:
    st.session_state.schedule_result = []
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ✅ GPT 일정 생성 버튼
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
            travel_date=str(start_date),
            count=3  # recommend 3 plans
        )
        st.session_state.schedule_result = result.split("---")
        st.session_state.chat_history = [
            {"role": "system", "content": "너는 여행 일정 전문가야. 아래 일정에 대해 사용자의 수정 요청에 응답해줘."},
            {"role": "user", "content": f"기존 일정:
{result}"}
        ]
        time.sleep(1)

# ✅ 일정 선택하기
if st.session_state.schedule_result:
    st.subheader("🗂️ 아래 일정 중 마음에 드는 것을 선택하세요")
    for i, plan in enumerate(st.session_state.schedule_result):
        with st.expander(f"✈️ 일정 {i+1}"):
            st.markdown(plan.strip())

    selected = st.radio("🧐 어떤 일정이 마음에 드시나요?", options=["일정 1", "일정 2", "일정 3", "마음에 드는 게 없어요"])

    if selected == "마음에 드는 게 없어요":
        st.warning("😅 다시 새로운 일정을 생성할게요!")
        if st.button("새로운 일정 다시 추천받기"):
            with st.spinner("새로운 일정 다시 추천 중..."):
                result = generate_schedule_gpt(
                    location=destination,
                    days=days,
                    style=travel_type,
                    companions=companions,
                    budget=budget,
                    selected_places=selected_places,
                    travel_date=str(start_date),
                    count=3
                )
                st.session_state.schedule_result = result.split("---")
                st.session_state.chat_history = [
                    {"role": "system", "content": "너는 여행 일정 전문가야. 아래 일정에 대해 사용자의 수정 요청에 응답해줘."},
                    {"role": "user", "content": f"기존 일정:
{result}"}
                ]
                st.rerun()

    else:
        idx = int(selected[-1]) - 1
        st.session_state.selected_plan = st.session_state.schedule_result[idx].strip()
        st.markdown("""
        <hr>
        <h4>✏️ 일정 수정 요청하기</h4>
        """, unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-assistant">{st.session_state.selected_plan}</div>', unsafe_allow_html=True)

        user_msg = st.chat_input("수정하고 싶은 내용을 입력하세요!")
        if user_msg:
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