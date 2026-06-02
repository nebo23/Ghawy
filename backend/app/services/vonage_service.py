import os
import random
import string

def generate_otp() -> str:
    """6 أرقام عشوائية"""
    return ''.join(random.choices(string.digits, k=6))

def send_otp_sms(phone: str, code: str) -> bool:
    """
    بيبعت SMS عبر Vonage باستخدام REST API
    """
    if phone.startswith("0"):
        international_phone = "2" + phone
    elif phone.startswith("+"):
        international_phone = phone[1:]
    else:
        international_phone = phone

    message = f"كود التحقق الخاص بك في Ghawy هو: {code}\nصالح لمدة 10 دقائق."

    api_key = os.getenv("VONAGE_API_KEY")
    api_secret = os.getenv("VONAGE_API_SECRET")
    from_name = os.getenv("VONAGE_FROM", "Ghawy")

    if not api_key or not api_secret:
        print(f"========== OTP CODE FOR {phone} IS: {code} ==========")
        print("Vonage API credentials missing - OTP bypassed (dev mode)")
        return True

    try:
        import requests
        url = "https://rest.nexmo.com/sms/json"
        payload = {
            "api_key": api_key,
            "api_secret": api_secret,
            "to": international_phone,
            "from": from_name,
            "text": message,
            "type": "unicode"
        }
        print(f"========== OTP CODE FOR {phone} IS: {code} ==========")
        res = requests.post(url, data=payload, timeout=10)
        data = res.json()
        print(f"Vonage Response: {data}")
        messages = data.get("messages", [])
        if messages and str(messages[0].get("status")) == "0":
            return True
        error_text = messages[0].get("error-text", "Unknown error") if messages else "No message object"
        print(f"Vonage SMS Failed - Error: {error_text}")
        return False

    except Exception as e:
        print(f"========== OTP CODE FOR {phone} IS: {code} ==========")
        print(f"Vonage HTTP Error: {e}")
        return False
