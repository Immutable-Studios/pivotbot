import os
import sys
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

API_KEY = os.getenv('ALPACA_API_KEY')
API_SECRET = os.getenv('ALPACA_API_SECRET')
DATA_URL = 'https://data.alpaca.markets/v2'

if len(sys.argv) < 2:
    print("Usage: python test_fetch_last_trading_day_pivots.py TICKER")
    sys.exit(1)

ticker = sys.argv[1].upper()

# Helper: Find last trading day (skip weekends)
def get_last_trading_day():
    today = datetime.utcnow().date()
    offset = 1
    while True:
        candidate = today - timedelta(days=offset)
        if candidate.weekday() < 5:  # Mon-Fri are 0-4
            return candidate
        offset += 1

last_trading_day = get_last_trading_day()

headers = {
    'APCA-API-KEY-ID': API_KEY,
    'APCA-API-SECRET-KEY': API_SECRET
}

params = {
    'timeframe': '1Day',
    'start': last_trading_day.strftime('%Y-%m-%d'),
    'end': last_trading_day.strftime('%Y-%m-%d'),
    'limit': 1
}

url = f"{DATA_URL}/stocks/{ticker}/bars"

print(f"Fetching data for {ticker} on {last_trading_day}...")
response = requests.get(url, headers=headers, params=params)
if response.status_code != 200:
    print(f"API error: {response.status_code} {response.text}")
    sys.exit(1)

data = response.json()
bars = data.get('bars', [])
if not bars:
    print(f"No data returned for {ticker} on {last_trading_day}")
    sys.exit(1)

bar = bars[0]
high = bar['h']
low = bar['l']
close = bar['c']
print(f"High: {high}, Low: {low}, Close: {close}")

def calculate_pivot_points(high, low, close):
    pivot = (high + low + close) / 3
    r1 = 2 * pivot - low
    s1 = 2 * pivot - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)
    r3 = high + 2 * (pivot - low)
    s3 = low - 2 * (high - pivot)
    return {
        'Pivot': pivot,
        'R1': r1,
        'S1': s1,
        'R2': r2,
        'S2': s2,
        'R3': r3,
        'S3': s3
    }

pivots = calculate_pivot_points(high, low, close)
print("Pivot Points:")
for k, v in pivots.items():
    print(f"  {k}: {v:.2f}") 