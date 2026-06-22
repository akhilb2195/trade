import creditials as cr
from fyers_apiv3.FyersWebsocket import data_ws

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

# IMPORTANT: WebSocket needs "clientid:accesstoken" format
full_token = f"{cr.client_id}:{access_token}"
print(f"Using token: {full_token[:20]}...")  # Print first 20 chars to verify format

# ── Callbacks ────────────────────────────────────────────

def onopen():
    print("✅ WebSocket connected successfully")

    symbols   = ["NSE:SBIN-EQ", "NSE:IDEA-EQ"]
    data_type = "SymbolUpdate"   # SymbolUpdate = live price | OrderUpdate = order status

    print(f"Subscribing to: {symbols}")
    fyers.subscribe(symbols=symbols, data_type=data_type)
    fyers.keep_running()

def onclose(message):
    print(f"🔴 WebSocket closed: {message}")

def onerror(message):
    print(f"❌ WebSocket error: {message}")

def onmessage(message):
    print(f"📩 Raw message: {message}")

    # Extract fields safely
    symbol = message.get("symbol", "N/A")
    ltp    = message.get("lp",    "N/A")   # Last traded price
    ch     = message.get("ch",    "N/A")   # Change in price
    chp    = message.get("chp",   "N/A")   # Change in %
    high   = message.get("high_price", "N/A")
    low    = message.get("low_price",  "N/A")
    vol    = message.get("vol",   "N/A")   # Volume
    bid    = message.get("bid",   "N/A")   # Best buy price
    ask    = message.get("ask",   "N/A")   # Best sell price

    print(f"""
    ----------------------------------------
    Symbol  : {symbol}
    LTP     : ₹{ltp}  ({ch} | {chp}%)
    High/Low: ₹{high} / ₹{low}
    Bid/Ask : ₹{bid} / ₹{ask}
    Volume  : {vol}
    ----------------------------------------
    """)

# ── Initialize WebSocket ─────────────────────────────────

print("Connecting to Fyers WebSocket...")

fyers = data_ws.FyersDataSocket(
    access_token  = full_token,   # "clientid:accesstoken"
    log_path      = "",           # auto create logs in current directory
    litemode      = False,        # False = full data | True = only ltp/chp/ch
    write_to_file = False,        # False = print to console
    reconnect     = True,         # auto reconnect on disconnect
    on_connect    = onopen,
    on_close      = onclose,
    on_error      = onerror,
    on_message    = onmessage,
    reconnect_retry = 10          # retry 10 times before giving up
)

# ── Start connection — MUST be last line ─────────────────
fyers.connect()
