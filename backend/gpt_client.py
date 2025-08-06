from openai import OpenAI
from prompts import build_prompt

client = OpenAI(api_key="너의_실제_API_키")  # 이미 설정되어 있음

def generate_schedule_gpt(location, days, style, companions, budget, selected_places, travel_date, count=3):
    prompt = build_prompt(
        location=location,
        days=days,
        budget=budget,
        companions=companions,
        style=style,
        selected_places=selected_places,
        travel_date=travel_date,
        count=count  # ✅ count 추가
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "너는 여행 일정 전문가야."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content
