import yfinance as yf
import pandas as pd

symbol = "BAIK.JK"

print(f"Testing {symbol}...")
print()

data = yf.download(
    symbol,
    period="3mo",
    interval="1d",
    progress=False,
    auto_adjust=False
)

if data.empty:
    print("No data returned.")
    exit()

if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

high = data["High"]
low = data["Low"]
close = data["Close"]

# ====================================
# STOCHASTIC 10,5,5
# ====================================

lowest_low = low.rolling(10).min()
highest_high = high.rolling(10).max()

raw_k = (
    (close - lowest_low)
    / (highest_high - lowest_low)
) * 100

slow_k = raw_k.rolling(5).mean()
slow_d = slow_k.rolling(5).mean()

print("Latest data:")
print(data.tail(5))

print()
print("Stochastic 10,5,5:")
print(
    f"Slow K = {float(slow_k.iloc[-1]):.2f}"
)
print(
    f"Slow D = {float(slow_d.iloc[-1]):.2f}"
)

print()
print(
    "Golden Cross:",
    float(slow_k.iloc[-1]) > float(slow_d.iloc[-1])
)
