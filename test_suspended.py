from tradingview_screener import Query

print("Testing TMPO TradingView data...")
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
    .where(
        "name",
        "equal",
        "TMPO"
    )
    .get_scanner_data()
)

print(df)
