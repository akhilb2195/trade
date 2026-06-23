"""
nifty_banknifty_vwap_scalper.py
---------------------------------
VWAP mean-reversion scalping strategy for NIFTY / BANKNIFTY futures on Fyers API V3.

Assumes you already have a valid access_token (saved in access_token.txt or
set as ACCESS_TOKEN below). This file is the strategy only.

STRATEGY:
1. Trend filter   -> EMA9 vs EMA21 on 5-min candles
2. Entry trigger  -> price pulls back to VWAP, then a confirmation candle
                      closes back in the trend direction
3. Exit           -> fixed stop-loss / target in points, or forced square-off
4. Risk caps      -> max trades/day, max daily loss
"""

import time
import csv
import os
from datetime import datetime, timedelta

import pandas as pd
import creditials as cr
from fyers_apiv3 import fyersModel

# ============================== CONFIG ===============================
SYMBOL = "NSE:BANKNIFTY26JUNFUT"   # VERIFY exact current contract before running
LOT_SIZE = 30                      # 30 BankNifty, 65 Nifty as of 2026 -- verify
NUM_LOTS = 1

STOP_LOSS_POINTS = 20
TARGET_POINTS = 25
VWAP_TOUCH_TOLERANCE = 8           # points within VWAP counted as a "touch"

EMA_FAST = 9
EMA_SLOW = 21

MAX_TRADES_PER_DAY = 4
MAX_DAILY_LOSS = 1500
SQUARE_OFF_TIME = "15:15"
POLL_INTERVAL_SECONDS = 5
TRADE_LOG_FILE = "trade_log.csv"
# =======================================================================

# Read saved access token from file (same pattern as your other scripts)
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")


# --------------------------- Data ------------------------------

def get_intraday_candles(resolution="1"):
    today = datetime.now().strftime("%Y-%m-%d")
    data = {"symbol": SYMBOL, "resolution": resolution, "date_format": "1",
             "range_from": today, "range_to": today, "cont_flag": "1"}
    resp = fyers.history(data=data)
    if resp.get("s") != "ok" or "candles" not in resp:
        raise RuntimeError(f"History fetch failed: {resp}")
    df = pd.DataFrame(resp["candles"], columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s") + timedelta(hours=5, minutes=30)
    return df


def compute_vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    return df


def determine_trend(df_5min):
    if len(df_5min) < EMA_SLOW:
        return "NEUTRAL"
    ema_fast = df_5min["close"].ewm(span=EMA_FAST, adjust=False).mean()
    ema_slow = df_5min["close"].ewm(span=EMA_SLOW, adjust=False).mean()
    if ema_fast.iloc[-1] > ema_slow.iloc[-1]:
        return "UP"
    if ema_fast.iloc[-1] < ema_slow.iloc[-1]:
        return "DOWN"
    return "NEUTRAL"


def get_ltp():
    resp = fyers.quotes(data={"symbols": SYMBOL})
    if resp.get("s") != "ok":
        raise RuntimeError(f"Quote fetch failed: {resp}")
    return resp["d"][0]["v"]["lp"]


# --------------------------- Orders ------------------------------

def place_market_order(side, qty):
    """side: 1 = buy, -1 = sell"""
    data = {"symbol": SYMBOL, "qty": qty, "type": 2, "side": side,
             "productType": "INTRADAY", "limitPrice": 0, "stopPrice": 0,
             "validity": "DAY", "disclosedQty": 0, "offlineOrder": False}
    resp = fyers.place_order(data=data)
    if resp.get("s") != "ok":
        raise RuntimeError(f"Order failed: {resp}")
    return resp


def log_trade(entry_time, side, entry_price, exit_time, exit_price, points, pnl, reason):
    new_file = not os.path.exists(TRADE_LOG_FILE)
    with open(TRADE_LOG_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["entry_time", "side", "entry_price", "exit_time", "exit_price", "points", "pnl", "reason"])
        w.writerow([entry_time, side, entry_price, exit_time, exit_price, round(points, 2), round(pnl, 2), reason])


# --------------------------- Strategy core ------------------------------

class State:
    def __init__(self):
        self.trades_today = 0
        self.daily_pnl = 0.0
        self.in_position = False
        self.side = None
        self.entry_price = None
        self.entry_time = None

    def can_trade(self):
        return self.trades_today < MAX_TRADES_PER_DAY and self.daily_pnl > -MAX_DAILY_LOSS


def check_entry(df_1min, trend):
    if trend == "NEUTRAL" or len(df_1min) < 3:
        return None
    last, prev = df_1min.iloc[-1], df_1min.iloc[-2]
    vwap = last["vwap"]

    if trend == "UP":
        touched = prev["low"] <= vwap + VWAP_TOUCH_TOLERANCE
        confirmed = last["close"] > last["open"] and last["close"] > vwap
        if touched and confirmed:
            return "LONG"

    if trend == "DOWN":
        touched = prev["high"] >= vwap - VWAP_TOUCH_TOLERANCE
        confirmed = last["close"] < last["open"] and last["close"] < vwap
        if touched and confirmed:
            return "SHORT"

    return None


def monitor_position(state):
    while state.in_position:
        now = datetime.now().strftime("%H:%M")
        ltp = get_ltp()
        points = (ltp - state.entry_price) if state.side == "LONG" else (state.entry_price - ltp)

        hit_target = points >= TARGET_POINTS
        hit_stop = points <= -STOP_LOSS_POINTS
        force_exit = now >= SQUARE_OFF_TIME

        if hit_target or hit_stop or force_exit:
            exit_side = -1 if state.side == "LONG" else 1
            place_market_order(exit_side, LOT_SIZE * NUM_LOTS)

            pnl = points * LOT_SIZE * NUM_LOTS
            reason = "TARGET" if hit_target else ("STOP_LOSS" if hit_stop else "SQUARE_OFF")
            log_trade(state.entry_time, state.side, state.entry_price,
                       datetime.now().strftime("%H:%M:%S"), ltp, points, pnl, reason)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] EXIT {state.side} at {ltp} "
                  f"| {points:.1f} pts | PnL: {pnl:.0f} | {reason}")

            state.daily_pnl += pnl
            state.in_position = False
            state.side = None
            return

        time.sleep(POLL_INTERVAL_SECONDS)


def run():
    state = State()
    print(f"Running VWAP scalper on {SYMBOL} | {LOT_SIZE}x{NUM_LOTS} | "
          f"SL {STOP_LOSS_POINTS} / TGT {TARGET_POINTS}")

    while True:
        now = datetime.now()
        now_str = now.strftime("%H:%M")

        if now_str < "09:16" or now_str > SQUARE_OFF_TIME:
            print(f"[{now.strftime('%H:%M:%S')}] Outside trading window "
                  f"(runs 09:16-{SQUARE_OFF_TIME} IST). Waiting...")
            time.sleep(30)
            continue

        if not state.can_trade():
            print(f"[{now.strftime('%H:%M:%S')}] Daily limit reached "
                  f"(trades: {state.trades_today}, pnl: {state.daily_pnl:.0f}). Standing down.")
            time.sleep(60)
            continue

        try:
            df_1min = compute_vwap(get_intraday_candles("1"))
            df_5min = get_intraday_candles("5")
            trend = determine_trend(df_5min)
            signal = check_entry(df_1min, trend)

            ltp_now = df_1min.iloc[-1]["close"]
            vwap_now = df_1min.iloc[-1]["vwap"]
            print(f"[{now.strftime('%H:%M:%S')}] Checking... LTP {ltp_now:.1f} | "
                  f"VWAP {vwap_now:.1f} | Trend: {trend} | Signal: {signal or 'none'} | "
                  f"Trades today: {state.trades_today}")

            if signal:
                side = 1 if signal == "LONG" else -1
                place_market_order(side, LOT_SIZE * NUM_LOTS)
                entry_price = get_ltp()

                state.in_position = True
                state.side = signal
                state.entry_price = entry_price
                state.entry_time = now.strftime("%H:%M:%S")
                state.trades_today += 1

                print(f"[{now.strftime('%H:%M:%S')}] ENTER {signal} at {entry_price} "
                      f"| trend {trend} | trade #{state.trades_today}")

                monitor_position(state)

        except Exception as e:
            print(f"[{now.strftime('%H:%M:%S')}] Error: {e}")

        time.sleep(POLL_INTERVAL_SECONDS)


from fastapi import FastAPI
import uvicorn
import os

app = FastAPI()

# Function that runs when server starts
def startup_function():
    print("🚀 Server Started Successfully")
    print("Running startup function...")

@app.on_event("startup")
async def startup_event():
    startup_function()
    run()

# API Endpoint
@app.get("/hello")
async def hello():
    return {"message": "Hello from FastAPI"}

if __name__ == "__main__":

    uvicorn.run(
        "Niftybankniftyvwapscalper:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )