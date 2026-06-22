import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")

# Create a price alert — Fyers will notify when condition is met
data = {
    "agent": "fyers-api",
    "alert-type": 1,
    "name": "NSE:SBIN-EQ",
    "symbol": "MCX:SILVERM26MARFUT",    # ✅ MAR 2026 active contract
    "comparisonType": "LTP",
    "condition": "LT",
    "value": 45
}

response = fyers.create_alert(data=data)
print(response)