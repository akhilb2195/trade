import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")

# Basket order = place multiple orders in a single API call (max 10 orders)
data = [
    {
        "symbol": "NSE:SBIN-EQ",      # State Bank of India
        "qty": 1,
        "type": 2,                     # Market Order
        "side": 1,                     # Buy
        "productType": "INTRADAY",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    },
    {
        "symbol": "NSE:IDEA-EQ",       # Vodafone Idea
        "qty": 1,
        "type": 2,                     # Market Order
        "side": 1,                     # Buy
        "productType": "INTRADAY",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    },
    {
        "symbol": "NSE:SBIN-EQ",
        "qty": 1,
        "type": 2,
        "side": -1,                    # Sell
        "productType": "INTRADAY",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    },
    {
        "symbol": "NSE:IDEA-EQ",
        "qty": 1,
        "type": 2,
        "side": -1,                    # Sell
        "productType": "INTRADAY",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
    }
]

# Places all orders simultaneously — faster than placing one by one
response = fyers.place_basket_orders(data=data)
print(response)