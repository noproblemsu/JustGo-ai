from datetime import datetime, timedelta

def build_prompt(location, days, budget, companions, style, selected_places, travel_date, count=3):
    companion_str = ', '.join(companions) if companions else "없음"
    selected_str = '\n'.join([f"- {place.strip()}" for place in selected_places if place.strip()]) or "없음"

    # 문자열 or datetime.date 처리
    if isinstance(travel_date, str):
        start_date = datetime.strptime(travel_date, "%Y-%m-%d")
    else:
        start_date = travel_date

    # 날짜 리스트 생성
    date_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d (%a)") for i in range(days)]
    date_str = '\n'.join([f"- {d}" for d in date_list])

    return f"""
너는 여행 일정 전문 플래너야.

여행지는 {location}이고, 여행 기간은 총 {days}일이야.
여행 날짜는 다음과 같아:
{date_str}

각 날짜에 해당하는 요일도 포함되어 있어. **각 날짜마다 아침, 점심, 저녁 일정**을 모두 짜줘.

예산은 {budget:,}원 정도야.
동반자는 {companion_str}이고, 여행 스타일은 '{style}'이야.

아래는 사용자가 선호하는 관광지 및 맛집 리스트야:
{selected_str}

하지만 사용자가 선택한 장소가 일정에 부족하거나 넘칠 경우, 너가 적절히 추가하거나 줄여줘.

---

### ✅ 일정 작성 규칙:
1. **각 날짜마다 아침, 점심, 저녁 3개의 활동**을 포함해.
2. 각 활동마다 다음 정보를 포함해줘:
   - 활동 내용
   - **예상 소요 시간 (예: 1시간, 1시간 30분 등)**
   - **예상 비용 (예: 15,000원)**
   예시: `09:00~10:30 불국사 관람 (약 1시간 30분, 약 3,000원)`
3. 일정은 **실제 가능한 동선 중심, 자동차로 1시간 이내 이동**, 무리하지 않게 구성해줘.
4. **전체 예상 비용은 반드시 입력 예산의 ±15% 이내여야 해.**
   - 예: 예산이 300,000원이면 총 예상 비용은 **255,000원 ~ 345,000원** 사이여야 해.
   - 이 범위를 벗어나면 틀린 결과야. 반드시 맞춰줘.
5. 하루가 끝날 때마다 **간단한 마무리 문장**을 추가해줘.
6. 각 날짜별 일정은 **마크다운 형식**으로 정리해.
7. **총 예상 비용은 맨 마지막에 1번만 작성**해줘.
   - 예시: `총 예상 비용은 약 289,000원으로, 입력 예산인 300,000원 내에서 잘 계획되었어요.`
8. 서로 다른 스타일의 여행 일정 {count}개를 만들어줘.
9. 각 일정은 아래 형식의 제목으로 시작하고, `---`로 구분해:
   - 일정추천 1
   - 일정추천 2
   - 일정추천 3
10. 제목 다음 줄부터 본문 시작하고, 각 일정 내에 `일정추천`이라는 단어는 반복하지 마.
11. 형식을 반드시 지켜서 출력해줘. 그렇지 않으면 잘못된 응답이야.
"""
