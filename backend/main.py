import streamlit as st
import time
from gpt_client import generate_schedule_gpt

# ✅ UI 구성
st.title("🌏 ChatTrip: AI 여행 플래너")

destination = st.selectbox("어디로 여행 가시나요?", 
    ["강릉", "경주", "광주", "대구", "대전", "부산", "서울", "속초", "여수", "울산", "인천", "전주", "제주도", "직접 입력"])

if destination == "직접 입력":
    destination = st.text_input("여행지를 직접 입력해주세요")

days = st.slider("여행 기간(일 수)", 1, 10, 3)
budget = st.number_input("여행 예산 (원)", min_value=10000, step=10000, value=300000)
travel_type = st.selectbox("여행 스타일을 선택하세요", ["휴식 중심", "액티비티 중심", "맛집 탐방", "역사 탐방"])

with st.expander("추가 옵션"):
    with_friends = st.checkbox("친구랑 함께")
    with_family = st.checkbox("가족과 함께")
    selected_places = st.text_area("방문하고 싶은 장소 (관광지나 맛집 등)", placeholder="예: 불국사, 황리단길, 경주월드 등").split(',')

# 세션 초기화
if "schedule_result" not in st.session_state:
    st.session_state.schedule_result = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ✅ GPT 호출
if st.button("일정 추천 받기"):
    companions = []
    if with_friends: companions.append("친구")
    if with_family: companions.append("가족")

    st.success(f"{destination}에서 {days}일 동안 '{travel_type}' 여행 일정을 준비 중이에요!")

    with st.spinner("AI가 여행 일정을 생성 중입니다..."):
        result = generate_schedule_gpt(destination, days, travel_type, companions, budget, selected_places)
        st.session_state.schedule_result = result
        st.session_state.chat_history = [
            {"role": "system", "content": "너는 여행 일정 전문가야. 아래 일정에 대해 사용자의 수정 요청에 응답해줘."},
            {"role": "user", "content": f"기존 일정:\n{result}"}
        ]
        time.sleep(1)
        st.info(result)

# ✅ 일정 수정 요청
if st.session_state.schedule_result:
    st.subheader("✏️ 일정 수정 요청하기")
    user_msg = st.chat_input("수정하고 싶은 내용을 입력하세요!")

    if user_msg:
        st.chat_message("user").write(user_msg)
        st.session_state.chat_history.append({"role": "user", "content": user_msg})

        from gpt_engine import client
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=st.session_state.chat_history
            )
            ai_msg = response.choices[0].message.content
            st.chat_message("assistant").write(ai_msg)
            st.session_state.chat_history.append({"role": "assistant", "content": ai_msg})
        except Exception as e:
            st.error(f"⚠️ 에러 발생: {e}")
