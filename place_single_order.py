import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")

data = {
    "symbol": "NSE:IDEA-EQ",       # Exchange:StockName-EQ(Equity) | BSE:IDEA-EQ for BSE
    "qty": 1,                        # Number of shares to buy/sell
    "type": 2,                       # 1 = Limit Order | 2 = Market Order | 3 = Stop Order | 4 = Stop-Limit
    "side": 1,                       # 1 = Buy | -1 = Sell
    "productType": "INTRADAY",       # INTRADAY = same day square off | CNC = delivery | MARGIN = leverage
    "limitPrice": 0,                 # Price for limit order | 0 if Market Order (type=2)
    "stopPrice": 0,                  # Trigger price for stop orders | 0 if not a stop order
    "validity": "DAY",               # DAY = valid till market close | IOC = cancel if not filled immediately
    "disclosedQty": 0,               # Quantity visible to market (for large orders) | 0 = show full qty
    "offlineOrder": False,           # True = pre-market order | False = live market order
    "orderTag": "tag1",              # Your custom label to track/identify this order
    "isSliceOrder": False            # True = split large order into smaller ones automatically
}

response = fyers.place_order(data=data)
print(response)