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
너는 여행 일정 전문 플래너야.

여행지는 {location}이고, 여행 기간은 총 {days}일이야.
여행 날짜는 다음과 같아:
{date_str}

각 날짜는 요일이 함께 포함되어 있고, **각 날짜마다 아침, 점심, 저녁 일정**을 모두 구성해줘.

여행 예산은 {budget:,}원이야.
동반자는 {companion_str}이고, 여행 스타일은 '{style}'이야.

아래는 사용자가 선호하는 장소 목록이야:
{selected_str}

다만 사용자가 선택한 장소가 부족하거나 많을 경우, 적절히 추가하거나 줄여도 괜찮아.

---

### ✅ 반드시 지켜야 할 일정 작성 규칙

1. 각 날짜는 **아침, 점심, 저녁 3개의 활동**으로 구성할 것.
2. 각 활동에는 다음 항목이 필수야:
   - 활동 시간 (예: `09:00~10:30`)
   - 활동 설명
   - 예상 소요 시간 (예: 약 1시간 30분)
   - 예상 비용 (예: 약 15,000원)
   예시: `09:00~10:30 불국사 관람 (약 1시간 30분, 약 3,000원)`
3. 일정은 **동선 고려**, 자동차로 **1시간 이내 거리**로 무리하지 않게 구성할 것.
4. ⚠️ **각 일정 추천 하나당 총 예상 비용은 반드시 예산의 ±15% 이내**여야 해.
   - 예산이 {budget:,}원이면, 각 일정별 총 비용은 반드시 **{int(budget*0.85):,}원 ~ {int(budget*1.15):,}원** 범위 내여야 해.
   - 이 범위를 벗어나면 무효야. 반드시 정확히 지켜.
5. 각 날짜는 {days}일 모두 빠짐없이 작성해. 하루라도 누락되면 잘못된 일정이야.
6. 각 날짜의 마지막에는 **간단한 마무리 문장**을 넣을 것.
7. 출력은 **마크다운 형식**으로 정리할 것.
8. ⚠️ **총 예상 비용은 각 일정마다 마지막에 1번만 출력**할 것.
   - 예시: `총 예상 비용은 약 289,000원으로, 입력 예산인 300,000원 내에서 잘 계획되었어요.`
   - 중간에 쓰지 말고, 하루마다 쓰지 말고, 일정 끝에 한 번만 써.
9. 총 {count}개의 추천 일정을 구성하고, **서로 다른 스타일**로 구성해.
10. 각 일정은 다음 제목 형식으로 시작하고, 반드시 `---` 구분선을 둘 것:
    - 일정추천 1: 힐링중심
    - 일정추천 2: 자연중심
    - 일정추천 3: 먹기중심
11. 각 제목 다음 줄부터 본문 시작. 일정 본문 중에는 `"일정추천"`이라는 단어를 다시 쓰지 마.
12. 출력에 오류가 나면 안 돼. 이 형식을 어기면 잘못된 응답이야. 반드시 모든 규칙을 지켜.
"""
