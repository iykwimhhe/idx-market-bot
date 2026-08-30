from tradingview_screener import Query
import requests
from datetime import datetime, date
import yfinance as yf
import holidays
import os
import pandas as pd

# ====================================
# TELEGRAM SETTINGS
# ====================================

import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ====================================
# TELEGRAM FUNCTION
# ====================================

def send_telegram(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": f"<pre>{message}</pre>",
        "parse_mode": "HTML"
    }

    response = requests.post(url, data=payload)

    print(response.status_code)
    print(response.text)

# ====================================
# INDONESIAN HOLIDAY CHECK
# ====================================

today_date = date.today()

indo_holidays = holidays.ID()

if today_date in indo_holidays:

    print(
        f"Today is holiday: "
        f"{indo_holidays[today_date]}"
    )

    exit()

# ====================================
# DATE
# ====================================

today = datetime.now().strftime("%A, %d %b %Y")

# ====================================
# RUN TIME
# ====================================

from zoneinfo import ZoneInfo

run_time = datetime.now(
    ZoneInfo("Asia/Jakarta")
).strftime("%H:%M WIB")

# ====================================
# IHSG
# ====================================

print("Getting IHSG...")

ihsg = yf.Ticker("^JKSE")

hist = ihsg.history(period="5d")

hist = hist.dropna()

if len(hist) < 2:
    print("IHSG data not sufficient")
    exit()

prev_close = hist["Close"].iloc[-2]
today_close = hist["Close"].iloc[-1]

ihsg_change = ((today_close - prev_close) / prev_close) * 100

# ====================================
# Sector Performance
# ====================================

print("Getting sector performance...")

_, sector_df = (
    Query()
    .set_markets("indonesia")
    .select("name", "change", "sector")
    .limit(1000)
    .get_scanner_data()
)
sector_perf = sector_df.groupby("sector")["change"].mean()
sector_perf = sector_perf.sort_values(ascending=False)

# ====================================
# TOP GAINERS
# ====================================

print("Getting top gainers...")

_, gainers_df = (

    Query()

    .set_markets("indonesia")

    .select(
        "name",
        "close",
        "change",
        "volume"
    )

    .order_by(
        "change",
        ascending=False
    )

    .limit(20)

    .get_scanner_data()

)

# ====================================
# TOP LOSERS
# ====================================

print("Getting top losers...")

_, losers_df = (

    Query()

    .set_markets("indonesia")

    .select(
        "name",
        "close",
        "change",
        "volume"
    )

    .order_by(
        "change",
        ascending=True
    )

    .limit(20)

    .get_scanner_data()

)

# ====================================
# TOP VALUE
# ====================================

print("Getting top value...")

_, value_df = (

    Query()

    .set_markets("indonesia")

    .select(
        "name",
        "close",
        "change",
        "volume",
        "Value.Traded"
    )

    .order_by(
        "Value.Traded",
        ascending=False
    )

    .limit(20)

    .get_scanner_data()

)

print("Getting full market breadth...")

_, all_df = (
    Query()
    .set_markets("indonesia")
    .select("name", "change")
    .limit(1000)   # important
    .get_scanner_data()
)

all_df = all_df.dropna()

advancers = (all_df["change"] > 0).sum()
decliners = (all_df["change"] < 0).sum()
flat = (all_df["change"] == 0).sum()
total = len(all_df)

ratio = advancers / (decliners + 1)

if ratio > 1.2:
    sentiment = "🟢 Strong Bullish"
elif ratio > 1.0:
    sentiment = "🟡 Mixed"
else:
    sentiment = "🔴 Weak"

# ====================================
# STOCHASTIC GOLDEN CROSS 10,5,5
# ====================================

print("Scanning Stochastic Golden Cross 10,5,5...")

_, stock_list_df = (
    Query()
    .set_markets("indonesia")
    .select(
        "name",
        "close",
        "change",
        "Value.Traded"
    )
    .limit(1000)
    .get_scanner_data()
)
tradingview_data = {}

for _, row in stock_list_df.iterrows():

    tradingview_data[row["name"]] = {
        "close": row["close"],
        "change": row["change"],
        "value_traded": row["Value.Traded"]
    }

stoch_signals = []

for symbol in stock_list_df["name"].dropna().unique():

    ticker = symbol + ".JK"

    try:
        data = yf.download(
            ticker,
            period="3mo",
            interval="1d",
            progress=False,
            auto_adjust=False
        )

        if data.empty or len(data) < 20:
            continue

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        high = data["High"]
        low = data["Low"]
        close = data["Close"]

        lowest_low = low.rolling(10).min()
        highest_high = high.rolling(10).max()

        raw_k = (
            (close - lowest_low)
            / (highest_high - lowest_low)
        ) * 100

        k = raw_k.rolling(5).mean()
        d = k.rolling(5).mean()

        if len(k.dropna()) < 2:
            continue

        today_k = float(k.iloc[-1])
        today_d = float(d.iloc[-1])

        # Golden Cross condition
        golden_cross = (
            today_k > today_d
            and today_k < 30
        )

        if golden_cross:

        last_price = float(close.iloc[-1])
        
        # Get transaction value and price change from TradingView
        tv_data = tradingview_data.get(symbol)
        
        if tv_data is None:
            continue
        
        transaction_value = float(
            tv_data["value_traded"]
        )
        
        price_change = float(
            tv_data["change"]
        )
        
        # Minimum transaction value: Rp250 million
        if transaction_value >= 250_000_000:
        
            stoch_signals.append({
                "name": symbol,
                "close": last_price,
                "change": price_change,
                "transaction_value": transaction_value,
                "k": today_k
            })

    except Exception as e:

        print(f"Skipping {symbol}: {e}")
        continue

# Sort by transaction value
stoch_signals = sorted(
    stoch_signals,
    key=lambda x: x["k"]
)

# Maximum 20 stocks
stoch_signals = stoch_signals[:20]

# ====================================
# BUILD MESSAGE
# ====================================

message = (
    f"📊 IDX MARKET UPDATE\n"
    f"{today}\n"
    f"Run: {run_time}\n\n"
)

# ====================================
# IHSG
# ====================================

message += (
    f"IHSG : {today_close:,.2f} ({ihsg_change:+.2f}%)\n\n"
)

message += (
    f"MARKET BREADTH\n"
    f"{sentiment}\n"
    f"🟢 {advancers}  🔴 {decliners}  🟡 {flat}\n\n"
)

message += "SECTORS\n"

for sector, chg in sector_perf.items():

    if str(sector) == "nan":
        continue

    arrow = "🟢" if chg > 0 else "🔴"

    sector_name = str(sector)[:18].ljust(18)

    message += (
        f"{arrow} {sector_name} "
        f"{chg:>6.2f}%\n"
    )

message += "\n"

# ====================================
# TOP GAINERS
# ====================================

message += "🔥 TOP GAINERS\n━━━━━━━━━━━━━━━━\n"

for i, (_, row) in enumerate(gainers_df.iterrows(), start=1):

    name = row['name'][:6].ljust(6)

    traded = (row['close'] * row['volume']) / 1_000_000_000

    message += (
        f"{i:>2}. {name} "
        f"{row['close']:>7,.0f} "
        f"{row['change']:>6.2f}% "
        f"Rp{traded:>7.1f}B\n"
    )

# ====================================
# TOP LOSERS
# ====================================

message += "\n🩸 TOP LOSERS\n━━━━━━━━━━━━━━━━\n"

for i, (_, row) in enumerate(losers_df.iterrows(), start=1):

    name = row['name'][:6].ljust(6)

    traded = (row['close'] * row['volume']) / 1_000_000_000

    message += (
        f"{i:>2}. {name} "
        f"{row['close']:>7,.0f} "
        f"{row['change']:>6.2f}% "
        f"Rp{traded:>7.1f}B\n"
    )

# ====================================
# TOP VALUE
# ====================================

message += "\n💰 TOP VALUE\n━━━━━━━━━━━━━━━━\n"

for i, (_, row) in enumerate(value_df.iterrows(), start=1):

    name = row['name'][:6].ljust(6)

    traded = row['Value.Traded'] / 1_000_000_000

    message += (
        f"{i:>2}. {name} "
        f"{row['close']:>7,.0f} "
        f"Rp{traded:>7.1f}B "
        f"{row['change']:>6.2f}%\n"
)

# ====================================
# STOCHASTIC GOLDEN CROSS MESSAGE
# ====================================

message += "\n⚡ STOCHASTIC GOLDEN CROSS 10,5,5\n"
message += "━━━━━━━━━━━━━━━━\n"

if not stoch_signals:

    message += "No signal today.\n"

else:

    for i, stock in enumerate(stoch_signals, start=1):

        name = stock["name"][:6].ljust(6)

        traded = (
            stock["transaction_value"]
            / 1_000_000_000
        )

        message += (
            f"{i:>2}. {name} "
            f"{stock['close']:>7,.0f} "
            f"Rp{traded:>7.1f}B "
            f"{stock['change']:>6.2f}%\n"
        )

# ====================================
# PRINT MESSAGE
# ====================================

print(message)

# ====================================
# SEND TELEGRAM
# ====================================

send_telegram(message)
