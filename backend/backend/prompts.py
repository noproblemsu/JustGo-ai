def build_prompt(location, days, budget, companions, style, selected_places, travel_date):
    companion_str = ', '.join(companions) if companions else "없음"
    selected_str = '\n'.join([f"- {place.strip()}" for place in selected_places if place.strip()]) or "없음"

    return f"""
너는 여행 일정 전문 플래너야.

여행지는 {location}이고, 여행 기간은 {days}일이야.
출발 날짜는 {travel_date}이야. 해당 날짜 기준으로 식당이나 관광지가 **휴무일은 아닌지 꼭 확인해줘.**

예산은 {budget:,}원 정도야.
동반자는 {companion_str}이고, 여행 스타일은 '{style}'이야.

아래는 사용자가 선호하는 관광지 및 맛집 리스트야:
{selected_str}

하지만 사용자가 선택한 장소가 일정에 부족하거나 넘칠 경우, 너가 적절히 추가하거나 줄여줘.

✅ 일정 작성 규칙:
1. 각 날짜마다 **아침, 점심, 저녁 3개의 활동**을 포함해.
2. 각 활동마다 다음 정보를 포함해줘:
   - 활동 내용
   - **예상 소요 시간 (예: 1시간, 1시간 30분 등)**
   - **예상 비용 (예: 15,000원)**
   예시: `09:00~10:30 불국사 관람 (약 1시간 30분, 약 3,000원)`
3. 일정은 **실제 가능한 동선 중심, 다음 일정으로 넘어갈 때 자동차로 1시간 이내의 동선**으로 구성하고, 너무 빡빡하지 않게 해줘.
4. **전체 예상 비용은 입력 예산과 10% 이하 차이**가 나도록 조절해줘.
5. 하루가 끝날 때마다 **간단한 마무리 문장**으로 정리해줘.
6. 결과는 날짜별로 **마크다운 형식**으로 예쁘게 정리해줘.
"""
