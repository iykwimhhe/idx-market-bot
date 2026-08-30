import yfinance as yf
import pandas as pd

symbol = "BAIK.JK"

print("=" * 60)
print(f"STOCHASTIC TEST: {symbol}")
print("=" * 60)

data = yf.download(
    symbol,
    period="6mo",
    interval="1d",
    progress=False,
    auto_adjust=False
)

if data.empty:
    print("No data returned.")
    exit()

if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

# Make sure numeric
for col in ["High", "Low", "Close", "Volume"]:
    data[col] = pd.to_numeric(data[col], errors="coerce")

data = data.dropna(subset=["High", "Low", "Close"])

print("\nLatest Yahoo data:")
print(data.tail(10))

# ============================================================
# METHOD A
# Current bot calculation
# ============================================================

def calculate_stochastic(df):
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    lowest_low = low.rolling(10).min()
    highest_high = high.rolling(10).max()

    raw_k = (
        (close - lowest_low)
        / (highest_high - lowest_low)
    ) * 100

    slow_k = raw_k.rolling(5).mean()
    slow_d = slow_k.rolling(5).mean()

    return slow_k, slow_d


# ============================================================
# METHOD A — ALL DAYS
# ============================================================

slow_k_a, slow_d_a = calculate_stochastic(data)

print("\n" + "=" * 60)
print("METHOD A — CURRENT BOT")
print("All Yahoo rows included")
print("=" * 60)

print(f"Slow K = {float(slow_k_a.iloc[-1]):.2f}")
print(f"Slow D = {float(slow_d_a.iloc[-1]):.2f}")
print(f"K > D  = {float(slow_k_a.iloc[-1]) > float(slow_d_a.iloc[-1])}")


# ============================================================
# METHOD B — REMOVE ZERO VOLUME DAYS
# ============================================================

trading_data = data[data["Volume"] > 0].copy()

slow_k_b, slow_d_b = calculate_stochastic(trading_data)

print("\n" + "=" * 60)
print("METHOD B — EXCLUDE ZERO-VOLUME DAYS")
print("=" * 60)

print(f"Trading rows: {len(trading_data)}")
print(f"Slow K = {float(slow_k_b.iloc[-1]):.2f}")
print(f"Slow D = {float(slow_d_b.iloc[-1]):.2f}")
print(f"K > D  = {float(slow_k_b.iloc[-1]) > float(slow_d_b.iloc[-1])}")


# ============================================================
# METHOD C — RAW K + SMA(5) + SMA(5)
# Show the latest intermediate values
# ============================================================

print("\n" + "=" * 60)
print("LATEST STOCHASTIC COMPONENTS")
print("=" * 60)

lowest_low = data["Low"].rolling(10).min()
highest_high = data["High"].rolling(10).max()

raw_k = (
    (data["Close"] - lowest_low)
    / (highest_high - lowest_low)
) * 100

slow_k = raw_k.rolling(5).mean()
slow_d = slow_k.rolling(5).mean()

debug = pd.DataFrame({
    "Close": data["Close"],
    "Raw K": raw_k,
    "Slow K": slow_k,
    "Slow D": slow_d
})

print(debug.tail(10).round(2))


# ============================================================
# COMPARISON
# ============================================================

print("\n" + "=" * 60)
print("MIRAE HOTS REFERENCE")
print("=" * 60)

print("K = 5.24")
print("D = 7.61")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)

print(
    f"Current bot:       "
    f"K={float(slow_k_a.iloc[-1]):.2f}, "
    f"D={float(slow_d_a.iloc[-1]):.2f}"
)

print(
    f"No zero-volume:    "
    f"K={float(slow_k_b.iloc[-1]):.2f}, "
    f"D={float(slow_d_b.iloc[-1]):.2f}"
)

print(
    "Mirae HOTS:        "
    "K=5.24, D=7.61"
)
