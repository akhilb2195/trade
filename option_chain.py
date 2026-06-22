import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")

# Option Chain = all available CE/PE strike prices for a given stock/index
data = {
    "symbol": "NSE:TCS-EQ",    # Underlying stock | For index use NSE:NIFTY50-INDEX
    "strikecount": 1,           # Number of strikes above & below ATM (1 = 1 above + 1 below = 2 strikes total)
    "timestamp": ""             # "" = current/nearest expiry | "1700000000" = specific expiry as unix timestamp
}

response = fyers.optionchain(data=data)
print(response)