from openai import OpenAI
from datetime import datetime

# 🔑 OpenAI 클라이언트 초기화
client = OpenAI(api_key="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")  # 여기에 실제 키 입력 (따옴표 포함!)

# 🧠 사용자 입력값 기반 프롬프트 생성 함수
def build_prompt(destination, days, budget, companions, style, travel_date="미정"):
    try:
        budget = int(budget)
    except ValueError:
        budget = 0

    prompt = f"""
사용자가 여행을 계획하고 있습니다. 아래 정보를 모두 고려하여 **관광지 5곳**과 **맛집 5곳**을 추천해 주세요.

[사용자 정보]
- 여행지: {destination}
- 여행 기간: {days}일
- 예산: {budget:,}원
- 여행 스타일: {style}
- 동반자: {companions}
- 여행 날짜: {travel_date}

[요청 사항]
- 관광지와 음식점은 구체적인 장소명으로 추천해 주세요. (예: 정동진 해수욕장, 교동짬뽕 본점)
- 추천은 numbered list 형식으로 제공해 주세요.
- 관광지와 음식점은 따로 구분해 주세요.

[출력 예시]
관광지 추천:
1. 장소명 - 간단한 설명

맛집 추천:
1. 장소명 - 대표 메뉴
""".strip()

    return prompt


# 💬 GPT 호출 함수
def generate_schedule_gpt(destination, days, budget, travel_type, companion, travel_date="미정"):
    prompt = build_prompt(destination, days, budget, companion, travel_type, travel_date)

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 여행 플래너입니다."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content

