from fyers_apiv3 import fyersModel
import creditials as cr
import json
import time
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

# Read credentials from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

client_id = cr.client_id

# Initialize Fyers
fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, is_async=False, log_path="")

# Your Nifty 500 stocks list
stock_list = [
    "RELIANCE", "SBIN", "HDFCBANK", "INDIGO", "ICICIBANK", "ONGC", "LT", "JWL", "BHARTIARTL", "MCX",
    "BEL", "BSE", "ETERNAL", "TATASTEEL", "MARUTI", "MAZDOCK", "AXISBANK", "DATAPATTNS", "SHRIRAMFIN", "BPCL",
    "HINDPETRO", "INFY", "COALINDIA", "M&M", "NETWEB", "HINDALCO", "OIL", "BAJFINANCE", "IOC", "NATIONALUM",
    "VEDL", "TEJASNET", "TCS", "HAL", "ADANIPORTS", "SUNPHARMA", "ASIANPAINT", "KOTAKBANK", "POWERGRID", "JIOFIN",
    "SOLARINDS", "DIXON", "TMPV", "NTPC", "PRAJIND", "ASHOKLEY", "IDEA", "EICHERMOT", "HINDCOPPER", "CANBK",
    "POLYCAB", "MRPL", "BANKBARODA", "POWERINDIA", "ITC", "ULTRACEMCO", "PERSISTENT", "LTFOODS", "IDFCFIRSTB", "PETRONET",
    "GRSE", "PFC", "HINDZINC", "UNIONBANK", "BDL", "CHENNPETRO", "KAYNES", "ADANIENT", "ASTERDM", "PNB",
    "SUZLON", "MAHABANK", "CDSL", "TRENT", "JSWSTEEL", "TVSMOTOR", "NMDC", "FEDERALBNK", "PAYTM", "HDFCLIFE",
    "DMART", "DLF", "FORCEMOT", "GRASIM", "WAAREEENER", "MANKIND", "RECLTD", "GAIL", "YESBANK", "HCLTECH",
    "BAJAJ-AUTO", "DRREDDY", "UPL", "INDUSINDBK", "SAIL", "WIPRO", "HINDUNILVR", "INDHOTEL", "AMBUJACEM", "COFORGE",
    "BANKINDIA", "MUTHOOTFIN", "POLICYBZR", "ADANIPOWER", "AUBANK", "TATAPOWER", "RVNL", "BANDHANBNK", "MAXHEALTH", "CGPOWER",
    "ANGELONE", "MOTHERSON", "TORNTPHARM", "APOLLOHOSP", "BHEL", "RBLBANK", "VBL", "INDIANB", "TITAN", "ADANIGREEN",
    "CHOLAFIN", "JINDALSTEL", "CAMS", "IRFC", "BALRAMCHIN", "IDBI", "BAJAJFINSV", "HEROMOTOCO", "360ONE", "JKTYRE",
    "LUPIN", "GODREJPROP", "LAURUSLABS", "KEI", "CIPLA", "JSWENERGY", "SYRMA", "BHARATFORG", "NATCOPHARM", "KPITTECH",
    "NESTLEIND", "SBILIFE", "NHPC", "ABB", "HAVELLS", "CUMMINSIND", "HDFCAMC", "FINCABLES", "UNOMINDA", "SAMMAANCAP",
    "GVT&D", "AMBER", "ABCAPITAL", "SHREECEM", "HYUNDAI", "PGEL", "AUROPHARMA", "PNBHOUSING", "COCHINSHIP", "IRCON",
    "BRITANNIA", "RPOWER", "SWIGGY", "MANAPPURAM", "INDUSTOWER", "LICHSGFIN", "VMM", "ANANTRAJ", "VOLTAS", "NAVINFLUOR",
    "GMRAIRPORT", "INOXWIND", "IREDA", "TECHM", "NBCC", "FORTIS", "PIDILITIND", "J&KBANK", "KIRLOSENG", "SBICARD",
    "GMDCLTD", "KARURVYSYA", "LICI", "HAPPSTMNDS", "MRF", "MFSL", "NAUKRI", "BLUESTARCO", "RADICO", "IRCTC",
    "LTM", "OLAELEC", "MARICO", "SAGILITY", "SUPREMEIND", "ZENTEC", "HSCL", "TARIL", "DIVISLAB", "ADANIENSOL",
    "UNITDSPR", "LODHA", "NEWGEN", "TATAELXSI", "LTF", "KFINTECH", "BIOCON", "SAILIFE", "ASTRAL", "KALYANKJIL",
    "SCI", "TORNTPOWER", "SIEMENS", "PRESTIGE", "SWANCORP", "MPHASIS", "GESHIP", "ENGINERSIN", "TATACONSUM", "HFCL",
    "APARINDS", "APLAPOLLO", "REDINGTON", "GRAPHITE", "SRF", "GODREJCP", "GODFRYPHLP", "HBLENGINE", "JUBLFOOD", "IFCI",
    "ITCHOTELS", "NYKAA", "ENRIN", "JSWINFRA", "OFSS", "IEX", "HUDCO", "NAM-INDIA", "TATACOMM", "GLENMARK",
    "DELHIVERY", "TITAGARH", "TIINDIA", "PREMIERENE", "COLPAL", "PIIND", "BAJAJHLDNG", "BOSCHLTD", "CENTRALBK", "ATHERENERG",
    "ANANDRATHI", "TATATECH", "HEG", "APOLLOTYRE", "BAJAJHFL", "LLOYDSME", "KIRLOSBROS", "FIVESTAR", "DEEPAKFERT", "JSL",
    "ZEEL", "ICICIGI", "EXIDEIND", "GODREJAGRO", "CASTROLIND", "SONACOMS", "PHOENIXLTD", "WOCKPHARMA", "OBEROIRLTY", "PPLPHARMA",
    "GPIL", "JMFINANCIL", "BEML", "JPPOWER", "DABUR", "RAILTEL", "MOTILALOFS", "CUB", "NH", "OLECTRA",
    "CROMPTON", "PVRINOX", "COROMANDEL", "NCC", "CEATLTD", "LTTS", "PAGEIND", "JKCEMENT", "ICICIPRULI", "LEMONTREE",
    "CONCOR", "RRKABEL", "AAVAS", "IIFL", "TATAINVEST", "WELCORP", "IRB", "IOB", "AARTIIND", "GRAVITA",
    "APTUS", "ZYDUSLIFE", "UCOBANK", "EIDPARRY", "M&MFIN", "BLUEJET", "SARDAEN", "MGL", "PATANJALI", "SYNGENE",
    "ARE&M", "CHOICEIN", "PCBL", "ACC", "THERMAX", "IGL", "BLS", "TECHNOE", "EMAMILTD", "DEEPAKNTR",
    "JINDALSAW", "NEULANDLAB", "AWL", "TRIVENI", "GILLETTE", "ATGL", "CREDITACC", "BSOFT", "POONAWALLA", "SUNDARMFIN",
    "SJVN", "TATACHEM", "RITES", "NLCINDIA", "MANYAVAR", "COHANCE", "CHAMBLFERT", "CYIENT", "LINDEINDIA", "KEC",
    "WHIRLPOOL", "ABFRL", "NUVAMA", "HOMEFIRST", "FIRSTCRY", "ALKEM", "AJANTPHARM", "KIMS", "ECLERX", "PTCIL",
    "AFFLE", "NTPCGREEN", "ABSLAMC", "CESC", "CCL", "INTELLECT", "JSWCEMENT", "WELSPUNLIV", "SCHAEFFLER", "SIGNATURE",
    "DCMSHRIRAM", "UBL", "INDIAMART", "SONATSOFTW", "AEGISLOG", "NAVA", "LATENTVIEW", "JBCHEPHARM", "ABREL", "AEGISVOPAK",
    "GRANULES", "VTL", "KPRMILL", "MSUMI", "BERGEPAINT", "JYOTICNC", "GUJGASLTD", "RCF", "DBREALTY", "ABBOTINDIA",
    "STARHEALTH", "ELGIEQUIP", "IGIL", "EMCURE", "TRIDENT", "GICRE", "BALKRISIND", "ACE", "CGCL", "FSL",
    "ELECON", "CERA", "GSPL", "INDGN", "DALBHARAT", "NSLNISP", "HONAUT", "CHOLAHLDNG", "ESCORTS", "JBMA",
    "INOXINDIA", "LALPATHLAB", "BRIGADE", "ZENSARTECH", "CRISIL", "AIAENG", "KAJARIACER", "IKS", "ENDURANCE", "RKFORGE",
    "ONESOURCE", "POLYMED", "AIIL", "CRAFTSMAN", "DEVYANI", "CANFINHOME", "TRITURBINE", "CLEAN", "THELEELA", "HEXT",
    "RELINFRA", "GLAND", "MEDANTA", "BATAINDIA", "EIHOTEL", "USHAMART", "MAPMYINDIA", "SBFC", "ACMESOLAR", "PGHH",
    "3MINDIA", "SOBHA", "SCHNEIDER", "AADHARHFC", "GODIGIT", "MMTC", "GODREJIND", "CAPLIPOINT", "DOMS", "FACT",
    "MAHSEAMLES", "AFCONS", "BBTC", "MINDACORP", "SUNTV", "SUNDRMFAST", "FLUOROCHEM", "SHYAMMETL", "TBOTEK", "FINPIPE",
    "TIMKEN", "UTIAMC", "ZFCVINDIA", "SAREGAMA", "GLAXO", "ALOKINDS", "ABLBL", "JYOTHYLAB", "RAINBOW", "KSB",
    "NIACL", "BLUEDART", "ERIS", "IPCALAB", "BIKAJI", "VIJAYA", "TTML", "SAPPHIRE", "CONCORDBIO", "JUBLINGREA",
    "ITI", "SUMICHEM", "HONASA", "AKUMS", "RAMCOCEM", "NIVABUPA", "JUBLPHARMA", "KPIL", "ASAHIINDIA", "NUVOCO",
    "BAYERCROP", "PFIZER", "INDIACEM", "CARBORUNIV", "BHARTIHEXA", "ATUL", "MAHSCOOTER", "BASF", "VENTIVE", "ALKYLAMINE",
    "AKZOINDIA", "CHALET", "RHIM", "VGUARD", "APLLTD", "CAMPUS", "ASTRAZEN", "CENTURYPLY", "METROPOLIS", "AGARWALEYE"
]

# ── FIX 1: Increased lookback from 30 → 60 days ─────────────────────────────
LOOKBACK_DAYS   = 60    # was 30
ATR_LENGTH      = 14
MIN_CANDLES     = ATR_LENGTH + 1   # 15
MAX_RETRIES     = 3
RETRY_DELAY_SEC = 2

batch_size = 50
filtered_stocks = []
all_stocks_summary = {}

end_date   = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
start_date = end_date - timedelta(days=LOOKBACK_DAYS)
range_to   = int(end_date.timestamp())
range_from = int(start_date.timestamp())

print("\n" + "="*80)
print("STOCK SCANNER - NIFTY 500 WITH ATR(14) FILTER")
print("="*80)
print(f"Total stocks : {len(stock_list)}")
print(f"Batch size   : {batch_size}")
print(f"Lookback days: {LOOKBACK_DAYS}  (min candles needed: {MIN_CANDLES})")
print(f"Filters:")
print(f"  • Price  > ₹50")
print(f"  • Volume > 5,00,000")
print(f"  • ATR({ATR_LENGTH}) > 2% of Current Price")
print("="*80)
print(f"Fetching data from : {start_date.strftime('%Y-%m-%d')}")
print(f"Fetching data to   : {end_date.strftime('%Y-%m-%d')}")
print()


def fetch_history_with_retry(symbol: str) -> dict | None:
    hist_data = {
        "symbol"     : f"NSE:{symbol}-EQ",
        "resolution" : "D",
        "date_format": "0",
        "range_from" : str(range_from),
        "range_to"   : str(range_to),
        "cont_flag"  : "1"
    }
    for attempt in range(1, MAX_RETRIES + 1):
        resp = fyers.history(data=hist_data)
        if resp.get('s') == 'ok' and 'candles' in resp:
            return resp
        if attempt < MAX_RETRIES:
            print(f"    ⚠ {symbol}: history fetch failed (attempt {attempt}/{MAX_RETRIES}), retrying in {RETRY_DELAY_SEC}s…")
            time.sleep(RETRY_DELAY_SEC)
    print(f"    ✗ {symbol}: all {MAX_RETRIES} history fetch attempts failed — ATR will be N/A")
    return None


def calc_atr_percent(candles: list, current_price: float) -> float | None:
    if len(candles) < MIN_CANDLES:
        return None

    df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['ATR'] = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=ATR_LENGTH)

    valid_atr = df['ATR'].dropna()
    if valid_atr.empty:
        return None

    latest_atr = valid_atr.iloc[-1]
    if current_price <= 0:
        return None

    return (latest_atr / current_price) * 100


for i in range(0, len(stock_list), batch_size):
    batch = stock_list[i:i+batch_size]

    print(f"Processing stocks {i+1} to {min(i+batch_size, len(stock_list))}…")

    symbols       = ",".join([f"NSE:{s}-EQ" for s in batch])
    quotes_data   = {"symbols": symbols}
    quotes_response = fyers.quotes(data=quotes_data)

    potential_stocks = []

    if quotes_response.get('s') == 'ok' and 'd' in quotes_response:
        for item in quotes_response['d']:
            if item.get('s') == 'ok':
                symbol = item['n'].replace('NSE:', '').replace('-EQ', '')
                qv     = item['v']
                lp     = qv.get('lp', 0)
                volume = qv.get('volume', 0)

                all_stocks_summary[symbol] = {
                    'price'      : lp,
                    'volume'     : volume,
                    'atr_percent': None
                }

                if lp > 50 and volume > 500000:
                    potential_stocks.append({'symbol': symbol, 'price': lp, 'volume': volume})

    for stock in potential_stocks:
        symbol = stock['symbol']

        hist_response = fetch_history_with_retry(symbol)

        if hist_response is None:
            continue

        candles    = hist_response['candles']
        atr_pct    = calc_atr_percent(candles, stock['price'])

        if atr_pct is None:
            print(f"  ⚠ {symbol}: only {len(candles)} candles returned — ATR skipped")
            continue

        all_stocks_summary[symbol]['atr_percent'] = round(atr_pct, 2)

        latest_atr_val = (atr_pct / 100) * stock['price']

        if atr_pct > 2:
            filtered_stocks.append({
                'symbol'     : symbol,
                'price'      : stock['price'],
                'volume'     : stock['volume'],
                'atr'        : round(latest_atr_val, 2),
                'atr_percent': round(atr_pct, 2)
            })
            print(f"  ✓ {symbol}: ₹{stock['price']:.2f} | Vol: {stock['volume']:,} | ATR%: {atr_pct:.2f}% ✓")
        else:
            print(f"  ✗ {symbol}: ₹{stock['price']:.2f} | Vol: {stock['volume']:,} | ATR%: {atr_pct:.2f}% [<2%]")

        time.sleep(0.2)

    time.sleep(1)
    print()


# ── Final filtered results ────────────────────────────────────────────────────
print("\n" + "="*80)
print(f"RESULTS: {len(filtered_stocks)} stocks found with ATR({ATR_LENGTH}) > 2%")
print("="*80)

if filtered_stocks:
    filtered_stocks.sort(key=lambda x: x['atr_percent'], reverse=True)
    print(f"{'Symbol':<15} {'Price (₹)':<12} {'Volume':<15} {'ATR(14)':<12} {'ATR%':<10}")
    print("-"*80)
    for stock in filtered_stocks:
        print(f"{stock['symbol']:<15} ₹{stock['price']:<11.2f} {stock['volume']:<15,} {stock['atr']:<12} {stock['atr_percent']:<10}%")
else:
    print("No stocks found matching all criteria")
print("="*80)

# ── Generate filtered stocks txt file ────────────────────────────────────────
output_filename = "filtered_stocks.txt"
with open(output_filename, "w") as f:
    f.write(f"FILTERED STOCKS — ATR({ATR_LENGTH}) > 2%\n")
    f.write(f"Generated on : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"Total matched: {len(filtered_stocks)}\n")
    f.write("="*60 + "\n\n")
    for stock in filtered_stocks:
        f.write(f"{stock['symbol']}\n")
print(f"\n📄 Filtered stock list saved to: {output_filename}")
# ─────────────────────────────────────────────────────────────────────────────


# ── Full 500 summary table ────────────────────────────────────────────────────
print("\n\n" + "="*100)
print("FULL NIFTY 500 SCAN SUMMARY — ALL STOCKS")
print("="*100)
print(f"{'#':<5} {'Symbol':<15} {'Price (₹)':<13} {'Price>50':<12} {'Volume':<15} {'Vol>5L':<10} {'ATR%':<10} {'ATR>2%':<10}")
print("-"*100)

for idx, symbol in enumerate(stock_list, start=1):
    data = all_stocks_summary.get(symbol)

    if data is None:
        print(f"{idx:<5} {symbol:<15} {'N/A':<13} {'✗':<12} {'N/A':<15} {'✗':<10} {'N/A':<10} {'✗':<10}")
        continue

    price      = data['price']
    volume     = data['volume']
    atr_pct    = data['atr_percent']

    price_pass = '✓' if price  > 50     else '✗'
    vol_pass   = '✓' if volume > 500000 else '✗'

    if atr_pct is None:
        atr_str  = 'N/A'
        atr_pass = '—'
    else:
        atr_str  = f"{atr_pct}%"
        atr_pass = '✓' if atr_pct > 2 else '✗'

    print(f"{idx:<5} {symbol:<15} ₹{price:<12.2f} {price_pass:<12} {volume:<15,} {vol_pass:<10} {atr_str:<10} {atr_pass:<10}")

print("="*100)
print(f"Legend: ✓ = Pass  |  ✗ = Fail  |  — = Not checked (failed earlier filter)")
print("="*100)