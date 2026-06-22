import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")

response = fyers.market_status()

# Exchange codes: 10 = NSE | 11 = MCX | 12 = BSE
# Segment codes:  10 = Capital Market | 11 = F&O | 12 = Currency | 20 = Commodity

exchange_map = {10: "NSE", 11: "MCX", 12: "BSE"}
segment_map  = {10: "Capital Market", 11: "F&O", 12: "Currency", 20: "Commodity"}

for market in response["marketStatus"]:
    exchange = exchange_map.get(market["exchange"], market["exchange"])
    segment  = segment_map.get(market["segment"], market["segment"])
    print(f"{exchange} | {segment} | {market['market_type']} → {market['status']}")
