# telegram_alerts.py
import requests
import time

def send_telegram_message(bot_token: str, chat_id: str, text: str):
    """
    Simple synchronous send. Returns True if sent, False otherwise.
    """
    if not bot_token or not chat_id:
        raise ValueError("Provide bot_token and chat_id in config.")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return True
        else:
            # Telegram returns helpful error text in r.json()
            time.sleep(0.5)
            return False
    except Exception as e:
        print("Telegram send error:", e)
        return False

