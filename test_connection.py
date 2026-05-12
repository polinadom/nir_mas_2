import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("LLM_API_KEY")
model = os.getenv("LLM_MODEL")
base_url = os.getenv("LLM_BASE_URL")

print("🔍 ПРОВЕРКА ПОДКЛЮЧЕНИЯ")
print(f"URL: {base_url}")
print(f"Model: {model}")
print(f"Key: {api_key[:20]}...")

try:
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Say OK"}],
        max_tokens=5
    )
    
    print("\n✅ ПОДКЛЮЧЕНИЕ УСПЕШНО!")
    print(f"Ответ: {response.choices[0].message.content}")
    
except Exception as e:
    print(f"\n❌ ОШИБКА: {e}")