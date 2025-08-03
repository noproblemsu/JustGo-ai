import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

def ask_gpt(prompt):
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content

def extract_places(response_text):
    sightseeing = []
    restaurants = []
    mode = None

    for line in response_text.split('\n'):
        line = line.strip()
        if '관광지 추천' in line:
            mode = 'sightseeing'
            continue
        elif '맛집 추천' in line:
            mode = 'restaurant'
            continue

        match = re.match(r'^\d+\.\s*(.+?)(\s*-\s*.+)?$', line)
        if match:
            name = match.group(1).strip()
            if mode == 'sightseeing':
                sightseeing.append(name)
            elif mode == 'restaurant':
                restaurants.append(name)

    return sightseeing, restaurants

