from tradingview_screener import Query
import requests
from datetime import datetime, date
import yfinance as yf
import holidays
import os

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

today = datetime.now().strftime(
    "%d %b %Y"
)

# ====================================
# IHSG
# ====================================

print("Getting IHSG...")

ihsg = yf.Ticker("^JKSE")

hist = ihsg.history(period="2d")

prev_close = hist["Close"].iloc[-2]

today_close = hist["Close"].iloc[-1]

ihsg_change = (
    (today_close - prev_close)
    / prev_close
) * 100

# ====================================
# Sector Performance
# ====================================

print("Getting sector performance...")

sectors = {
    "Finance": "IDXFINANCE",
    "Mining": "IDXENERGY",
    "Industry": "IDXINDUST",
    "Consumer": "IDXNONCYC",
    "Infrastructure": "IDXINFRA",
    "Property": "IDXPROPERT",
}

sector_perf = []

for name, symbol in sectors.items():

    try:
        data = (
            Query()
            .set_markets("indonesia")
            .select("close", "change")
            .limit(1)
            .get_scanner_data()
        )

        # fallback using yfinance-style approach via TradingView
        _, df = (
            Query()
            .set_markets("indonesia")
            .search(symbol)
            .limit(1)
            .get_scanner_data()
        )

        if len(df) > 0:
            sector_perf.append((name, df.iloc[0]["change"]))

    except:
        continue

sector_perf = sorted(sector_perf, key=lambda x: x[1], reverse=True)

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

print("Getting market breadth...")

_, breadth_df = (
    Query()
    .set_markets("indonesia")
    .select(
        "name",
        "change"
    )
    .get_scanner_data()
)

advancers = (breadth_df["change"] > 0).sum()
decliners = (breadth_df["change"] < 0).sum()
flat = (breadth_df["change"] == 0).sum()
total = len(breadth_df)

# ====================================
# BUILD MESSAGE
# ====================================

message = (
    f"📊 IDX MARKET UPDATE\n"
    f"{today}\n\n"
)

# ====================================
# IHSG
# ====================================

message += (
    f"IHSG : {ihsg_change:.2f}%\n\n"
)

message += (
    f"BREADTH\n"
    f"Adv: {advancers}  Dec: {decliners}  Flat: {flat}\n\n"
)

message += "SECTORS\n"

for name, chg in sector_perf:
    message += f"{name:<12} {chg:>6.2f}%\n"

message += "\n"

# ====================================
# TOP GAINERS
# ====================================

message += "TOP GAINERS\n"

for i, (_, row) in enumerate(gainers_df.iterrows(), start=1):

    name = row['name'][:6].ljust(6)

    traded = (row['close'] * row['volume']) / 1_000_000_000

    message += (
        f"{i:>2}. {name} "
        f"{row['change']:>6.2f}% "
        f"Rp{traded:>7.1f}B\n"
    )

# ====================================
# TOP LOSERS
# ====================================

message += "\nTOP LOSERS\n"

for i, (_, row) in enumerate(losers_df.iterrows(), start=1):

    name = row['name'][:6].ljust(6)

    traded = (row['close'] * row['volume']) / 1_000_000_000

    message += (
        f"{i:>2}. {name} "
        f"{row['change']:>6.2f}% "
        f"Rp{traded:>7.1f}B\n"
    )

# ====================================
# TOP VALUE
# ====================================

message += "\nTOP VALUE\n"

for i, (_, row) in enumerate(value_df.iterrows(), start=1):

    name = row['name'][:6].ljust(6)

    traded = row['Value.Traded'] / 1_000_000_000

    message += (
        f"{i:>2}. {name} "
        f"{row['change']:>6.2f}% "
        f"Rp{traded:>7.1f}B\n"
    )

# ====================================
# PRINT MESSAGE
# ====================================

print(message)

# ====================================
# SEND TELEGRAM
# ====================================

send_telegram(message)
