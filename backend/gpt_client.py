from openai import OpenAI
from prompts import build_prompt

client = OpenAI(api_key="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")

def generate_schedule_gpt(location, days, style, companions, budget, selected_places, travel_date, count=3):
    prompt = build_prompt(
        location=location,
        days=days,
        budget=budget,
        companions=companions,
        style=style,
        selected_places=selected_places,
        travel_date=travel_date
    )

    # 🔁 3개의 일정 요청 (count만큼 반복해서 생성)
    results = []
    for _ in range(count):
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "너는 여행 일정 전문가야."},
                {"role": "user", "content": prompt}
            ]
        )
        results.append(response.choices[0].message.content.strip())

    # ✂️ 결과를 ---로 구분
    return "\n\n---\n\n".join(results)

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

