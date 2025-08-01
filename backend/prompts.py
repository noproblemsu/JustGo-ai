def build_prompt(location, days, budget, companions, style, selected_places):
    companion_str = ', '.join(companions) if companions else "없음"
    selected_str = '\n'.join([f"- {place.strip()}" for place in selected_places if place.strip()]) or "없음"

    return f"""
너는 여행 일정 전문 플래너야.

여행지는 {location}이고, 여행 기간은 {days}일이야.
예산은 {budget:,}원 정도야.
동반자는 {companion_str}이고, 여행 스타일은 '{style}'이야.

아래는 사용자가 선호하는 관광지 및 맛집 리스트야:
{selected_str}

하지만 사용자가 선택한 장소가 일정에 부족하거나 넘칠 경우, 너가 적절히 추가하거나 줄여줘.

각 날짜마다 아침, 점심, 저녁 포함 3개의 활동으로 일정을 정리해줘.
단, **일정이 과도하게 빡빡하지 않고, 실제 가능한 동선 중심**으로 작성해.

결과는 날짜별로 마크다운 형식으로 정리해줘.
"""
