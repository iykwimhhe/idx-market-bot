import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# SETTINGS
# ============================================================

WIB = ZoneInfo("Asia/Jakarta")
now = datetime.now(WIB)

print("=" * 70)
print("MARKET BRIEF DATA TEST")
print(f"{now.strftime('%d-%b-%Y | %H:%M')} WIB")
print("=" * 70)


# ============================================================
# HELPERS
# ============================================================

def get_yahoo(ticker):
    """
    Get the latest available Yahoo Finance price.
    Returns:
        price, previous_close, change, change_pct, timestamp
    """

    try:
        data = yf.Ticker(ticker)

        hist = data.history(
            period="5d",
            interval="1d",
            auto_adjust=False
        )

        if hist.empty:
            return None

        hist = hist.dropna(subset=["Close"])

        if len(hist) == 0:
            return None

        latest = hist.iloc[-1]

        price = float(latest["Close"])

        if len(hist) >= 2:
            previous = float(hist.iloc[-2]["Close"])
            change = price - previous

            if previous != 0:
                change_pct = (change / previous) * 100
            else:
                change_pct = None
        else:
            previous = None
            change = None
            change_pct = None

        timestamp = hist.index[-1]

        return {
            "price": price,
            "previous": previous,
            "change": change,
            "change_pct": change_pct,
            "timestamp": timestamp
        }

    except Exception as e:
        print(f"ERROR {ticker}: {e}")
        return None


def print_result(name, ticker):
    result = get_yahoo(ticker)

    if result is None:
        print(f"{name:<18} n/a")
        return

    price = result["price"]
    change = result["change"]
    change_pct = result["change_pct"]

    if change is None:
        print(f"{name:<18} {price:,.2f}    n/a       n/a")
    else:
        flag = ""

        if abs(change_pct) > 2:
            flag = " !!"

        print(
            f"{name:<18} "
            f"{price:>12,.2f} "
            f"{change:>12,.2f} "
            f"{change_pct:>8.2f}%{flag}"
        )


# ============================================================
# GLOBAL MARKETS
# ============================================================

print("\nGLOBAL MARKETS")
print("-" * 70)

global_markets = {
    "DJIA": "^DJI",
    "Nasdaq": "^IXIC",
    "S&P 500": "^GSPC",
    "VIX": "^VIX",
    "FTSE 100": "^FTSE",
    "DAX": "^GDAXI",
    "CAC 40": "^FCHI",
    "Nikkei": "^N225",
    "HSI": "^HSI",
    "KOSPI": "^KS11",
    "Shanghai": "000001.SS",
    "EIDO": "EIDO",
    "USD Index": "DX-Y.NYB",
    "USD/IDR": "IDR=X",
}

for name, ticker in global_markets.items():
    print_result(name, ticker)


# ============================================================
# US GOVERNMENT BONDS
# ============================================================

print("\nGOV. BONDS — US")
print("-" * 70)

us_bonds = {
    "US 2Y": "^UST2Y",
    "US 5Y": "^FVX",
    "US 10Y": "^TNX",
    "US 20Y": "^UST20Y",
    "US 30Y": "^TYX",
}

for name, ticker in us_bonds.items():
    print_result(name, ticker)


# ============================================================
# COMMODITIES
# ============================================================

print("\nCOMMODITIES")
print("-" * 70)

commodities = {
    "WTI": "CL=F",
    "Brent": "BZ=F",
    "Gold": "GC=F",
    "Silver": "SI=F",
    "Copper": "HG=F",
    "Corn": "ZC=F",
    "Wheat": "ZW=F",
    "Natural Gas": "NG=F",
    "Soybean Oil": "ZL=F",
    "Rubber": "OJ=F",
}

for name, ticker in commodities.items():
    print_result(name, ticker)


# ============================================================
# LME METALS
# ============================================================

print("\nLME / INDUSTRIAL METALS")
print("-" * 70)

lme = {
    "Copper": "HG=F",
    "Aluminum": "ALI=F",
    "Nickel": "NI=F",
    "Tin": "SN=F",
}

for name, ticker in lme.items():
    print_result(name, ticker)


# ============================================================
# CHINA MARKET
# ============================================================

print("\nCHINA MARKET")
print("-" * 70)

china = {
    "Iron Ore": "TIO=F",
    "Thermal Coal": "MTF=F",
    "Coking Coal": "JMM=F",
}

for name, ticker in china.items():
    print_result(name, ticker)


# ============================================================
# CURRENCY
# ============================================================

print("\nCURRENCY")
print("-" * 70)

currencies = {
    "USD/IDR": "IDR=X",
    "SGD/IDR": "SGDIDR=X",
    "MYR/IDR": "MYRIDR=X",
    "JPY/IDR": "JPYIDR=X",
    "AUD/IDR": "AUDIDR=X",
}

for name, ticker in currencies.items():
    print_result(name, ticker)


# ============================================================
# SUMMARY
# ============================================================

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print()
print("This is ONLY a data-source test.")
print("No Telegram message has been sent.")
print("No existing IDX bot files are modified.")
