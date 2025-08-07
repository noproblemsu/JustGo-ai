from datetime import datetime, timedelta

def build_prompt(location, days, budget, companions, style, selected_places, travel_date, count=3):
    companion_str = ', '.join(companions) if companions else "없음"
    selected_str = '\n'.join([f"- {place.strip()}" for place in selected_places if place.strip()]) or "없음"

    # 날짜 리스트 생성
    start_date = travel_date
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

✅ 일정 작성 규칙:
1. **각 날짜마다 아침, 점심, 저녁 3개의 활동**을 포함해.
2. 각 활동마다 다음 정보를 포함해줘:
   - 활동 내용
   - **예상 소요 시간 (예: 1시간, 1시간 30분 등)**
   - **예상 비용 (예: 15,000원)**
   예시: `09:00~10:30 불국사 관람 (약 1시간 30분, 약 3,000원)`
3. 일정은 **실제 가능한 동선 중심, 다음 일정으로 넘어갈 때 자동차로 1시간 이내의 동선**으로 구성하고, 너무 빡빡하지 않게 해줘.
4. **전체 예상 비용은 입력 예산과 10% 이하 차이**가 나도록 조절해줘.
5. 하루가 끝날 때마다 **간단한 마무리 문장**으로 정리해줘.
6. 결과는 날짜별로 **마크다운 형식**으로 예쁘게 정리해줘.
7. 마지막에는 전체 여행 일정에 대한 **총 예상 비용**을 계산해서 아래처럼 문장으로 알려줘:
   예시: `총 예상 비용은 약 267,000원으로, 입력 예산인 300,000원 내에서 잘 계획되었어요.`
8. 사용자가 일정을 고를 수 있도록 **각기 다른 스타일의 여행 일정 {count}개**를 작성해줘.  
9. 각 일정은 반드시 마크다운 구분선 `---` 으로 정확히 나누고, 일정 제목은 다음 형식으로 써줘:  
   - `### 일정추천 1: {{간단한 요약}}`  
   - `### 일정추천 2: {{간단한 요약}}`  
   - `### 일정추천 3: {{간단한 요약}}`  
10. **각 일정의 세부 내용은 제목 아래에만 포함**해줘. 제목만 보면 어떤 여행 스타일인지 대략적으로 유추할 수 있게 해줘.
"""
