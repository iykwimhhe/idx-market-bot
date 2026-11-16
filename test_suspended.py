from tradingview_screener import Query

print("Getting Indonesia market data...")
print("=" * 50)

_, df = (
    Query()
    .set_markets("indonesia")
    .select(
        "name",
        "close",
        "change",
        "volume",
        "Value.Traded"
    )
    .limit(1000)
    .get_scanner_data()
)

print(f"Total stocks returned: {len(df)}")
print()

tmpo = df[df["name"] == "TMPO"]

if tmpo.empty:
    print("TMPO was NOT returned by TradingView.")
else:
    print("TMPO FOUND:")
    print(tmpo.to_string(index=False))
