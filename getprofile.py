import creditials as cr
from fyers_apiv3 import fyersModel

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, is_async=False, token=access_token, log_path="")

# Make a request to get the user profile information
response = fyers.get_profile()

# Print the response received from the Fyers API
print(response)