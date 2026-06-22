import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")

# Returns current market status — open, closed, pre-open, post-close etc.
response = fyers.market_status()
print(response)