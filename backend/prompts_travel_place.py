def build_prompt(destination, days, budget, companions, style):
    prompt = f"""
사용자가 여행을 계획하고 있습니다. 아래 정보를 모두 고려하여 **관광지 5곳**과 **맛집 5곳**을 추천해 주세요.

[사용자 정보]
- 여행지: {destination}
- 여행 기간: {days}일
- 예산: {budget}원
- 여행 스타일: {style}
- 동반자: {companions}

[요청 사항]
- 관광지와 음식점은 구체적인 장소명으로 추천해 주세요. (예: 정동진 해수욕장, 교동짬뽕 본점)
- 추천은 numbered list 형식으로 제공해 주세요.
- 관광지와 음식점은 따로 구분해 주세요.

[출력 예시]
관광지 추천:
1. 장소명 - 간단한 설명

맛집 추천:
1. 장소명 - 간단한 설명
    """.strip()

    return prompt

def generate_schedule_gpt(destination, days, budget, travel_type, companion):
    return f"""
당신은 여행 플래너입니다.
다음 조건을 고려해 관광지와 맛집을 각각 5곳씩 추천해주세요.

여행지: {destination}
여행 기간: {days}일
예산: {budget}원
여행 스타일: {travel_type}
동반자: {companion}

다음과 같은 형식으로 출력해 주세요:

관광지 추천:
1. 장소명 - 간단한 설명
...

맛집 추천:
1. 장소명 - 대표 메뉴
...
"""

