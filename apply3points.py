import creditials as cr
from fyers_apiv3 import fyersModel
from datetime import datetime, timedelta
import time
import json
import os

# Read saved access token from file
with open("access_token.txt", "r") as f:
    access_token = f.read().strip()

# Initialize Fyers client
fyers = fyersModel.FyersModel(
    client_id=cr.client_id, 
    token=access_token, 
    is_async=False, 
    log_path=""
)

class FyersOverreactionScanner:
    def __init__(self):
        self.results = {
            'buy_candidates': [],
            'sell_candidates': []
        }
        
        # Exchange and segment mappings
        self.exchange_map = {10: "NSE", 11: "MCX", 12: "BSE"}
        self.segment_map = {10: "Capital Market", 11: "F&O", 12: "Currency", 20: "Commodity"}
    
    def check_market_status(self):
        """Check if markets are open"""
        response = fyers.market_status()
        
        print("\n📊 MARKET STATUS")
        print("-" * 50)
        
        for market in response["marketStatus"]:
            exchange = self.exchange_map.get(market["exchange"], market["exchange"])
            segment = self.segment_map.get(market["segment"], market["segment"])
            status_icon = "✅" if market["status"] == "Open" else "❌"
            print(f"{status_icon} {exchange} | {segment} | {market['market_type']} → {market['status']}")
        
        print("-" * 50)
        return response
    
    def get_nifty_50_symbols(self):
        """Return list of Nifty 50 symbols in Fyers format"""
        symbols = [
            'NSE:RELIANCE-EQ', 'NSE:TCS-EQ', 'NSE:HDFCBANK-EQ', 'NSE:INFY-EQ', 
            'NSE:ICICIBANK-EQ', 'NSE:HINDUNILVR-EQ', 'NSE:ITC-EQ', 'NSE:KOTAKBANK-EQ',
            'NSE:SBIN-EQ', 'NSE:BHARTIARTL-EQ', 'NSE:LT-EQ', 'NSE:ASIANPAINT-EQ',
            'NSE:HCLTECH-EQ', 'NSE:MARUTI-EQ', 'NSE:SUNPHARMA-EQ', 'NSE:TITAN-EQ',
            'NSE:AXISBANK-EQ', 'NSE:BAJFINANCE-EQ', 'NSE:NESTLEIND-EQ', 'NSE:WIPRO-EQ',
            'NSE:TATAMOTORS-EQ', 'NSE:TATASTEEL-EQ', 'NSE:JSWSTEEL-EQ', 'NSE:TECHM-EQ',
            'NSE:GRASIM-EQ', 'NSE:BRITANNIA-EQ', 'NSE:INDUSINDBK-EQ', 'NSE:DRREDDY-EQ',
            'NSE:CIPLA-EQ', 'NSE:ULTRACEMCO-EQ', 'NSE:BAJAJ-AUTO-EQ', 'NSE:ADANIPORTS-EQ',
            'NSE:HEROMOTOCO-EQ', 'NSE:BPCL-EQ', 'NSE:EICHERMOT-EQ', 'NSE:COALINDIA-EQ',
            'NSE:GAIL-EQ', 'NSE:HDFCLIFE-EQ', 'NSE:SBILIFE-EQ', 'NSE:UPL-EQ',
            'NSE:DIVISLAB-EQ', 'NSE:SHREECEM-EQ', 'NSE:BAJAJFINSV-EQ', 'NSE:HINDALCO-EQ',
            'NSE:POWERGRID-EQ', 'NSE:NTPC-EQ', 'NSE:M&M-EQ', 'NSE:ONGC-EQ', 'NSE:IOC-EQ'
        ]
        return symbols
    
    def get_intraday_data(self, symbol, resolution="5"):
        """Fetch intraday data for a symbol"""
        try:
            # Calculate timestamps (last 1 day)
            end_time = datetime.now()
            start_time = end_time - timedelta(days=1)
            
            range_from = int(start_time.timestamp())
            range_to = int(end_time.timestamp())
            
            data = {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "1",
                "range_from": range_from,
                "range_to": range_to,
                "cont_flag": "1"
            }
            
            response = fyers.history(data=data)
            
            if response and response.get('s') == 'ok':
                candles = response['candles']
                formatted_candles = []
                
                for c in candles:
                    formatted_candles.append({
                        'timestamp': datetime.fromtimestamp(c[0]),
                        'open': float(c[1]),
                        'high': float(c[2]),
                        'low': float(c[3]),
                        'close': float(c[4]),
                        'volume': int(c[5])
                    })
                
                return formatted_candles
            else:
                return None
                
        except Exception as e:
            return None
    
    def calculate_average_volume(self, candles):
        """Calculate average volume from candles"""
        if len(candles) <= 1:
            return 0
        
        total_volume = 0
        for i in range(len(candles) - 1):  # Exclude last candle
            total_volume += candles[i]['volume']
        
        return total_volume / (len(candles) - 1)
    
    def apply_buy_test(self, candles, symbol):
        """Apply 3-point test for BUY candidates"""
        if not candles or len(candles) < 5:
            return False
        
        # Calculate metrics
        day_open = candles[0]['open']
        current_close = candles[-1]['close']
        
        # Find day high and low
        day_low = min(c['low'] for c in candles)
        day_high = max(c['high'] for c in candles)
        day_range = day_high - day_low
        
        # Test 1: Fall more than 3% from open
        pct_from_open = ((current_close - day_open) / day_open) * 100
        test1 = pct_from_open <= -3.0
        
        # Test 2: Close above lowest 25% of range
        lowest_25pct = day_low + (day_range * 0.25)
        test2 = current_close > lowest_25pct
        
        # Test 3: Volume spike during fall
        avg_volume = self.calculate_average_volume(candles)
        
        # Find red candles with high volume
        spike_found = False
        spike_volume = 0
        spike_time = None
        
        for c in candles:
            if c['close'] < c['open'] and c['volume'] > avg_volume * 1.5:
                spike_found = True
                spike_volume = c['volume']
                spike_time = c['timestamp']
                break
        
        test3 = spike_found
        
        if test1 and test2 and test3:
            # Calculate closing position percentage
            close_position = ((current_close - day_low) / day_range) * 100
            
            return {
                'symbol': symbol.replace('NSE:', '').replace('-EQ', ''),
                'action': 'BUY',
                'price': round(current_close, 2),
                'change_%': round(pct_from_open, 2),
                'open': round(day_open, 2),
                'low': round(day_low, 2),
                'high': round(day_high, 2),
                'position_%': round(close_position, 1),
                'spike_time': spike_time.strftime('%H:%M') if spike_time else 'N/A',
                'spike_vol': spike_volume,
                'avg_vol': int(avg_volume)
            }
        return False
    
    def apply_sell_test(self, candles, symbol):
        """Apply 3-point test for SELL candidates"""
        if not candles or len(candles) < 5:
            return False
        
        # Calculate metrics
        day_open = candles[0]['open']
        current_close = candles[-1]['close']
        
        # Find day high and low
        day_low = min(c['low'] for c in candles)
        day_high = max(c['high'] for c in candles)
        day_range = day_high - day_low
        
        # Test 1: Rise more than 3% from open
        pct_from_open = ((current_close - day_open) / day_open) * 100
        test1 = pct_from_open >= 3.0
        
        # Test 2: Close below highest 25% of range
        highest_25pct = day_high - (day_range * 0.25)
        test2 = current_close < highest_25pct
        
        # Test 3: Volume spike during rise
        avg_volume = self.calculate_average_volume(candles)
        
        # Find green candles with high volume
        spike_found = False
        spike_volume = 0
        spike_time = None
        
        for c in candles:
            if c['close'] > c['open'] and c['volume'] > avg_volume * 1.5:
                spike_found = True
                spike_volume = c['volume']
                spike_time = c['timestamp']
                break
        
        test3 = spike_found
        
        if test1 and test2 and test3:
            # Calculate closing position percentage
            close_position = ((current_close - day_low) / day_range) * 100
            
            return {
                'symbol': symbol.replace('NSE:', '').replace('-EQ', ''),
                'action': 'SELL',
                'price': round(current_close, 2),
                'change_%': round(pct_from_open, 2),
                'open': round(day_open, 2),
                'low': round(day_low, 2),
                'high': round(day_high, 2),
                'position_%': round(close_position, 1),
                'spike_time': spike_time.strftime('%H:%M') if spike_time else 'N/A',
                'spike_vol': spike_volume,
                'avg_vol': int(avg_volume)
            }
        return False
    
    def scan_symbols(self, symbols=None, resolution="5"):
        """Scan all symbols for overreaction candidates"""
        if symbols is None:
            symbols = self.get_nifty_50_symbols()
        
        print(f"\n🔍 Scanning {len(symbols)} symbols ({resolution}-minute)...")
        print("-" * 50)
        
        for i, symbol in enumerate(symbols, 1):
            print(f"\rProgress: {i}/{len(symbols)} - {symbol}", end="")
            
            candles = self.get_intraday_data(symbol, resolution)
            
            if candles:
                buy_result = self.apply_buy_test(candles, symbol)
                if buy_result:
                    self.results['buy_candidates'].append(buy_result)
                
                sell_result = self.apply_sell_test(candles, symbol)
                if sell_result:
                    self.results['sell_candidates'].append(sell_result)
            
            time.sleep(0.3)  # Rate limiting
        
        print("\n" + "-" * 50)
        return self.results
    
    def display_results(self):
        """Display formatted results"""
        print("\n" + "=" * 90)
        print("📊 OVERREACTION SCANNER RESULTS")
        print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 90)
        
        # BUY Candidates
        print("\n📈 BUY CANDIDATES (Oversold - Potential Reversal UP)")
        print("-" * 90)
        print(f"{'Symbol':<8} {'Price':>8} {'% Chng':>8} {'Pos%':>6} {'Spike':>8} {'Spike Vol':>12} {'Avg Vol':>12}")
        print("-" * 90)
        
        if self.results['buy_candidates']:
            # Sort by change_%
            sorted_buy = sorted(self.results['buy_candidates'], key=lambda x: x['change_%'])
            
            for c in sorted_buy:
                print(f"{c['symbol']:<8} {c['price']:>8.2f} {c['change_%']:>8.2f}% "
                      f"{c['position_%']:>6.1f}% {c['spike_time']:>8} "
                      f"{c['spike_vol']:>12,} {c['avg_vol']:>12,}")
        else:
            print("No buy candidates found")
        
        # SELL Candidates
        print("\n📉 SELL CANDIDATES (Overbought - Potential Reversal DOWN)")
        print("-" * 90)
        print(f"{'Symbol':<8} {'Price':>8} {'% Chng':>8} {'Pos%':>6} {'Spike':>8} {'Spike Vol':>12} {'Avg Vol':>12}")
        print("-" * 90)
        
        if self.results['sell_candidates']:
            # Sort by change_% descending
            sorted_sell = sorted(self.results['sell_candidates'], key=lambda x: x['change_%'], reverse=True)
            
            for c in sorted_sell:
                print(f"{c['symbol']:<8} {c['price']:>8.2f} +{c['change_%']:>7.2f}% "
                      f"{c['position_%']:>6.1f}% {c['spike_time']:>8} "
                      f"{c['spike_vol']:>12,} {c['avg_vol']:>12,}")
        else:
            print("No sell candidates found")
        
        # Summary
        print("\n" + "=" * 90)
        print(f"📌 SUMMARY")
        print(f"   Total Scanned: {len(self.get_nifty_50_symbols())}")
        print(f"   BUY Candidates: {len(self.results['buy_candidates'])}")
        print(f"   SELL Candidates: {len(self.results['sell_candidates'])}")
        print("=" * 90)
    
    def save_results(self, filename=None):
        """Save results to JSON file"""
        if filename is None:
            filename = f"scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        
        output = {
            'scan_time': datetime.now().isoformat(),
            'buy_candidates': self.results['buy_candidates'],
            'sell_candidates': self.results['sell_candidates']
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"\n✅ Results saved to {filename}")
        
        # Also save to simple text file
        txt_file = filename.replace('.json', '.txt')
        with open(txt_file, 'w') as f:
            f.write(f"SCAN RESULTS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 50 + "\n\n")
            
            f.write("BUY CANDIDATES:\n")
            f.write("-" * 30 + "\n")
            for c in self.results['buy_candidates']:
                f.write(f"{c['symbol']} - Price: {c['price']}, Change: {c['change_%']}%, Position: {c['position_%']}%\n")
            
            f.write("\nSELL CANDIDATES:\n")
            f.write("-" * 30 + "\n")
            for c in self.results['sell_candidates']:
                f.write(f"{c['symbol']} - Price: {c['price']}, Change: +{c['change_%']}%, Position: {c['position_%']}%\n")
        
        print(f"✅ Text file saved to {txt_file}")


def main():
    """Main function"""
    print("🚀 FYERS API OVERREACTION SCANNER")
    print("=" * 50)
    
    # Initialize scanner
    scanner = FyersOverreactionScanner()
    
    # Check market status
    market_status = scanner.check_market_status()
    
    # Verify connection
    try:
        profile = fyers.get_profile()
        if profile.get('s') == 'ok':
            print(f"\n✅ Connected: {profile.get('data', {}).get('name', 'User')}")
        else:
            print(f"\n❌ Connection failed")
            return
    except:
        print("\n❌ Error connecting to Fyers API")
        return
    
    # Get user input for scan type
    print("\n📋 SCAN OPTIONS")
    print("1. Quick scan (5-minute)")
    print("2. Detailed scan (15-minute)")
    print("3. Custom timeframe")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        resolution = "5"
    elif choice == "2":
        resolution = "15"
    elif choice == "3":
        resolution = input("Enter timeframe (1/2/3/5/10/15/30/60): ").strip()
    else:
        resolution = "5"
    
    # Run scan
    scanner.scan_symbols(resolution=resolution)
    
    # Display results
    scanner.display_results()
    
    # Save results
    save_choice = input("\n💾 Save results? (y/n): ").strip().lower()
    if save_choice == 'y':
        scanner.save_results()


if __name__ == "__main__":
    main()