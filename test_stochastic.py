import yfinance as yf
import pandas as pd

symbol = "BAIK.JK"

print("=" * 70)
print(f"STOCHASTIC TEST: {symbol}")
print("=" * 70)

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

for col in ["High", "Low", "Close", "Volume"]:
    data[col] = pd.to_numeric(data[col], errors="coerce")

data = data.dropna(subset=["High", "Low", "Close"])


# ============================================================
# STOCHASTIC FUNCTION
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
# METHOD A
# CURRENT BOT
# ============================================================

slow_k_a, slow_d_a = calculate_stochastic(data)

print("\n" + "=" * 70)
print("METHOD A — CURRENT BOT")
print("All Yahoo rows included")
print("=" * 70)

print(f"Slow K = {float(slow_k_a.iloc[-1]):.2f}")
print(f"Slow D = {float(slow_d_a.iloc[-1]):.2f}")
print(
    f"K > D  = "
    f"{float(slow_k_a.iloc[-1]) > float(slow_d_a.iloc[-1])}"
)


# ============================================================
# METHOD B
# REMOVE ZERO-VOLUME DAYS
# ============================================================

trading_data = data[data["Volume"] > 0].copy()

slow_k_b, slow_d_b = calculate_stochastic(trading_data)

print("\n" + "=" * 70)
print("METHOD B — REMOVE ZERO-VOLUME DAYS")
print("=" * 70)

print(f"Trading rows = {len(trading_data)}")
print(f"Slow K = {float(slow_k_b.iloc[-1]):.2f}")
print(f"Slow D = {float(slow_d_b.iloc[-1]):.2f}")
print(
    f"K > D  = "
    f"{float(slow_k_b.iloc[-1]) > float(slow_d_b.iloc[-1])}"
)


# ============================================================
# METHOD C
# REPLACE ZERO-VOLUME OHLC WITH PREVIOUS TRADING DAY
# ============================================================

filled_data = data.copy()

zero_volume = filled_data["Volume"] == 0

# Copy previous available OHLC forward
for column in ["Open", "High", "Low", "Close"]:

    if column in filled_data.columns:

        filled_data.loc[zero_volume, column] = (
            filled_data[column]
            .shift(1)
            .loc[zero_volume]
        )

# Fill multiple consecutive zero-volume days
filled_data[["Open", "High", "Low", "Close"]] = (
    filled_data[["Open", "High", "Low", "Close"]]
    .ffill()
)

slow_k_c, slow_d_c = calculate_stochastic(filled_data)

print("\n" + "=" * 70)
print("METHOD C — REPLACE ZERO-VOLUME DAYS")
print("Use previous available OHLC")
print("=" * 70)

print(f"Rows = {len(filled_data)}")
print(f"Slow K = {float(slow_k_c.iloc[-1]):.2f}")
print(f"Slow D = {float(slow_d_c.iloc[-1]):.2f}")
print(
    f"K > D  = "
    f"{float(slow_k_c.iloc[-1]) > float(slow_d_c.iloc[-1])}"
)


# ============================================================
# SHOW BAIK'S ZERO-VOLUME DAYS
# ============================================================

print("\n" + "=" * 70)
print("ZERO-VOLUME DAYS")
print("=" * 70)

print(
    data[data["Volume"] == 0][
        ["Open", "High", "Low", "Close", "Volume"]
    ].tail(10)
)


# ============================================================
# FINAL COMPARISON
# ============================================================

print("\n" + "=" * 70)
print("FINAL COMPARISON")
print("=" * 70)

print(
    f"Method A - Current:       "
    f"K={float(slow_k_a.iloc[-1]):.2f}, "
    f"D={float(slow_d_a.iloc[-1]):.2f}"
)

print(
    f"Method B - Remove zero:   "
    f"K={float(slow_k_b.iloc[-1]):.2f}, "
    f"D={float(slow_d_b.iloc[-1]):.2f}"
)

print(
    f"Method C - Previous OHLC:  "
    f"K={float(slow_k_c.iloc[-1]):.2f}, "
    f"D={float(slow_d_c.iloc[-1]):.2f}"
)

print(
    "Mirae HOTS:               "
    "K=5.24, D=7.61"
)
