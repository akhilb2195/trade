from fyers_apiv3 import fyersModel
from fyers_apiv3.FyersWebsocket import data_ws
import creditials as cr
import time
import threading
from datetime import datetime, timedelta

# ── Auth ──────────────────────────────────────────────────────────────────────
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

client_id   = cr.client_id
fyers_http  = fyersModel.FyersModel(client_id=client_id, token=access_token, is_async=False, log_path="")
ws_token    = f"{client_id}:{access_token}"

# ── Config ────────────────────────────────────────────────────────────────────
QTY               = int(input("Enter quantity per trade (for testing): "))
WAIT_DEADLINE     = 10 * 60 + 30 * 60
TARGET_MULTIPLIER = 0.4
STOPLOSS_BUFFER   = 2.0
TIME_STOP_HOUR    = 13
EXIT_HOUR         = 14
EXIT_MINUTE       = 30

# ── Load BUY signals from txt ─────────────────────────────────────────────────
with open("overreaction_signals.txt", "r") as f:
    lines = [l.strip() for l in f]

buy_symbols  = []
sell_symbols = []
in_buy = in_sell = False
for line in lines:
    if line.startswith("BUY"):
        in_buy = True; in_sell = False; continue
    if line.startswith("SELL"):
        in_sell = True; in_buy = False; continue
    if line.startswith("=") or not line:
        continue
    if in_buy:
        buy_symbols.append(line)
    elif in_sell:
        sell_symbols.append(line)

print("\n" + "="*70)
print("NEXT DAY EXECUTION — BUY SIGNALS ONLY")
print("="*70)
print(f"Loaded {len(buy_symbols)} BUY symbols: {', '.join(buy_symbols)}")
print(f"Loaded {len(sell_symbols)} SELL symbols: {', '.join(sell_symbols)}")
print(f"Qty per trade : {QTY}")
print(f"Target        : Yesterday low + (range x {TARGET_MULTIPLIER})")
print(f"Stop Loss     : Yesterday low - Rs{STOPLOSS_BUFFER}")
print(f"Time stop     : 1:00 PM")
print(f"Force exit    : 2:30 PM")
print("="*70 + "\n")


# ── Step 1: Fetch yesterday's OHLC from history ───────────────────────────────
print("Fetching yesterday's OHLC...")

yesterday       = datetime.now() - timedelta(days=1)
range_from      = int(yesterday.replace(hour=0,  minute=0,  second=0).timestamp())
range_to        = int(yesterday.replace(hour=23, minute=59, second=59).timestamp())

stock_data = {}

all_symbols = [(s, 'BUY') for s in buy_symbols] + [(s, 'SELL') for s in sell_symbols]

for symbol, side in all_symbols:
    data = {
        "symbol"     : f"NSE:{symbol}-EQ",
        "resolution" : "D",
        "date_format": "0",
        "range_from" : str(range_from),
        "range_to"   : str(range_to),
        "cont_flag"  : "1"
    }
    resp = fyers_http.history(data=data)

    if resp.get('s') != 'ok' or not resp.get('candles'):
        print(f"  x {symbol}: could not fetch yesterday's data — skipping")
        continue

    candle     = resp['candles'][-1]
    prev_high  = candle[2]
    prev_low   = candle[3]
    prev_close = candle[4]
    day_range  = prev_high - prev_low

    if side == 'BUY':
        target   = round(prev_low  + (day_range * TARGET_MULTIPLIER), 2)
        stoploss = round(prev_low  - STOPLOSS_BUFFER, 2)
    else:
        target   = round(prev_high - (day_range * TARGET_MULTIPLIER), 2)
        stoploss = round(prev_high + STOPLOSS_BUFFER, 2)

    stock_data[symbol] = {
        'side'      : side,
        'prev_high' : prev_high,
        'prev_low'  : prev_low,
        'prev_close': prev_close,
        'day_range' : day_range,
        'target'    : target,
        'stoploss'  : stoploss,
        'open'      : None,
        'ltp'       : None,
        'entry_price': None,       # actual price at which order was placed
        'status'    : 'WAITING',
        'order_id'  : None,
        'exited'    : False,
        'candle_930': [],
    }
    print(f"  [{'BUY' if side=='BUY' else 'SELL'}] {symbol}: PrevHigh={prev_high} PrevLow={prev_low} PrevClose={prev_close} | Target={target} | SL={stoploss}")

print()

if not stock_data:
    print("No valid stocks to trade. Exiting.")
    exit()

# ── Event log for report ──────────────────────────────────────────────────────
event_log = []

def log_event(symbol: str, event: str, reason: str = "", price: float = 0):
    d = stock_data.get(symbol, {})
    event_log.append({
        'time'   : datetime.now().strftime('%H:%M:%S'),
        'symbol' : symbol,
        'side'   : d.get('side', '-'),
        'event'  : event,
        'reason' : reason,
        'price'  : price,
        'target' : d.get('target', 0),
        'sl'     : d.get('stoploss', 0),
    })


# ── Step 2: Order placement helpers ──────────────────────────────────────────
def place_exit_order(symbol: str, reason: str):
    if stock_data[symbol].get('exited'):
        return
    order_data = {
        "symbol"       : f"NSE:{symbol}-EQ",
        "qty"          : QTY,
        "type"         : 2,
        "side"         : -1,
        "productType"  : "INTRADAY",
        "limitPrice"   : 0,
        "stopPrice"    : 0,
        "validity"     : "DAY",
        "disclosedQty" : 0,
        "offlineOrder" : False,
        "orderTag"     : "overreactionexit",
        "isSliceOrder" : False
    }
    resp = fyers_http.place_order(data=order_data)
    if resp.get('s') == 'ok':
        stock_data[symbol]['exited'] = True
        ltp = stock_data[symbol]['ltp'] or 0
        print(f"\n  EXIT ORDER PLACED — {symbol} | Reason: {reason} | Order ID: {resp.get('id', 'N/A')}")
        log_event(symbol, 'EXIT', reason, ltp)
    else:
        print(f"\n  EXIT FAILED — {symbol} | Reason: {reason} | Response: {resp}")
        log_event(symbol, 'EXIT FAILED', reason, stock_data[symbol]['ltp'] or 0)


def place_buy_order(symbol: str):
    order_data = {
        "symbol"       : f"NSE:{symbol}-EQ",
        "qty"          : QTY,
        "type"         : 2,
        "side"         : 1,
        "productType"  : "INTRADAY",
        "limitPrice"   : 0,
        "stopPrice"    : 0,
        "validity"     : "DAY",
        "disclosedQty" : 0,
        "offlineOrder" : False,
        "orderTag"     : "overreactionbuy",
        "isSliceOrder" : False
    }
    resp = fyers_http.place_order(data=order_data)
    if resp.get('s') == 'ok':
        order_id = resp.get('id', 'N/A')
        ltp = stock_data[symbol]['ltp'] or 0
        stock_data[symbol]['order_id']    = order_id
        stock_data[symbol]['status']      = 'ORDERED'
        stock_data[symbol]['entry_price'] = ltp
        print(f"\n  ORDER PLACED — {symbol} | Qty:{QTY} | Order ID:{order_id}")
        print(f"     Entry : Rs{ltp} | Target : Rs{stock_data[symbol]['target']} | SL : Rs{stock_data[symbol]['stoploss']}")
        log_event(symbol, 'BUY ENTRY', f"Order ID: {order_id}", ltp)
    else:
        print(f"\n  ORDER FAILED — {symbol} | Response: {resp}")
        log_event(symbol, 'BUY ENTRY FAILED', str(resp), stock_data[symbol]['ltp'] or 0)


def place_sell_entry_order(symbol: str):
    """SELL entry — real money, no mock"""
    order_data = {
        "symbol"       : f"NSE:{symbol}-EQ",
        "qty"          : QTY,
        "type"         : 2,
        "side"         : -1,
        "productType"  : "INTRADAY",
        "limitPrice"   : 0,
        "stopPrice"    : 0,
        "validity"     : "DAY",
        "disclosedQty" : 0,
        "offlineOrder" : False,
        "orderTag"     : "overreactionsell",
        "isSliceOrder" : False
    }
    resp = fyers_http.place_order(data=order_data)
    if resp.get('s') == 'ok':
        order_id = resp.get('id', 'N/A')
        ltp = stock_data[symbol]['ltp'] or 0
        stock_data[symbol]['order_id']    = order_id
        stock_data[symbol]['status']      = 'ORDERED'
        stock_data[symbol]['entry_price'] = ltp
        print(f"\n  SELL ENTRY PLACED — {symbol} | Qty:{QTY} | Order ID:{order_id}")
        print(f"     Entry : Rs{ltp} | Target : Rs{stock_data[symbol]['target']} | SL : Rs{stock_data[symbol]['stoploss']}")
        log_event(symbol, 'SELL ENTRY', f"Order ID: {order_id}", ltp)
    else:
        print(f"\n  SELL ENTRY FAILED — {symbol} | Response: {resp}")
        log_event(symbol, 'SELL ENTRY FAILED', str(resp), stock_data[symbol]['ltp'] or 0)


def place_sell_exit_order(symbol: str, reason: str):
    """Exit a SELL position by buying back"""
    if stock_data[symbol].get('exited'):
        return
    order_data = {
        "symbol"       : f"NSE:{symbol}-EQ",
        "qty"          : QTY,
        "type"         : 2,
        "side"         : 1,           # BUY to cover short
        "productType"  : "INTRADAY",
        "limitPrice"   : 0,
        "stopPrice"    : 0,
        "validity"     : "DAY",
        "disclosedQty" : 0,
        "offlineOrder" : False,
        "orderTag"     : "overreactionsellexit",
        "isSliceOrder" : False
    }
    resp = fyers_http.place_order(data=order_data)
    if resp.get('s') == 'ok':
        stock_data[symbol]['exited'] = True
        ltp = stock_data[symbol]['ltp'] or 0
        print(f"\n  SELL EXIT PLACED — {symbol} | Reason: {reason} | Order ID: {resp.get('id', 'N/A')}")
        log_event(symbol, 'SELL EXIT', reason, ltp)
    else:
        print(f"\n  SELL EXIT FAILED — {symbol} | Reason: {reason} | Response: {resp}")
        log_event(symbol, 'SELL EXIT FAILED', reason, stock_data[symbol]['ltp'] or 0)


# ── Step 3: Entry logic ───────────────────────────────────────────────────────
def check_entry(symbol: str, ltp: float):
    now    = datetime.now()
    hour   = now.hour
    minute = now.minute
    data   = stock_data[symbol]
    side   = data['side']

    # ── Force exit at 2:30 PM ────────────────────────────────────────────────
    if hour > EXIT_HOUR or (hour == EXIT_HOUR and minute >= EXIT_MINUTE):
        if data['status'] == 'ORDERED' and not data['exited']:
            if side == 'BUY':
                place_exit_order(symbol, "2:30 PM force exit")
            else:
                place_sell_exit_order(symbol, "2:30 PM force exit")
        return

    # ── Target / SL check on every tick after order placed ───────────────────
    if data['status'] == 'ORDERED' and not data.get('exited'):
        if side == 'BUY':
            if ltp >= data['target']:
                place_exit_order(symbol, f"Target hit Rs{data['target']}")
                return
            if ltp <= data['stoploss']:
                place_exit_order(symbol, f"Stop loss hit Rs{data['stoploss']}")
                return
        else:  # SELL
            if ltp <= data['target']:
                place_sell_exit_order(symbol, f"Target hit Rs{data['target']}")
                return
            if ltp >= data['stoploss']:
                place_sell_exit_order(symbol, f"Stop loss hit Rs{data['stoploss']}")
                return

    # ── Time stop — skip if no entry by 1 PM ─────────────────────────────────
    if hour >= TIME_STOP_HOUR and data['status'] not in ('ORDERED',):
        if data['status'] != 'TIME_STOP':
            print(f"\n  1:00 PM time stop — {symbol} [{side}] SKIPPED (no entry triggered)")
            data['status'] = 'TIME_STOP'
            log_event(symbol, 'REJECTED — TIME STOP', 'No entry triggered by 1:00 PM', ltp)
        return

    # ── 9:15–9:30 → DO NOTHING ───────────────────────────────────────────────
    if hour == 9 and minute < 30:
        if data['open'] is None:
            data['open'] = ltp
        return

    # ── 9:30 onwards → check open behaviour ──────────────────────────────────
    if data['open'] is None:
        data['open'] = ltp

    data['ltp']  = ltp
    open_price   = data['open']
    prev_close   = data['prev_close']
    open_chg_pct = ((open_price - prev_close) / prev_close) * 100

    if data['status'] == 'WAITING':
        if side == 'BUY':
            if open_chg_pct > 1.0:
                data['status'] = 'WAIT_PULLBACK'
                print(f"  {symbol} [BUY]: Gap up {open_chg_pct:.2f}% — WAITING for pullback (deadline 10:30 AM)")
                log_event(symbol, 'WAIT — GAP UP', f"Open {open_chg_pct:.2f}% above prev close", ltp)
            elif ltp < open_price and ((ltp - open_price) / open_price * 100) < -1.0:
                data['status'] = 'AVOID'
                print(f"  {symbol} [BUY]: Price continues falling — AVOID")
                log_event(symbol, 'REJECTED — AVOID', 'Price continues falling at open', ltp)
            else:
                data['status'] = 'WATCH'
                print(f"  {symbol} [BUY]: Opens flat/down {open_chg_pct:.2f}% — watching for 5-min green candle after 9:30")
        else:  # SELL
            if open_chg_pct < -1.0:
                data['status'] = 'WAIT_PULLBACK'
                print(f"  {symbol} [SELL]: Gap down {open_chg_pct:.2f}% — WAITING for bounce (deadline 10:30 AM)")
                log_event(symbol, 'WAIT — GAP DOWN', f"Open {open_chg_pct:.2f}% below prev close", ltp)
            elif ((ltp - open_price) / open_price * 100) > 1.0:
                data['status'] = 'AVOID'
                print(f"  {symbol} [SELL]: Price continues rising — AVOID")
                log_event(symbol, 'REJECTED — AVOID', 'Price continues rising at open', ltp)
            else:
                data['status'] = 'WATCH'
                print(f"  {symbol} [SELL]: Opens flat/up {open_chg_pct:.2f}% — watching for 5-min red candle after 9:30")

    # ── WATCH → collect 9:30–9:35 candle, buy/sell on candle close ───────────
    if data['status'] == 'WATCH':
        if hour == 9 and 30 <= minute < 35:
            data['candle_930'].append(ltp)
        elif hour == 9 and minute >= 35 and data['candle_930']:
            candle_open  = data['candle_930'][0]
            candle_close = data['candle_930'][-1]
            if side == 'BUY':
                if candle_close > candle_open:
                    print(f"\n  {symbol} [BUY]: 9:30 candle CLOSED GREEN ({candle_open:.2f} -> {candle_close:.2f}) — BUYING")
                    place_buy_order(symbol)
                else:
                    data['status'] = 'AVOID'
                    print(f"  {symbol} [BUY]: 9:30 candle closed RED — AVOID")
                    log_event(symbol, 'REJECTED — CANDLE', f'9:30 candle RED ({candle_open:.2f}->{candle_close:.2f})', ltp)
            else:  # SELL
                if candle_close < candle_open:
                    print(f"\n  {symbol} [SELL]: 9:30 candle CLOSED RED ({candle_open:.2f} -> {candle_close:.2f}) — SELLING")
                    place_sell_entry_order(symbol)
                else:
                    data['status'] = 'AVOID'
                    print(f"  {symbol} [SELL]: 9:30 candle closed GREEN — AVOID")
                    log_event(symbol, 'REJECTED — CANDLE', f'9:30 candle GREEN ({candle_open:.2f}->{candle_close:.2f})', ltp)
            data['candle_930'] = []

    # ── WAIT_PULLBACK → check if price pulled back near prev_close ───────────
    if data['status'] == 'WAIT_PULLBACK':
        if hour >= 10 and minute >= 30:
            data['status'] = 'AVOID'
            print(f"  {symbol} [{side}]: No pullback by 10:30 AM — SKIP")
            log_event(symbol, 'REJECTED — NO PULLBACK', 'No pullback/bounce by 10:30 AM', ltp)
            return
        if side == 'BUY':
            pullback_threshold = prev_close * 1.005
            if ltp <= pullback_threshold:
                data['status'] = 'WATCH'
                print(f"  {symbol} [BUY]: Pullback detected at Rs{ltp:.2f} — watching for green candle")
        else:
            pullback_threshold = prev_close * 0.995
            if ltp >= pullback_threshold:
                data['status'] = 'WATCH'
                print(f"  {symbol} [SELL]: Bounce detected at Rs{ltp:.2f} — watching for red candle")


# ── Step 4: WebSocket setup ───────────────────────────────────────────────────
ws_symbols = [f"NSE:{s}-EQ" for s in stock_data.keys()]

def onmessage(message):
    symbol_full = message.get('symbol', '')
    ltp         = message.get('ltp', None)
    if not symbol_full or ltp is None:
        return
    symbol = symbol_full.replace('NSE:', '').replace('-EQ', '')
    if symbol in stock_data:
        check_entry(symbol, ltp)

def onerror(message):
    print(f"WebSocket error: {message}")

def onclose(message):
    print(f"WebSocket closed: {message}")

def onopen():
    fyers_ws.subscribe(symbols=ws_symbols, data_type="SymbolUpdate")
    fyers_ws.keep_running()

fyers_ws = data_ws.FyersDataSocket(
    access_token  = ws_token,
    log_path      = "",
    litemode      = True,
    write_to_file = False,
    reconnect     = True,
    on_connect    = onopen,
    on_close      = onclose,
    on_error      = onerror,
    on_message    = onmessage
)

# ── Step 5: Summary printer (every 5 min in background) ──────────────────────
def print_summary():
    while True:
        time.sleep(300)
        now = datetime.now()
        if now.hour >= EXIT_HOUR and now.minute >= EXIT_MINUTE:
            break
        print("\n" + "-"*70)
        print(f"STATUS UPDATE — {now.strftime('%H:%M:%S')}")
        print(f"  {'Symbol':<12} {'Side':<6} {'Status':<18} {'LTP':>8} {'Target':>8} {'SL':>8} {'OrderID'}")
        print("  " + "-"*66)
        for sym, d in stock_data.items():
            ltp_str = f"Rs{d['ltp']:.2f}" if d['ltp'] else "—"
            oid     = d['order_id'] or "—"
            print(f"  {sym:<12} {d['side']:<6} {d['status']:<18} {ltp_str:>8} Rs{d['target']:>7} Rs{d['stoploss']:>7} {oid}")
        print("-"*70 + "\n")

threading.Thread(target=print_summary, daemon=True).start()

# ── Connect ───────────────────────────────────────────────────────────────────
print("="*70)
print(f"Connecting WebSocket — monitoring {len(ws_symbols)} stocks...")
print("9:15-9:30 -> DO NOTHING  |  9:30 -> Entry check begins")
print("="*70 + "\n")
fyers_ws.connect()


# ── Daily report (runs after WebSocket disconnects at EOD) ───────────────────
def generate_report() -> str:
    today = datetime.now().strftime('%Y-%m-%d')
    lines = []
    lines.append(f"DAILY TRADING REPORT — {today}")
    lines.append("=" * 70)

    lines.append("\nSTOCK SUMMARY")
    lines.append("-" * 70)
    for sym, d in stock_data.items():
        lines.append(f"\n  {sym} [{d['side']}]")
        lines.append(f"    PrevHigh   : Rs{d['prev_high']}   PrevLow  : Rs{d['prev_low']}")
        lines.append(f"    PrevClose  : Rs{d['prev_close']}")
        lines.append(f"    Target     : Rs{d['target']}      SL       : Rs{d['stoploss']}")
        entry = f"Rs{d['entry_price']:.2f}" if d['entry_price'] else "Not entered"
        lines.append(f"    Entry Price: {entry}")
        lines.append(f"    Status     : {d['status']}{'  (EXITED)' if d['exited'] else ''}")
        lines.append(f"    Order ID   : {d['order_id'] or 'None'}")

    lines.append("\n\nDETAILED EVENT LOG")
    lines.append("-" * 70)
    lines.append(f"  {'Time':<10} {'Symbol':<13} {'Side':<6} {'Event':<30} {'Price':>9}  Reason")
    lines.append("  " + "-"*70)
    for e in event_log:
        lines.append(
            f"  {e['time']:<10} {e['symbol']:<13} {e['side']:<6} "
            f"{e['event']:<30} Rs{e['price']:>8.2f}  {e['reason']}"
        )

    entries  = [e for e in event_log if 'ENTRY' in e['event'] and 'FAIL' not in e['event']]
    exits    = [e for e in event_log if 'EXIT' in e['event'] and 'FAIL' not in e['event']]
    rejected = [e for e in event_log if 'REJECTED' in e['event']]
    waited   = [e for e in event_log if 'WAIT' in e['event']]

    lines.append("\n\nSUMMARY")
    lines.append("-" * 40)
    lines.append(f"  Total stocks loaded  : {len(stock_data)}")
    lines.append(f"  BUY stocks           : {len(buy_symbols)}")
    lines.append(f"  SELL stocks          : {len(sell_symbols)}")
    lines.append(f"  Entries placed       : {len(entries)}")
    lines.append(f"  Exits placed         : {len(exits)}")
    lines.append(f"  Rejected / Avoided   : {len(rejected)}")
    lines.append(f"  Waited (gap)         : {len(waited)}")

    if rejected:
        lines.append("\nREJECTION DETAILS")
        lines.append("-" * 40)
        for e in rejected:
            lines.append(f"  {e['symbol']} [{e['side']}] at {e['time']}")
            lines.append(f"    Reason : {e['event']} — {e['reason']}")
            lines.append(f"    Price at rejection : Rs{e['price']:.2f}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def save_report():
    report = generate_report()
    today  = datetime.now().strftime('%Y-%m-%d')
    fname  = f"report_{today}.txt"
    with open(fname, "w", encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to: {fname}")


save_report()