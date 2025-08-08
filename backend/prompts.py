from datetime import datetime, timedelta

def build_prompt(location, days, budget, companions, style, selected_places, travel_date, count=3):
    companion_str = ', '.join(companions) if companions else "없음"
    selected_str = '\n'.join([f"- {place.strip()}" for place in selected_places if place.strip()]) or "없음"

    if isinstance(travel_date, str):
        start_date = datetime.strptime(travel_date, "%Y-%m-%d")
    else:
        start_date = travel_date

    date_list = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d (%a)") for i in range(days)]
    date_str = '\n'.join([f"- {d}" for d in date_list])

    return f"""
너는 여행 일정을 작성하는 전문가야.

🗺️ 여행지: {location}
📅 여행 기간: 총 {days}일
🗓️ 여행 날짜:
{date_str}

👥 동반자: {companion_str}
🎯 여행 스타일: '{style}'
💰 예산: {budget:,}원

선호 장소 목록:
{selected_str}

단, 사용자가 입력한 장소가 부족하거나 너무 많을 경우 적절히 보완하거나 조정해도 괜찮아.

---

## ✅ 반드시 지켜야 할 일정 작성 규칙

1. 각 날짜는 **아침, 점심, 저녁 일정 3개**로 구성되어야 한다. 하루라도 빠지면 안 된다.
2. 각 활동은 다음 항목을 반드시 포함해야 한다:
   - 시간 (예: 09:00~10:30)
   - 설명
   - 소요 시간 (예: 약 1시간 30분)
   - 비용 (예: 약 15,000원)

   예시: `09:00~10:30 불국사 관람 (약 1시간 30분, 약 3,000원)`

3. 일정 동선은 반드시 **자동차로 1시간 이내 거리**로 자연스럽고 현실성 있게 구성할 것.
4. ⚠️ **각 일정의 총 예상 비용은 입력 예산의 ±15% 이내**여야 한다. 절대 넘기지 마라.
   - 입력 예산이 {budget:,}원일 경우, 허용 범위는 **{int(budget*0.85):,}원 ~ {int(budget*1.15):,}원**이다.
   - 이 범위를 넘기면 틀린 일정이므로 무효다. 정확히 지켜야 한다.

5. 각 날짜의 마지막에는 반드시 **간단한 마무리 문장**을 넣어야 한다.
6. 일정 전체는 **Markdown 형식**으로 깔끔하게 정리해야 한다.
7. ⚠️ **각 추천 일정의 맨 마지막에만 총 예상 비용을 1번만 출력할 것. 중간에 쓰면 안 됨.**
   - 예: `총 예상 비용은 약 298,000원으로, 입력 예산인 300,000원 내에서 잘 계획되었어요.`

8. 총 {count}개의 서로 다른 추천 일정을 만들어야 한다.
9. 각 일정은 반드시 다음 형식의 제목으로 시작하고, 아래에 `---` 구분선을 넣는다:
   - 일정추천 1: 힐링중심
   - 일정추천 2: 자연중심
   - 일정추천 3: 먹기중심

10. 일정 제목 다음 줄부터 바로 본문을 시작하고, 본문에는 `"일정추천"`이라는 단어를 다시 쓰지 마라.
11. 각 추천 일정은 반드시 **{days}일치** 일정으로 구성해야 한다. 하루라도 빠지면 잘못된 응답이다.
12. 위 조건을 어기면 잘못된 결과다. 반드시 모든 조건을 충족해라.
"""
