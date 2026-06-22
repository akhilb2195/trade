from fyers_apiv3 import fyersModel
import creditials as cr
import pandas as pd
import pandas_ta as ta
import time
from datetime import datetime

# ── Auth ──────────────────────────────────────────────────────────────────────
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

fyers = fyersModel.FyersModel(client_id=cr.client_id, token=access_token, is_async=False, log_path="")

# ── Config ────────────────────────────────────────────────────────────────────
TOP_N            = 50       # top gainers + top losers
MOVE_THRESHOLD   = 3.0      # % move from open to qualify
RESOLUTION       = "15"     # intraday candle resolution (5 or 15 min)
BATCH_SIZE       = 50
SLEEP_BETWEEN    = 0.2

# ── Load stock list ───────────────────────────────────────────────────────────
with open("filtered_stocks.txt", "r") as f:
    lines = [l.strip() for l in f if l.strip() and not l.startswith(("FILTERED", "Generated", "Total", "="))]

stock_list = lines
print("\n" + "="*70)
print("OVERREACTION SCANNER — BUY / SELL CANDIDATES")
print("="*70)
print(f"Stocks loaded : {len(stock_list)}")
print(f"Resolution    : {RESOLUTION}-min candles")
print(f"Move threshold: >{MOVE_THRESHOLD}% from open")
print(f"Top N         : {TOP_N} gainers + {TOP_N} losers")
print("="*70 + "\n")


# ── Step 1: Fetch quotes in batches ───────────────────────────────────────────
print("Fetching quotes...")
quotes = {}

for i in range(0, len(stock_list), BATCH_SIZE):
    batch   = stock_list[i:i + BATCH_SIZE]
    symbols = ",".join([f"NSE:{s}-EQ" for s in batch])
    resp    = fyers.quotes(data={"symbols": symbols})

    if resp.get('s') != 'ok':
        print(f"  ⚠ Quote fetch failed for batch {i//BATCH_SIZE + 1}")
        continue

    for item in resp.get('d', []):
        if item.get('s') != 'ok':
            continue
        symbol = item['n'].replace('NSE:', '').replace('-EQ', '')
        v      = item['v']
        quotes[symbol] = {
            'symbol'    : symbol,
            'lp'        : v.get('lp', 0),
            'open'      : v.get('open_price', 0),
            'high'      : v.get('high_price', 0),
            'low'       : v.get('low_price', 0),
            'volume'    : v.get('volume', 0),
            'chp'       : v.get('chp', 0),       # % change from prev close
        }

    time.sleep(SLEEP_BETWEEN)

print(f"  ✓ {len(quotes)} quotes fetched\n")


# ── Step 2: Sort → top 50 gainers + top 50 losers ────────────────────────────
sorted_stocks = sorted(quotes.values(), key=lambda x: x['chp'], reverse=True)
candidates    = sorted_stocks[:TOP_N] + sorted_stocks[-TOP_N:]

gainers = sorted_stocks[:TOP_N]
losers  = sorted_stocks[-TOP_N:][::-1]

print("="*60)
print(f"TOP {TOP_N} GAINERS")
print("="*60)
print(f"  {'Symbol':<14} {'LTP':>8} {'Open':>8} {'%Change':>10}")
print("  " + "-"*44)
for s in gainers:
    print(f"  {s['symbol']:<14} {s['lp']:>8.2f} {s['open']:>8.2f} {s['chp']:>9.2f}%")

print("\n" + "="*60)
print(f"TOP {TOP_N} LOSERS")
print("="*60)
print(f"  {'Symbol':<14} {'LTP':>8} {'Open':>8} {'%Change':>10}")
print("  " + "-"*44)
for s in losers:
    print(f"  {s['symbol']:<14} {s['lp']:>8.2f} {s['open']:>8.2f} {s['chp']:>9.2f}%")
print()

print(f"Analysing {len(candidates)} candidates (top/bottom {TOP_N})...\n")


# ── Step 3: Fetch intraday candles + apply 3-point test ──────────────────────
today_start = int(datetime.now().replace(hour=9, minute=15, second=0, microsecond=0).timestamp())
today_end   = int(datetime.now().timestamp())

buy_candidates  = []
sell_candidates = []

def get_intraday(symbol: str) -> pd.DataFrame | None:
    data = {
        "symbol"     : f"NSE:{symbol}-EQ",
        "resolution" : RESOLUTION,
        "date_format": "0",
        "range_from" : str(today_start),
        "range_to"   : str(today_end),
        "cont_flag"  : "1"
    }
    resp = fyers.history(data=data)
    if resp.get('s') != 'ok' or 'candles' not in resp or len(resp['candles']) < 3:
        return None
    df = pd.DataFrame(resp['candles'], columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    return df


def volume_spike(df: pd.DataFrame, candle_type: str) -> bool:
    """True if any candle of given type (red/green) has volume > 1.5x avg."""
    avg_vol = df['volume'].mean()
    if candle_type == 'red':
        spike_candles = df[df['close'] < df['open']]
    else:
        spike_candles = df[df['close'] > df['open']]
    return bool((spike_candles['volume'] > avg_vol * 1.5).any())


for stock in candidates:
    symbol = stock['symbol']
    lp     = stock['lp']
    op     = stock['open']
    high   = stock['high']
    low    = stock['low']

    if op <= 0:
        continue

    pct_from_open = ((lp - op) / op) * 100
    day_range     = high - low

    if day_range <= 0:
        continue

    df = get_intraday(symbol)
    time.sleep(SLEEP_BETWEEN)

    if df is None:
        continue

    # ── BUY check (overreaction down) ────────────────────────────────────────
    if pct_from_open <= -MOVE_THRESHOLD:
        cond1 = True                                          # already checked above
        cond2 = lp > (low + 0.25 * day_range)               # closed above lowest 25%
        cond3 = volume_spike(df, 'red')                      # red candle volume spike



        if cond1 and cond2 and cond3:
            buy_candidates.append({
                **stock,
                'pct_from_open': round(pct_from_open, 2),
                'checks'       : f"Drop>{MOVE_THRESHOLD}% ✓ | Above low-25% ✓ | Vol spike ✓"
            })
            print(f"  📗 BUY  {symbol:<14} | Open:{op:.2f} → LTP:{lp:.2f} ({pct_from_open:.2f}%) | Vol:{stock['volume']:,}")

    # ── SELL check (overreaction up) ─────────────────────────────────────────
    elif pct_from_open >= MOVE_THRESHOLD:
        cond1 = True
        cond2 = lp < (high - 0.25 * day_range)              # closed below highest 25%
        cond3 = volume_spike(df, 'green')                    # green candle volume spike



        if cond1 and cond2 and cond3:
            sell_candidates.append({
                **stock,
                'pct_from_open': round(pct_from_open, 2),
                'checks'       : f"Rise>{MOVE_THRESHOLD}% ✓ | Below high-25% ✓ | Vol spike ✓"
            })
            print(f"  📕 SELL {symbol:<14} | Open:{op:.2f} → LTP:{lp:.2f} (+{pct_from_open:.2f}%) | Vol:{stock['volume']:,}")


# ── Results ───────────────────────────────────────────────────────────────────
def print_table(title: str, stocks: list, emoji: str):
    print("\n" + "="*80)
    print(f"{emoji}  {title}  ({len(stocks)} found)")
    print("="*80)
    if not stocks:
        print("  None found.")
        return
    stocks.sort(key=lambda x: abs(x['pct_from_open']), reverse=True)
    print(f"  {'Symbol':<14} {'LTP':>8} {'Open':>8} {'%Move':>8} {'Volume':>14}  Checks")
    print("  " + "-"*76)
    for s in stocks:
        print(f"  {s['symbol']:<14} {s['lp']:>8.2f} {s['open']:>8.2f} {s['pct_from_open']:>7.2f}%  {s['volume']:>13,}  {s['checks']}")
    print("="*80)

print_table("BUY CANDIDATES  — Overreaction Down (Mean Reversion Up)",  buy_candidates,  "📗")
print_table("SELL CANDIDATES — Overreaction Up   (Mean Reversion Down)", sell_candidates, "📕")

print(f"\n✅ Scan complete at {datetime.now().strftime('%H:%M:%S')}")
print(f"   BUY signals : {len(buy_candidates)}")
print(f"   SELL signals: {len(sell_candidates)}")

# ── Generate output txt ───────────────────────────────────────────────────────
with open("overreaction_signals.txt", "w") as f:
    f.write("BUY CANDIDATES\n")
    f.write("="*40 + "\n")
    for s in buy_candidates:
        f.write(f"{s['symbol']}\n")
    f.write("\nSELL CANDIDATES\n")
    f.write("="*40 + "\n")
    for s in sell_candidates:
        f.write(f"{s['symbol']}\n")
print("\n📄 Signals saved to: overreaction_signals.txt")