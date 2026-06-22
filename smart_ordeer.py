import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, is_async=False, token=access_token, log_path="")

# Smart Order = GTT (Good Till Triggered) order with auto target/stoploss management
data = {
    "symbol": "NSE:SBIN-EQ",       # Stock symbol
    "side": 1,                      # 1 = Buy | -1 = Sell
    "qty": 1,                       # Number of shares
    "productType": "CNC",           # CNC = delivery (holds shares) | INTRADAY = same day square off
    "limitPrice": 1250,             # Entry price — order triggers when stock hits this price
    "stopPrice": 1200,              # Stoploss price — auto exit if stock falls to this
    "orderType": 1,                 # 1 = Limit | 2 = Market
    "endTime": 1768987800,          # Unix timestamp — order expires after this time
    "hpr": 1300,                    # High Price Range — target/take profit price
    "lpr": 700,                     # Low Price Range — lower bound for price monitoring
    "mpp": 1,                       # Min Price change to trigger — 1 = trigger on every tick
    "onExp": 2                      # Action on expiry: 1 = cancel order | 2 = convert to market order
}

response = fyers.create_smart_order_limit(data=data)
print(response)