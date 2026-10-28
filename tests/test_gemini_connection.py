import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import requests
from app.config import settings

def test_gemini_connection():
    api_key = settings.GEMINI_API_KEY
    model_id = settings.GEMINI_MODEL_ID
    print(f"Connecting to Google Gemini API (Model: {model_id})...")
    print(f"API Key masked: {api_key[:6]}...{api_key[-4:]}")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Xác nhận kết nối: Bạn là trợ lý AI đọc bản vẽ kỹ thuật BOSOL AI. Hãy trả lời ngắn gọn đúng 1 câu tiếng Việt: 'Hệ thống BOSOL AI đã kết nối thành công với Google Gemini!'."
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 100
        }
    }

    resp = requests.post(url, json=payload, timeout=settings.GEMINI_TIMEOUT_SEC)
    print(f"HTTP Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        reply = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        usage = data.get("usageMetadata", {})
        print("\n--- PHẢN HỒI CHÍNH THỨC TỪ GOOGLE GEMINI ---")
        print(reply)
        print("---------------------------------------------")
        print(f"Usage Token: Input={usage.get('promptTokenCount')}, Output={usage.get('candidatesTokenCount')}")
        print(">>> KẾT NỐI GEMINI API THÀNH CÔNG 100%! <<<")
    else:
        print(f"Lỗi kết nối: {resp.status_code} - {resp.text}")
        raise RuntimeError(f"Gemini API error: {resp.status_code}")

if __name__ == "__main__":
    test_gemini_connection()
