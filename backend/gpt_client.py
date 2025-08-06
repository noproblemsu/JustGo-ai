# ✅ gpt_client.py (전체 수정된 코드)
from openai import OpenAI
from prompts import build_prompt

client = OpenAI(api_key="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")

def generate_schedule_gpt(location, days, style, companions, budget, selected_places, travel_date):
    prompt = build_prompt(
        location=location,
        days=days,
        budget=budget,
        companions=companions,
        style=style,
        selected_places=selected_places,
        travel_date=travel_date
    )

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "너는 여행 일정 전문가야."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content
