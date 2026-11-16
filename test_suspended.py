import yfinance as yf
import pandas as pd

test_tickers = [
    "TMPO.JK",
    "BBCA.JK",
    "BMRI.JK",
    "BREN.JK",
    "BBRI.JK"
]

print("Testing latest actual trading date...")
print("=" * 60)

for ticker in test_tickers:

    print(f"\nChecking {ticker}...")

    try:
        data = yf.download(
            ticker,
            period="10d",
            interval="1d",
            auto_adjust=False,
            progress=False
        )

        if data.empty:
            print("  No Yahoo data found.")
            continue

        # Handle possible multi-level columns
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        # Remove non-trading days
        data = data[data["Volume"] > 0].copy()

        if data.empty:
            print("  No trading days with volume found.")
            continue

        latest = data.iloc[-1]

        print(f"  Latest trading date : {data.index[-1].date()}")
        print(f"  Close               : {latest['Close']}")
        print(f"  Volume              : {latest['Volume']:,}")

    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "=" * 60)
print("Test complete.")
