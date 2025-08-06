from openai import OpenAI
from prompts import build_prompt

client = OpenAI(api_key="your-api-key")  # 🔑 실제 키로 교체하세요

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