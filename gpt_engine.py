from openai import OpenAI
from prompts import build_prompt

# ✅ 민재님의 실제 API 키 적용
client = OpenAI(api_key="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")

def generate_schedule_gpt(location, days, style, companions, budget, selected_places):
    prompt = build_prompt(location, days, budget, companions, style, selected_places)

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ 에러 발생: {e}"
