import os
import sys
import time
import json
import logging
import datetime
import traceback
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

# Fyers API
from fyers_apiv3 import fyersModel

# Import your credentials file (create cr.py with client_id, secret_key, etc.)
try:
    import creditials as cr
except ImportError:
    print("ERROR: Create a credentials.py file with client_id, secret_key, and redirect_uri.")
    sys.exit(1)

# ========================= CONFIGURATION =========================
SYMBOL = "NSE:YESBANK-EQ"           # Yes Bank
QUANTITY = 3000                     # Number of shares per trade (adjust based on capital)
RISK_PER_TRADE_PERCENT = 1.0        # 1% of capital risk per trade
CAPITAL = 68000                    # Total trading capital (₹2 lakhs)
MAX_TRADES_PER_DAY = 8
DAILY_LOSS_LIMIT_PERCENT = 2.0      # Stop trading if loss exceeds 2% of capital

# Indicator parameters
FAST_EMA = 9
SLOW_EMA = 21
TIMEFRAME_5MIN = "5"                # Fyers interval: 5 = 5 minutes
TIMEFRAME_1MIN = "1"                # 1 minute

# Order constants (from Fyers docs)
LIMIT_ORDER = 1
MARKET_ORDER = 2
STOP_ORDER = 3
STOP_LIMIT = 4
BUY = 1
SELL = -1
INTRADAY = "INTRADAY"
CNC = "CNC"
DAY_VALIDITY = "DAY"

# ========================= LOGGING SETUP =========================
log_filename = f"yesbank_scalper_{datetime.datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ========================= FYERS AUTHENTICATION =========================
def authenticate_fyers() -> fyersModel.FyersModel:
    """Authenticate using saved access token or generate new one."""
    # Try to read access token from file
    token_file = "access_token.txt"
    if os.path.exists(token_file):
        with open(token_file, "r") as f:
            access_token = f.read().strip()
        logger.info("Loaded access token from file.")
    else:
        # If no token file, we need to generate one (you must have already done the auth flow)
        # For production, you should store the token securely.
        logger.error("No access_token.txt found. Please run authentication flow first.")
        sys.exit(1)

    fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")
    # Verify token by fetching profile
    try:
        profile = fyers.get_profile()
        if profile.get("code") != 200:
            raise Exception(f"Auth failed: {profile}")
        logger.info(f"Authenticated successfully. User: {profile.get('data', {}).get('user_name')}")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        sys.exit(1)
    return fyers

# ========================= DATA FETCHING & INDICATORS =========================
def get_historical_candles(fyers: fyersModel.FyersModel, symbol: str, timeframe: str, days_back: int = 5) -> pd.DataFrame:
    """
    Fetch historical candles from Fyers.
    Returns DataFrame with columns: datetime, open, high, low, close, volume.
    """
    # Calculate from_date (today - days_back)
    to_date = datetime.datetime.now()
    from_date = to_date - datetime.timedelta(days=days_back)
    data = {
        "symbol": symbol,
        "resolution": timeframe,
        "date_format": "1",
        "range_from": from_date.strftime("%Y-%m-%d"),
        "range_to": to_date.strftime("%Y-%m-%d"),
        "cont_flag": "1"
    }
    try:
        response = fyers.history(data=data)
        if response.get("code") != 200:
            raise Exception(f"History API error: {response}")
        candles = response.get("candles", [])
        if not candles:
            raise Exception("No candles returned.")
        df = pd.DataFrame(candles, columns=["datetime", "open", "high", "low", "close", "volume"])
        df["datetime"] = pd.to_datetime(df["datetime"], unit="s")
        return df
    except Exception as e:
        logger.error(f"Failed to fetch historical data: {e}")
        raise

def compute_ema(df: pd.DataFrame, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return df["close"].ewm(span=period, adjust=False).mean()

def compute_vwap(df: pd.DataFrame) -> pd.Series:
    """Volume Weighted Average Price (typical price * volume) / cumulative volume."""
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
    cumulative_vol = df["volume"].cumsum()
    vwap = cumulative_tp_vol / cumulative_vol
    return vwap

def get_premarket_bias(fyers: fyersModel.FyersModel) -> Tuple[str, float, float]:
    """
    Determine daily bias using 5-min chart from 9:15 to 9:30.
    Returns ('bullish' or 'bearish', current_price, vwap_value).
    """
    # Fetch today's 5-min candles (from 9:15 to 9:30)
    now = datetime.datetime.now()
    # If before 9:30, wait
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    if now < market_open:
        logger.info("Market not open yet. Waiting for 9:15 AM...")
        time.sleep((market_open - now).total_seconds())
    
    # Fetch last 30 minutes of 5-min data (6 candles)
    df_5min = get_historical_candles(fyers, SYMBOL, TIMEFRAME_5MIN, days_back=1)
    # Filter today's data after 9:15
    today = now.date()
    df_today = df_5min[df_5min["datetime"].dt.date == today]
    df_pre = df_today[df_today["datetime"].dt.time <= datetime.time(9, 30)]
    if df_pre.empty:
        logger.warning("No pre-market data found. Using last 5-min candle.")
        df_pre = df_today.tail(1)
    
    # Compute EMAs and VWAP on the pre-market data
    df_pre["ema9"] = compute_ema(df_pre, FAST_EMA)
    df_pre["ema21"] = compute_ema(df_pre, SLOW_EMA)
    df_pre["vwap"] = compute_vwap(df_pre)
    
    last_row = df_pre.iloc[-1]
    current_price = last_row["close"]
    vwap_val = last_row["vwap"]
    ema9_val = last_row["ema9"]
    ema21_val = last_row["ema21"]
    
    # Bias determination
    if ema9_val > ema21_val and current_price > vwap_val:
        bias = "bullish"
    elif ema9_val < ema21_val and current_price < vwap_val:
        bias = "bearish"
    else:
        # Neutral / range-bound day – default to scalping both sides but with caution
        bias = "neutral"
    
    logger.info(f"Pre-market bias: {bias.upper()} (EMA9={ema9_val:.2f}, EMA21={ema21_val:.2f}, VWAP={vwap_val:.2f}, LTP={current_price:.2f})")
    return bias, current_price, vwap_val

def get_live_1min_candle(fyers: fyersModel.FyersModel, retries=3) -> Optional[pd.DataFrame]:
    """Fetch the latest completed 1-min candle."""
    for _ in range(retries):
        try:
            # Fetch last 2 minutes to be safe
            df = get_historical_candles(fyers, SYMBOL, TIMEFRAME_1MIN, days_back=1)
            if df.empty:
                time.sleep(2)
                continue
            # Return only the last completed candle (most recent minute)
            return df.iloc[-1:]
        except Exception as e:
            logger.warning(f"Error fetching 1-min candle: {e}. Retrying...")
            time.sleep(1)
    return None

def check_pullback_entry(df_1min: pd.DataFrame, bias: str) -> Tuple[bool, str, float]:
    """
    Check if the last 1-min candle forms a valid pullback entry.
    Returns (signal, side, entry_price).
    side: "BUY" or "SELL"
    """
    if len(df_1min) < 2:
        return False, "", 0.0
    
    # Compute EMAs on the fly (need at least 21 candles)
    if len(df_1min) < SLOW_EMA:
        return False, "", 0.0
    
    df = df_1min.copy()
    df["ema9"] = compute_ema(df, FAST_EMA)
    df["ema21"] = compute_ema(df, SLOW_EMA)
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    price = last["close"]
    ema9 = last["ema9"]
    ema21 = last["ema21"]
    
    # Bullish entry: price pulled back to touch EMA9/21, then closed above EMA9
    if bias in ("bullish", "neutral"):
        # Condition: previous candle low <= ema9 (or close to it) and current close > ema9
        if prev["low"] <= ema9 and price > ema9 and price > ema21:
            return True, "BUY", price
    
    # Bearish entry: price rallied to EMA9/21, then closed below EMA9
    if bias in ("bearish", "neutral"):
        if prev["high"] >= ema9 and price < ema9 and price < ema21:
            return True, "SELL", price
    
    return False, "", 0.0

# ========================= ORDER MANAGEMENT =========================
def place_bracket_order(fyers: fyersModel.FyersModel, side: str, entry_price: float, sl_price: float, target_price: float) -> Dict:
    """
    Place a bracket order (entry + SL + target) using Fyers' Bracket Order type.
    Note: Fyers supports BO with productType "BO". We'll use regular order + separate SL-M and limit target.
    Alternative: Use single order with stop-loss and target via "type": 5 (bracket order) if available.
    Here we use separate orders for simplicity (not atomic but works).
    """
    qty = QUANTITY
    if side == "BUY":
        # Entry market buy
        entry_order = {
            "symbol": SYMBOL,
            "qty": qty,
            "type": MARKET_ORDER,
            "side": BUY,
            "productType": INTRADAY,
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": DAY_VALIDITY,
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag": "scalp_entry",
            "isSliceOrder": False
        }
        # Stop-loss (sell) at sl_price
        sl_order = {
            "symbol": SYMBOL,
            "qty": qty,
            "type": STOP_ORDER,
            "side": SELL,
            "productType": INTRADAY,
            "limitPrice": 0,
            "stopPrice": sl_price,
            "validity": DAY_VALIDITY,
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag": "scalp_stoploss",
            "isSliceOrder": False
        }
        # Target (sell limit)
        target_order = {
            "symbol": SYMBOL,
            "qty": qty,
            "type": LIMIT_ORDER,
            "side": SELL,
            "productType": INTRADAY,
            "limitPrice": target_price,
            "stopPrice": 0,
            "validity": DAY_VALIDITY,
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag": "scalp_target",
            "isSliceOrder": False
        }
    else:  # SELL
        entry_order = {
            "symbol": SYMBOL,
            "qty": qty,
            "type": MARKET_ORDER,
            "side": SELL,
            "productType": INTRADAY,
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": DAY_VALIDITY,
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag": "scalp_entry",
            "isSliceOrder": False
        }
        sl_order = {
            "symbol": SYMBOL,
            "qty": qty,
            "type": STOP_ORDER,
            "side": BUY,
            "productType": INTRADAY,
            "limitPrice": 0,
            "stopPrice": sl_price,
            "validity": DAY_VALIDITY,
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag": "scalp_stoploss",
            "isSliceOrder": False
        }
        target_order = {
            "symbol": SYMBOL,
            "qty": qty,
            "type": LIMIT_ORDER,
            "side": BUY,
            "productType": INTRADAY,
            "limitPrice": target_price,
            "stopPrice": 0,
            "validity": DAY_VALIDITY,
            "disclosedQty": 0,
            "offlineOrder": False,
            "orderTag": "scalp_target",
            "isSliceOrder": False
        }
    
    # Place entry order
    entry_resp = fyers.place_order(data=entry_order)
    logger.info(f"Entry order response: {entry_resp}")
    if entry_resp.get("code") != 200:
        raise Exception(f"Entry order failed: {entry_resp}")
    order_id = entry_resp.get("id")
    
    # Place SL and target orders (they will remain pending until entry fills)
    sl_resp = fyers.place_order(data=sl_order)
    target_resp = fyers.place_order(data=target_order)
    logger.info(f"SL order: {sl_resp}, Target order: {target_resp}")
    
    return {"entry_id": order_id, "sl_resp": sl_resp, "target_resp": target_resp}

def calculate_position_size(entry_price: float, stop_loss_price: float, capital: float, risk_percent: float) -> int:
    """Calculate number of shares based on risk per trade."""
    risk_amount = capital * (risk_percent / 100.0)
    sl_points = abs(entry_price - stop_loss_price)
    if sl_points <= 0:
        return QUANTITY  # fallback
    qty = int(risk_amount / sl_points)
    # Ensure minimum lot size (1 share) and not exceed reasonable limit
    qty = max(1, min(qty, 50000))  # cap at 50k shares
    return qty

# ========================= MAIN TRADING LOOP =========================
def run_scalper():
    logger.info("Starting Yes Bank Scalper Strategy")
    fyers = authenticate_fyers()
    
    # Get daily bias (waits until 9:30 AM if needed)
    bias, current_price, vwap = get_premarket_bias(fyers)
    
    # Initialize daily metrics
    trades_today = 0
    daily_pnl = 0.0
    daily_loss_limit = CAPITAL * (DAILY_LOSS_LIMIT_PERCENT / 100.0)
    
    # Main loop: run from 9:45 AM to 3:20 PM (avoid last 10 minutes)
    end_time = datetime.time(15, 20)
    while True:
        now = datetime.datetime.now()
        if now.time() > end_time:
            logger.info("Market closing soon. Stopping scalper.")
            break
        if trades_today >= MAX_TRADES_PER_DAY:
            logger.info(f"Reached max trades per day ({MAX_TRADES_PER_DAY}). Stopping.")
            break
        if daily_pnl <= -daily_loss_limit:
            logger.warning(f"Daily loss limit reached ({daily_pnl:.2f} <= -{daily_loss_limit:.2f}). Stopping.")
            break
        
        # Wait for next minute boundary (poll every 2 seconds to align with new candle)
        current_second = now.second
        if current_second < 55:
            time.sleep(2)
            continue
        
        # Fetch latest 1-min candle data (enough to compute EMAs)
        df_1min = get_live_1min_candle(fyers)
        if df_1min is None:
            logger.warning("No 1-min data. Retrying in 5 sec.")
            time.sleep(5)
            continue
        
        # Check for entry signal
        signal, side, entry_price = check_pullback_entry(df_1min, bias)
        if not signal:
            # No signal, continue
            time.sleep(2)
            continue
        
        logger.info(f"Signal detected: {side} at {entry_price}")
        
        # Determine stop-loss and target based on ATR or fixed points
        # For simplicity, use fixed 0.25 points for Yes Bank (adjust based on volatility)
        sl_points = 0.25
        target_points = 0.35  # 1:1.4 risk-reward
        
        sl_price = entry_price - sl_points if side == "BUY" else entry_price + sl_points
        target_price = entry_price + target_points if side == "BUY" else entry_price - target_points
        
        # Calculate dynamic quantity based on risk
        qty = calculate_position_size(entry_price, sl_price, CAPITAL, RISK_PER_TRADE_PERCENT)
        global QUANTITY
        QUANTITY = qty
        logger.info(f"Position size: {qty} shares. SL: {sl_price}, Target: {target_price}")
        
        # Place orders
        try:
            order_result = place_bracket_order(fyers, side, entry_price, sl_price, target_price)
            trades_today += 1
            # Note: actual P&L will be known after orders fill. For simplicity, we assume execution.
            # In a real system, you would track order status via webhook or polling.
            logger.info(f"Trade placed. Trade count today: {trades_today}")
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            traceback.print_exc()
        
        # Wait for at least 1 minute before next signal to avoid multiple entries on same candle
        time.sleep(60)
    
    logger.info("Scalper finished for the day.")
    logger.info(f"Total trades: {trades_today}, Estimated P&L: {daily_pnl:.2f}")

if __name__ == "__main__":
    try:
        run_scalper()
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        traceback.print_exc()