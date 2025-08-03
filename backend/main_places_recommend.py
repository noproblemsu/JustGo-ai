import streamlit as st
from prompts import generate_schedule_gpt
from gpt_client import ask_gpt, extract_places
import urllib.parse  # 네이버 지도 링크 생성을 위한 모듈

# 네이버 지도 링크 생성 함수
def generate_naver_map_url(place_name):
    base_url = "https://map.naver.com/v5/search/"
    encoded_name = urllib.parse.quote(place_name)
    return f"{base_url}{encoded_name}"

# ✅ Streamlit UI 구성
st.title("🌏 ChatTrip: AI 여행 플래너")

destination = st.selectbox("어디로 여행 가시나요?", 
    ["강릉", "경주", "광주", "대구", "대전", "부산", "서울", "속초", "여수", "울산", "인천", "전주", "제주도", "직접 입력"])

if destination == "직접 입력":
    destination = st.text_input("여행지를 직접 입력해주세요")

days = st.slider("여행 기간(일 수)", 1, 10, 3)
budget = st.number_input("여행 예산 (원)", min_value=10000, step=10000, value=300000)
travel_type = st.selectbox("여행 스타일을 선택하세요", ["휴식 중심", "액티비티 중심", "맛집 탐방", "역사 탐방"])
companion = st.selectbox("동반자는 누구인가요?", ["혼자", "가족", "연인", "친구", "반려동물"])

if st.button("추천 받기"):
    with st.spinner("AI가 여행지를 추천 중입니다..."):
        prompt = generate_schedule_gpt(destination, days, budget, travel_type, companion)
        response = ask_gpt(prompt)
        sightseeing, restaurants = extract_places(response)

    # 관광지 출력
    if sightseeing:
        st.subheader("📸 관광지 추천")
        for place in sightseeing:
            link = generate_naver_map_url(place)
            st.markdown(f"👉 [{place} - 네이버 지도에서 보기]({link})", unsafe_allow_html=True)

    # 맛집 출력
    if restaurants:
        st.subheader("🍽️ 맛집 추천")
        for place in restaurants:
            link = generate_naver_map_url(place)
            st.markdown(f"👉 [{place} - 네이버 지도에서 보기]({link})", unsafe_allow_html=True)

