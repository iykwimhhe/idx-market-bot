import os
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

import requests
import yfinance as yf
import holidays
from bs4 import BeautifulSoup

# ====================================
# TELEGRAM & ENVIRONMENT SETTINGS
# ====================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CACHE_FILE = "market_cache.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    )
}

# ====================================
# TELEGRAM FUNCTION (HTML <pre>)
# ====================================

def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

def send_telegram(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("BOT_TOKEN or CHAT_ID missing. Printing output only.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Telegram message limit is 4096 chars; split safely if needed
    chunks = [message[i:i + 3900] for i in range(0, len(message), 3900)]

    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": f"<pre>{escape_html(chunk)}</pre>",
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        response = requests.post(url, data=payload, timeout=20)
        print(response.status_code, response.text)
        time.sleep(0.5)

# ====================================
# CACHE HELPERS (FOR WEEKLY / DELAYED DATA)
# ====================================

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache: dict):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Cache save warning: {e}")

# ====================================
# HOLIDAY & WEEKEND CHECK
# ====================================

now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
today_date = now_wib.date()
indo_holidays = holidays.ID()

if today_date.weekday() >= 5:
    print("Weekend — market is closed.")
    exit()

if today_date in indo_holidays:
    print(f"Today is holiday: {indo_holidays[today_date]}")
    exit()

# ====================================
# DATA FETCHERS
# ====================================

def fetch_yf_batch(tickers: list[str]) -> dict:
    """Fetch last 5 days from Yahoo Finance and return level, chg, pct, and age."""
    results = {}
    if not tickers:
        return results

    try:
        raw = yf.download(
            tickers,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
    except Exception as e:
        print(f"Yahoo batch download failed: {e}")
        return results

    now_utc = datetime.now(timezone.utc)

    for t in tickers:
        try:
            df = raw.copy() if len(tickers) == 1 else raw[t].copy()
            df = df.dropna(subset=["Close"])
            if len(df) < 2:
                continue

            last_ts = df.index[-1]
            if last_ts.tzinfo is None:
                last_dt = datetime.combine(last_ts.date(), datetime.min.time(), tzinfo=timezone.utc)
            else:
                last_dt = last_ts.astimezone(timezone.utc)

            age_hours = (now_utc - last_dt).total_seconds() / 3600.0
            last_close = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2])
            chg = last_close - prev_close
            pct = (chg / prev_close) * 100 if prev_close != 0 else 0.0

            results[t] = {
                "level": last_close,
                "chg": chg,
                "pct": pct,
                "stale": age_hours > 36,  # Daily bars older than ~1.5 days
                "source": "Yahoo",
                "timestamp": last_ts.strftime("%Y-%m-%d"),
            }
        except Exception:
            continue

    return results


def fetch_tv_symbol(symbol: str) -> dict | None:
    """Query TradingView's public symbol scanner endpoint directly."""
    url = "https://scanner.tradingview.com/symbol"
    params = {
        "symbol": symbol,
        "fields": "close,change,change_abs,update_mode,lp_time",
        "no_404": "true",
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        close = data.get("close")
        pct = data.get("change")
        chg = data.get("change_abs")
        if close is None:
            return None

        lp_time = data.get("lp_time")
        stale = False
        ts_str = now_wib.strftime("%Y-%m-%d %H:%M WIB")
        if lp_time:
            dt_wib = datetime.fromtimestamp(lp_time, tz=ZoneInfo("Asia/Jakarta"))
            age_hours = (now_wib - dt_wib).total_seconds() / 3600.0
            stale = age_hours > 24
            ts_str = dt_wib.strftime("%Y-%m-%d %H:%M WIB")

        return {
            "level": float(close),
            "chg": float(chg) if chg is not None else None,
            "pct": float(pct) if pct is not None else None,
            "stale": stale,
            "source": "TradingView",
            "timestamp": ts_str,
        }
    except Exception:
        return None


def fetch_headlines(limit: int = 6) -> list[str]:
    """Pull top macro & market-moving headlines from Reuters/CNBC/Investing RSS."""
    feeds = [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Top News
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",   # CNBC Economy
        "https://feeds.marketwatch.com/marketwatch/topstories/",  # MarketWatch
    ]
    headlines = []
    seen = set()

    for feed_url in feeds:
        if len(headlines) >= limit:
            break
        try:
            r = requests.get(feed_url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title_el = item.find("title")
                if title_el is None or not title_el.text:
                    continue
                title = " ".join(title_el.text.strip().split())
                # Keep one-line concise headline
                if len(title) > 78:
                    title = title[:75].rstrip() + "..."
                key = title.lower()[:35]
                if key not in seen:
                    seen.add(key)
                    headlines.append(title)
                if len(headlines) >= limit:
                    break
        except Exception:
            continue

    return headlines if headlines else ["n/a (RSS feed unavailable)"]


def fetch_indonesia_5y_cds(cache: dict) -> dict | None:
    """Attempt public scrape of Indonesia 5Y CDS; fallback to cache with timestamp."""
    try:
        url = "https://www.worldgovernmentbonds.com/cds-historical-data/indonesia/5-years/"
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text(" ", strip=True)
            m = re.search(r"5 Years CDS\s*[:\-]?\s*(\d+\.\d+)", text, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                entry = {
                    "level": val,
                    "chg": None,
                    "pct": None,
                    "stale": False,
                    "source": "WGB",
                    "timestamp": now_wib.strftime("%Y-%m-%d"),
                }
                cache["ID_5Y_CDS"] = entry
                return entry
    except Exception:
        pass

    if "ID_5Y_CDS" in cache:
        cached = cache["ID_5Y_CDS"].copy()
        cached["stale"] = True
        return cached
    return None


def fetch_ici_coal(cache: dict) -> dict:
    """Attempt public scrape of weekly ICI 1-5; fallback to cache with last update date."""
    ici_data = {}
    try:
        url = "https://www.jwcindonesia.com/price-index"
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            text = soup.get_text("\n", strip=True)
            for idx in range(1, 6):
                m = re.search(
                    rf"ICI\s*{idx}.*?(\d{{2,3}}\.\d{{2}})",
                    text,
                    re.IGNORECASE | re.DOTALL,
                )
                if m:
                    ici_data[f"ICI {idx}"] = {
                        "level": float(m.group(1)),
                        "chg": None,
                        "pct": None,
                        "stale": True,
                        "source": "Argus/Coalindo",
                        "timestamp": now_wib.strftime("%Y-%m-%d"),
                    }
    except Exception:
        pass

    if ici_data:
        cache["ICI"] = ici_data
        return ici_data

    return cache.get("ICI", {})

# ====================================
# FORMATTING HELPER
# ====================================

def format_line(
    label: str,
    item: dict | None,
    asset_type: str = "other",
    decimals: int = 2,
    is_yield: bool = False,
    force_tag: str | None = None,
) -> str:
    """
    Formats: Label : Level | Chg | %Chg [!!] [(Source, Timestamp)]
    Rules:
    - Missing -> 'n/a'
    - Flag moves > 2% for equities or > 3% for commodities with '!!'
    - Append source and timestamp if delayed/older than 24h
    """
    label_col = f"{label:<16}"
    if not item or item.get("level") is None:
        return f"{label_col}: n/a"

    lvl = item["level"]
    chg = item.get("chg")
    pct = item.get("pct")

    lvl_str = f"{lvl:,.{decimals}f}%" if is_yield else f"{lvl:,.{decimals}f}"
    chg_str = f"{chg:+,.{decimals}f}" if chg is not None else "n/a"
    pct_str = f"{pct:+.2f}%" if pct is not None else "n/a"

    flag = ""
    if pct is not None:
        if asset_type == "equity" and abs(pct) > 2.0:
            flag = " !!"
        elif asset_type == "commodity" and abs(pct) > 3.0:
            flag = " !!"

    tag = ""
    if force_tag:
        tag = f" ({force_tag})"
    elif item.get("stale"):
        src = item.get("source", "Delayed")
        ts = item.get("timestamp", "")
        tag = f" ({src}, {ts})"

    return f"{label_col}: {lvl_str} | {chg_str} | {pct_str}{flag}{tag}"

# ====================================
# MAIN EXECUTION
# ====================================

def main():
    cache = load_cache()

    # 1. Batch Yahoo Finance Tickers
    yf_tickers = [
        # Global Equities
        "^DJI", "^IXIC", "^GSPC", "^VIX",
        "^FTSE", "^GDAXI", "^FCHI",
        "YM=F", "^JKSE", "^N225", "^HSI", "^KS11", "000001.SS",
        "EIDO",
        # DXY & FX
        "DX-Y.NYB", "USDIDR=X", "SGDIDR=X", "MYRIDR=X", "JPYIDR=X", "AUDIDR=X",
        # US Yields
        "^TNX", "^TYX",
        # Commodities
        "CL=F", "BZ=F", "GC=F", "SI=F", "HG=F",
        "ZL=F", "ZC=F", "ZW=F", "NG=F",
    ]
    print("Fetching Yahoo Finance data...")
    yf_data = fetch_yf_batch(yf_tickers)

    # Helper to pick TV first, fallback to Yahoo
    def get_metric(tv_sym: str | None = None, yf_sym: str | None = None) -> dict | None:
        if tv_sym:
            res = fetch_tv_symbol(tv_sym)
            if res is not None:
                return res
        if yf_sym and yf_sym in yf_data:
            return yf_data[yf_sym]
        return None

    print("Fetching TradingView quotes (Bonds, Metals, China, Coal)...")
    # Bonds
    us_2y = get_metric("TVC:US02Y")
    us_10y = get_metric("TVC:US10Y", "^TNX")
    us_20y = get_metric("TVC:US20Y")
    id_1y = get_metric("TVC:ID01Y")
    id_5y = get_metric("TVC:ID05Y")
    id_10y = get_metric("TVC:ID10Y")

    # Metals & Softs via TradingView
    tin = get_metric("LME:TIN3M") or get_metric("MCX:TIN1!")
    nickel = get_metric("LME:NID3M") or get_metric("MCX:NICKEL1!")
    aluminum = get_metric("LME:AHD3M") or get_metric("COMEX:ALI1!")
    copper = get_metric("COMEX:HG1!", "HG=F")
    cpo = get_metric("MYX:FCPO1!")
    rubber = get_metric("SGX:TF1!")

    # China Market (DCE / SHFE)
    iron_ore = get_metric("DCE:I1!") or get_metric("SGX:FEF1!")
    hrc = get_metric("SHFE:HC1!")
    cn_thermal_coal = get_metric("CZCE:ZC1!")
    coking_coal = get_metric("DCE:JM1!")

    # Coal Forward Curves (ICE Newcastle & API2 Rotterdam)
    ncf_1 = get_metric("ICEEUR:NCF1!")
    ncf_2 = get_metric("ICEEUR:NCF2!")
    ncf_3 = get_metric("ICEEUR:NCF3!")

    rot_1 = get_metric("ICEEUR:ATW1!")
    rot_2 = get_metric("ICEEUR:ATW2!")
    rot_3 = get_metric("ICEEUR:ATW3!")

    # CDS & ICI Weekly
    id_cds = fetch_indonesia_5y_cds(cache)
    ici_map = fetch_ici_coal(cache)
    save_cache(cache)

    # Headlines
    print("Fetching headlines...")
    headlines = fetch_headlines(6)

    # ====================================
    # ASSEMBLE REPORT
    # ====================================

    date_str = now_wib.strftime("%A, %d %b %Y")
    time_str = now_wib.strftime("%H:%M")

    lines = [
        "TODAY'S MARKET OVERVIEW",
        f"{date_str} | {time_str} WIB",
        "",
        "HEADLINES",
    ]
    for h in headlines:
        lines.append(f"- {h}")

    # GLOBAL MARKETS
    lines += [
        "",
        "GLOBAL MARKETS",
        format_line("DJIA", get_metric("DJ:DJI", "^DJI"), "equity", 2),
        format_line("Nasdaq", get_metric("NASDAQ:IXIC", "^IXIC"), "equity", 2),
        format_line("S&P 500", get_metric("SP:SPX", "^GSPC"), "equity", 2),
        format_line("VIX", get_metric("CBOE:VIX", "^VIX"), "other", 2),
        format_line("FTSE 100", get_metric("FTSE:UKX", "^FTSE"), "equity", 2),
        format_line("DAX", get_metric("XETR:DAX", "^GDAXI"), "equity", 2),
        format_line("CAC 40", get_metric("EURONEXT:PX1", "^FCHI"), "equity", 2),
        format_line("Dow Futures", get_metric("CBOT_MINI:YM1!", "YM=F"), "equity", 2),
        format_line("IDX (IHSG)", get_metric("IDX:COMPOSITE", "^JKSE"), "equity", 2),
        format_line("Nikkei", get_metric("TVC:NI225", "^N225"), "equity", 2),
        format_line("HSI", get_metric("HSI:HSI", "^HSI"), "equity", 2),
        format_line("KOSPI", get_metric("KRX:KOSPI", "^KS11"), "equity", 2),
        format_line("Shanghai", get_metric("SSE:000001", "000001.SS"), "equity", 2),
        format_line("EIDO", get_metric("AMEX:EIDO", "EIDO"), "equity", 2),
        format_line("Indo 5Y CDS", id_cds, "other", 2),
        format_line("USD Index", get_metric("TVC:DXY", "DX-Y.NYB"), "other", 2),
        format_line("USD/IDR", get_metric("FX_IDC:USDIDR", "USDIDR=X"), "other", 2),
    ]

    # GOV. BONDS
    lines += [
        "",
        "GOV. BONDS",
        format_line("US 2Y", us_2y, "other", 3, is_yield=True),
        format_line("US 10Y", us_10y, "other", 3, is_yield=True),
        format_line("US 20Y", us_20y, "other", 3, is_yield=True),
        format_line("Indonesia 1Y", id_1y, "other", 3, is_yield=True),
        format_line("Indonesia 5Y", id_5y, "other", 3, is_yield=True),
        format_line("Indonesia 10Y", id_10y, "other", 3, is_yield=True),
    ]

    # COMMODITIES
    lines += [
        "",
        "COMMODITIES",
        format_line("WTI", get_metric("NYMEX:CL1!", "CL=F"), "commodity", 2),
        format_line("Brent", get_metric("ICEEUR:BRN1!", "BZ=F"), "commodity", 2),
        format_line("Gold", get_metric("COMEX:GC1!", "GC=F"), "commodity", 2),
        format_line("Silver", get_metric("COMEX:SI1!", "SI=F"), "commodity", 2),
        format_line("Copper", copper, "commodity", 3),
        format_line("Tin", tin, "commodity", 2),
        format_line("Nickel", nickel, "commodity", 2),
        format_line("Aluminum", aluminum, "commodity", 2),
        format_line("CPO", cpo, "commodity", 2),
        format_line("Soybean Oil", get_metric("CBOT:ZL1!", "ZL=F"), "commodity", 2),
        format_line("Corn", get_metric("CBOT:ZC1!", "ZC=F"), "commodity", 2),
        format_line("Wheat", get_metric("CBOT:ZW1!", "ZW=F"), "commodity", 2),
        format_line("Natural Gas", get_metric("NYMEX:NG1!", "NG=F"), "commodity", 3),
        format_line("Rubber", rubber, "commodity", 2),
    ]

    # CHINA MARKET
    lines += [
        "",
        "CHINA MARKET",
        format_line("Iron Ore", iron_ore, "commodity", 2),
        format_line("HRC", hrc, "commodity", 2),
        format_line("Thermal Coal", cn_thermal_coal, "commodity", 2),
        format_line("Coking Coal", coking_coal, "commodity", 2),
    ]

    # COAL
    lines += [
        "",
        "COAL",
        format_line("Newcastle M1", ncf_1, "commodity", 2),
        format_line("Newcastle M2", ncf_2, "commodity", 2),
        format_line("Newcastle M3", ncf_3, "commodity", 2),
        format_line("Rotterdam M1", rot_1, "commodity", 2),
        format_line("Rotterdam M2", rot_2, "commodity", 2),
        format_line("Rotterdam M3", rot_3, "commodity", 2),
    ]
    for i in range(1, 6):
        key = f"ICI {i}"
        item = ici_map.get(key)
        tag = None
        if item:
            tag = f"{item.get('source', 'Argus/Coalindo')}, updated {item.get('timestamp', 'n/a')}"
        lines.append(format_line(f"{key} (Weekly)", item, "commodity", 2, force_tag=tag))

    # CURRENCY
    lines += [
        "",
        "CURRENCY",
        format_line("USD/IDR", get_metric("FX_IDC:USDIDR", "USDIDR=X"), "other", 2),
        format_line("SGD/IDR", get_metric("FX_IDC:SGDIDR", "SGDIDR=X"), "other", 2),
        format_line("MYR/IDR", get_metric("FX_IDC:MYRIDR", "MYRIDR=X"), "other", 2),
        format_line("JPY/IDR", get_metric("FX_IDC:JPYIDR", "JPYIDR=X"), "other", 2),
        format_line("AUD/IDR", get_metric("FX_IDC:AUDIDR", "AUDIDR=X"), "other", 2),
    ]

    # 3 SHORT BULLETS FOR INDONESIA
    usdidr = get_metric("FX_IDC:USDIDR", "USDIDR=X")
    id10y_val = id_10y["level"] if id_10y else None

    idr_note = "IDR tracking global USD/yield moves"
    if usdidr and usdidr.get("pct") is not None:
        direction = "weakened" if usdidr["pct"] > 0 else "strengthened"
        idr_note = f"USD/IDR {direction} {usdidr['pct']:+.2f}% to {usdidr['level']:,.0f}"
        if id10y_val:
            idr_note += f" with Indo 10Y at {id10y_val:.2f}%"

    coal_note = "Coal benchmarks mixed; watch China restocking"
    if ncf_1 and ncf_1.get("pct") is not None:
        coal_note = f"Newcastle M1 moved {ncf_1['pct']:+.2f}% (${ncf_1['level']:,.2f}/t), guiding IDX coal margins"

    agri_metal_parts = []
    if cpo and cpo.get("pct") is not None:
        agri_metal_parts.append(f"CPO {cpo['pct']:+.2f}% (MYR {cpo['level']:,.0f})")
    if nickel and nickel.get("pct") is not None:
        agri_metal_parts.append(f"Nickel {nickel['pct']:+.2f}% (${nickel['level']:,.0f})")
    agri_metal_note = (
        "; ".join(agri_metal_parts) + " steering planter & smelter flows"
        if agri_metal_parts
        else "CPO & Nickel flows remain key drivers for IDX exporters"
    )

    lines += [
        "",
        "WHAT MATTERS MOST FOR INDONESIA",
        f"- {idr_note}.",
        f"- {coal_note}.",
        f"- {agri_metal_note}.",
    ]

    final_message = "\n".join(lines)
    print(final_message)
    send_telegram(final_message)


if __name__ == "__main__":
    main()
