from openai import OpenAI
from prompts import build_prompt

client = OpenAI(api_key="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")  # 그대로 유지

def generate_schedule_gpt(location, days, style, companions, budget, selected_places, travel_date, count=3):
    # ✅ 일정 3개를 한 번에 생성하는 프롬프트
    prompt = build_prompt(
        location=location,
        days=days,
        budget=budget,
        companions=companions,
        style=style,
        selected_places=selected_places,
        travel_date=travel_date,
        count=count  # 명시적으로 전달
    )

    # ✅ GPT 한 번만 호출
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "너는 여행 일정 전문가야."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content.strip()  # 💡 하나의 응답 전체를 반환

def ask_gpt(prompt: str):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "당신은 여행지 추천 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content

def extract_places(response):
    sightseeing = []
    restaurants = []

    lines = response.splitlines()
    current = None

    for line in lines:
        if "관광지 추천" in line:
            current = "sightseeing"
        elif "맛집 추천" in line:
            current = "restaurants"
        elif line.strip().startswith(tuple("1234567890")):
            if current == "sightseeing":
                sightseeing.append(line)
            elif current == "restaurants":
                restaurants.append(line)

    return sightseeing, restaurants  # ✅ 반드시 두 개 반환
