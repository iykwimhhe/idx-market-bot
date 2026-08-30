import yfinance as yf
import pandas as pd

symbol = "BAIK.JK"

print("=" * 75)
print(f"STOCHASTIC METHOD COMPARISON: {symbol}")
print("=" * 75)

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
# REMOVE ZERO-VOLUME DAYS
# ============================================================

trading_data = data[data["Volume"] > 0].copy()

# ============================================================
# BASE STOCHASTIC
# ============================================================

def raw_stochastic(df):

    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    lowest_low = low.rolling(10).min()
    highest_high = high.rolling(10).max()

    raw_k = (
        (close - lowest_low)
        / (highest_high - lowest_low)
    ) * 100

    return raw_k


# ============================================================
# METHOD A
# CURRENT BOT
# Raw K -> SMA 5 -> SMA 5
# ============================================================

raw_a = raw_stochastic(data)

slow_k_a = raw_a.rolling(5).mean()
slow_d_a = slow_k_a.rolling(5).mean()


# ============================================================
# METHOD B
# REMOVE ZERO-VOLUME
# Raw K -> SMA 5 -> SMA 5
# ============================================================

raw_b = raw_stochastic(trading_data)

slow_k_b = raw_b.rolling(5).mean()
slow_d_b = slow_k_b.rolling(5).mean()


# ============================================================
# METHOD C
# EMA -> EMA
# ============================================================

slow_k_c = raw_b.ewm(
    span=5,
    adjust=False
).mean()

slow_d_c = slow_k_c.ewm(
    span=5,
    adjust=False
).mean()


# ============================================================
# METHOD D
# SMA -> EMA
# ============================================================

slow_k_d = raw_b.rolling(5).mean()

slow_d_d = slow_k_d.ewm(
    span=5,
    adjust=False
).mean()


# ============================================================
# METHOD E
# EMA -> SMA
# ============================================================

slow_k_e = raw_b.ewm(
    span=5,
    adjust=False
).mean()

slow_d_e = slow_k_e.rolling(5).mean()


# ============================================================
# METHOD F
# COMMON STOCHASTIC FULL VARIANT
#
# First smooth raw %K by 5
# Then calculate %D using another SMA(5)
# ============================================================

k_f = raw_b.rolling(5).mean()
d_f = k_f.rolling(5).mean()


# ============================================================
# PRINT RESULTS
# ============================================================

print("\n" + "=" * 75)
print("RESULTS")
print("=" * 75)

print("\nMirae HOTS reference:")
print("K = 5.24")
print("D = 7.61")


print("\nMethod A — Current bot")
print(
    f"K = {float(slow_k_a.iloc[-1]):.2f}, "
    f"D = {float(slow_d_a.iloc[-1]):.2f}, "
    f"K > D = {float(slow_k_a.iloc[-1]) > float(slow_d_a.iloc[-1])}"
)


print("\nMethod B — Remove zero-volume")
print(
    f"K = {float(slow_k_b.iloc[-1]):.2f}, "
    f"D = {float(slow_d_b.iloc[-1]):.2f}, "
    f"K > D = {float(slow_k_b.iloc[-1]) > float(slow_d_b.iloc[-1])}"
)


print("\nMethod C — EMA → EMA")
print(
    f"K = {float(slow_k_c.iloc[-1]):.2f}, "
    f"D = {float(slow_d_c.iloc[-1]):.2f}, "
    f"K > D = {float(slow_k_c.iloc[-1]) > float(slow_d_c.iloc[-1])}"
)


print("\nMethod D — SMA → EMA")
print(
    f"K = {float(slow_k_d.iloc[-1]):.2f}, "
    f"D = {float(slow_d_d.iloc[-1]):.2f}, "
    f"K > D = {float(slow_k_d.iloc[-1]) > float(slow_d_d.iloc[-1])}"
)


print("\nMethod E — EMA → SMA")
print(
    f"K = {float(slow_k_e.iloc[-1]):.2f}, "
    f"D = {float(slow_d_e.iloc[-1]):.2f}, "
    f"K > D = {float(slow_k_e.iloc[-1]) > float(slow_d_e.iloc[-1])}"
)


print("\nMethod F — Stochastic Full / SMA")
print(
    f"K = {float(k_f.iloc[-1]):.2f}, "
    f"D = {float(d_f.iloc[-1]):.2f}, "
    f"K > D = {float(k_f.iloc[-1]) > float(d_f.iloc[-1])}"
)


# ============================================================
# LAST 10 VALUES
# ============================================================

print("\n" + "=" * 75)
print("LAST 10 VALUES — ZERO-VOLUME DAYS REMOVED")
print("=" * 75)

comparison = pd.DataFrame({
    "Close": trading_data["Close"],
    "Raw K": raw_b,
    "SMA K": slow_k_b,
    "SMA D": slow_d_b,
    "EMA K": slow_k_c,
    "EMA D": slow_d_c
})

print(comparison.tail(10).round(2))


# ============================================================
# DISTANCE FROM MIRAE
# ============================================================

mirae_k = 5.24
mirae_d = 7.61

print("\n" + "=" * 75)
print("DISTANCE FROM MIRAE HOTS")
print("=" * 75)

methods = {
    "A Current": (slow_k_a, slow_d_a),
    "B No Zero": (slow_k_b, slow_d_b),
    "C EMA/EMA": (slow_k_c, slow_d_c),
    "D SMA/EMA": (slow_k_d, slow_d_d),
    "E EMA/SMA": (slow_k_e, slow_d_e),
    "F Full SMA": (k_f, d_f),
}

for name, (k, d) in methods.items():

    k_value = float(k.iloc[-1])
    d_value = float(d.iloc[-1])

    distance = (
        abs(k_value - mirae_k)
        + abs(d_value - mirae_d)
    )

    print(
        f"{name:<15} "
        f"K={k_value:>6.2f} "
        f"D={d_value:>6.2f} "
        f"Distance={distance:>6.2f}"
    )
