import base64
import requests
from datetime import datetime
from django.conf import settings


def _require_setting(name):
    value = getattr(settings, name, None)
    if not value:
        raise RuntimeError(f"{name} is not configured. Set it in the environment before sending an M-Pesa prompt.")
    return value


def get_access_token():
    """Fetch an OAuth access token from Safaricom's Daraja API (sandbox)."""
    consumer_key = _require_setting('MPESA_CONSUMER_KEY')
    consumer_secret = _require_setting('MPESA_CONSUMER_SECRET')
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(
        url,
        auth=(consumer_key, consumer_secret),
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(f"M-Pesa authentication failed: {response.status_code} {response.text}")
    return response.json()["access_token"]


def generate_password(shortcode, passkey, timestamp):
    """Base64(Shortcode + Passkey + Timestamp), as required by Daraja."""
    raw = f"{shortcode}{passkey}{timestamp}"
    return base64.b64encode(raw.encode()).decode()


def format_phone_number(phone):
    """Normalize to the 2547XXXXXXXX format Daraja expects."""
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    if phone.startswith("7") or phone.startswith("1"):
        phone = "254" + phone
    return phone


def stk_push(phone_number, amount, account_reference, transaction_desc):
    """
    Initiates an STK Push prompt on the customer's phone.
    Returns the parsed JSON response from Daraja (contains CheckoutRequestID etc).
    Raises RuntimeError or requests.HTTPError on failure.
    """
    if not phone_number:
        raise ValueError("A customer phone number is required to send an M-Pesa prompt.")

    access_token = get_access_token()
    shortcode = _require_setting('MPESA_SHORTCODE')
    passkey = _require_setting('MPESA_PASSKEY')
    callback_url = _require_setting('MPESA_CALLBACK_URL')
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    password = generate_password(shortcode, passkey, timestamp)
    formatted_phone = format_phone_number(phone_number)

    url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),  # Daraja sandbox requires a whole number
        "PartyA": formatted_phone,
        "PartyB": shortcode,
        "PhoneNumber": formatted_phone,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_desc,
    }

    response = requests.post(url, json=payload, headers=headers, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f"M-Pesa prompt failed: {response.status_code} {response.text}")
    return response.json()