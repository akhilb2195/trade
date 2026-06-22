import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")

# Market Depth = Level 2 order book (top 5 buy/sell orders in the market)
data = {
    "symbol": "NSE:SBIN-EQ",
    "ohlcv_flag": "1"       # 1 = include OHLCV data along with depth | 0 = depth only
}

response = fyers.depth(data=data)
print(response)