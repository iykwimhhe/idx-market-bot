from tradingview_screener import Query
import requests
from datetime import datetime
import yfinance as yf

# ====================================
# TELEGRAM SETTINGS
# ====================================

BOT_TOKEN = "8920968558:AAFLckHxHMTGL3GEhR2JBOXivxxCMKgTdxw"
CHAT_ID = "@idxdailymarketdata"

# ====================================
# TELEGRAM FUNCTION
# ====================================

def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    payload = {

        "chat_id": CHAT_ID,

        "text": f"```{message}```",

        "parse_mode": "Markdown"

    }

    response = requests.post(
        url,
        data=payload
    )

    print(response.text)

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

# ====================================
# TOP GAINERS
# ====================================

message += "🔥 TOP GAINERS\n"

for i, (_, row) in enumerate(
    gainers_df.iterrows(),
    start=1
):

    traded = (
        row['close']
        * row['volume']
    ) / 1_000_000_000

    message += (

        f"{i:>2}. "

        f"{row['name']:<6}"

        f"{row['change']:>8.2f}%   "

        f"Rp {traded:.1f}B\n"

    )

# ====================================
# TOP LOSERS
# ====================================

message += "\n🩸 TOP LOSERS\n"

for i, (_, row) in enumerate(
    losers_df.iterrows(),
    start=1
):

    traded = (
        row['close']
        * row['volume']
    ) / 1_000_000_000

    message += (

        f"{i:>2}. "

        f"{row['name']:<6}"

        f"{row['change']:>8.2f}%   "

        f"Rp {traded:.1f}B\n"

    )

# ====================================
# TOP VALUE
# ====================================

message += "\n💰 TOP VALUE\n"

for i, (_, row) in enumerate(
    value_df.iterrows(),
    start=1
):

    traded = (
        row['Value.Traded']
        / 1_000_000_000
    )

    message += (

        f"{i:>2}. "

        f"{row['name']:<6}"

        f"Rp {traded:.1f}B\n"

    )

# ====================================
# PRINT MESSAGE
# ====================================

print(message)

# ====================================
# SEND TELEGRAM
# ====================================

send_telegram(message)