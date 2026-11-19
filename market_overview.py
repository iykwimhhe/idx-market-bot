from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import time
from bs4 import BeautifulSoup
import feedparser
import pytz
import requests
import yfinance as yf

# ==========================================
# 1. CONFIGURATION & ENVIRONMENT
# ==========================================
WIB = pytz.timezone("Asia/Jakarta")
CACHE_FILE = Path("ici_coal_cache.json")

# Set these via environment variables or replace directly for local testing
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.cnbcindonesia.com/market/rss/",
    "https://finance.yahoo.com/news/rssindex",
]

MARKET_SECTIONS = {
    "GLOBAL MARKETS": [
        ("DJIA", "^DJI"),
        ("Nasdaq", "^IXIC"),
        ("S&P 500", "^GSPC"),
        ("VIX", "^VIX"),
        ("", None),
        ("FTSE 100", "^FTSE"),
        ("DAX", "^GDAXI"),
        ("CAC 40", "^FCHI"),
        ("", None),
        ("Dow Fut", "YM=F"),
        ("IDX", "^JKSE"),
        ("Nikkei", "^N225"),
        ("HSI", "^HSI"),
        ("KOSPI", "^KS11"),
        ("Shanghai", "000001.SS"),
        ("", None),
        ("EIDO", "EIDO"),
        ("IndoCDS 5yr", "SCRAPE_INDO_CDS"),
        ("", None),
        ("USD Index", "DX-Y.NYB"),
        ("USD/IDR", "USDIDR=X"),
    ],
    "GOV. BONDS": [
        ("DXY", "DX-Y.NYB"),
        ("U.S 2Y", "^IRX"),
        ("U.S 10Y", "^TNX"),
        ("U.S 20Y", "^TYX"),
        ("Indo 10Y", "SCRAPE_INDO_10Y"),
    ],
    "COMMODITIES": [
        ("Oil (WTI)", "CL=F"),
        ("Brent Crude", "BZ=F"),
        ("Gold", "GC=F"),
        ("Silver", "SI=F"),
        ("Copper", "HG=F"),
        ("Corn", "ZC=F"),
        ("Aluminum3M", "ALI=F"),
        ("", None),
        ("CPO", "SCRAPE_CPO"),
        ("Soybean Oil", "ZL=F"),
        ("Wheat", "ZW=F"),
        ("Natural Gas", "NG=F"),
    ],
    "COAL (ICI WEEKLY)": [
        ("ICI 1", "SCRAPE_ICI_1"),
        ("ICI 2", "SCRAPE_ICI_2"),
        ("ICI 3", "SCRAPE_ICI_3"),
        ("ICI 4", "SCRAPE_ICI_4"),
        ("ICI 5", "SCRAPE_ICI_5"),
    ],
    "CURRENCY": [
        ("USD/IDR", "USDIDR=X"),
        ("SGD/IDR", "SGDIDR=X"),
        ("MYR/IDR", "MYRIDR=X"),
        ("JPY/IDR", "JPYIDR=X"),
        ("AUD/IDR", "AUDIDR=X"),
    ],
}


# ==========================================
# 2. WEEKLY ICI COAL CACHING & SCRAPER
# ==========================================
def _should_refresh_ici_cache(cache_payload, now_wib):
    """
    Returns True if cache is missing, older than 7 days, or if a new Friday
    17:00 WIB Argus/Coalindo release window has passed since the last fetch.
    """
    if not cache_payload or "updated_at" not in cache_payload:
        return True

    try:
        last_updated = datetime.fromisoformat(cache_payload["updated_at"])
        if last_updated.tzinfo is None:
            last_updated = WIB.localize(last_updated)
    except ValueError:
        return True

    if now_wib - last_updated > timedelta(days=7):
        return True

    # Find the most recent Friday 17:00 WIB release checkpoint
    days_since_friday = (now_wib.weekday() - 4) % 7
    latest_friday_release = (now_wib - timedelta(days=days_since_friday)).replace(
        hour=17, minute=0, second=0, microsecond=0
    )
    if latest_friday_release > now_wib:
        latest_friday_release -= timedelta(days=7)

    return last_updated < latest_friday_release


def get_ici_coal_cached(force_refresh=False):
    """Loads weekly ICI 1-5 prices from local JSON cache or refreshes on schedule."""
    now_wib = datetime.now(WIB)
    cache_payload = {}

    if CACHE_FILE.exists():
        try:
            cache_payload = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            cache_payload = {}

    if not force_refresh and not _should_refresh_ici_cache(cache_payload, now_wib):
        cached_rates = cache_payload.get("data", {})
        return {
            k: tuple(v) if isinstance(v, list) else None
            for k, v in cached_rates.items()
        }

    # Scrape fresh weekly ICI prices
    fresh_data = {f"SCRAPE_ICI_{i}": None for i in range(1, 6)}
    try:
        search_url = "https://www.kontan.co.id/search/?search=Harga+Batubara+ICI"
        resp = requests.get(search_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")

        article_link = None
        for a in soup.select("a[href*='kontan.co.id/news/']"):
            if "ICI" in a.text.upper():
                article_link = a["href"]
                if article_link.startswith("//"):
                    article_link = "https:" + article_link
                break

        if article_link:
            art_resp = requests.get(article_link, headers=HEADERS, timeout=10)
            text = BeautifulSoup(art_resp.text, "lxml").get_text(" ")

            for grade in range(1, 6):
                pattern = rf"ICI\s*{grade}[^\d]{{1,25}}(\d{{2,3}}[.,]\d{{2}})"
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    val = float(match.group(1).replace(",", "."))
                    prev_entry = cache_payload.get("data", {}).get(f"SCRAPE_ICI_{grade}")
                    if isinstance(prev_entry, list) and len(prev_entry) >= 1 and prev_entry[0] != val:
                        prev_val = float(prev_entry[0])
                        diff = val - prev_val
                        pct = (diff / prev_val) * 100
                        fresh_data[f"SCRAPE_ICI_{grade}"] = (val, diff, pct)
                    else:
                        fresh_data[f"SCRAPE_ICI_{grade}"] = (val, 0.0, 0.0)
    except Exception:
        pass

    # Only overwrite cache if at least one grade was successfully parsed
    if any(v is not None for v in fresh_data.values()):
        serializable = {
            k: list(v) if v is not None else None for k, v in fresh_data.items()
        }
        CACHE_FILE.write_text(
            json.dumps(
                {"updated_at": now_wib.isoformat(), "data": serializable}, indent=2
            ),
            encoding="utf-8",
        )
        return fresh_data

    # Fallback to stale cache if live scrape failed
    if cache_payload.get("data"):
        return {
            k: tuple(v) if isinstance(v, list) else None
            for k, v in cache_payload["data"].items()
        }

    return fresh_data


# ==========================================
# 3. OTHER SCRAPERS, YFINANCE & RSS
# ==========================================
def scrape_tradingeconomics_quote(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        price_el = soup.select_one("#p")
        diff_el = soup.select_one("#nch")
        pct_el = soup.select_one("#pch")

        if price_el and diff_el and pct_el:
            last = float(price_el.text.strip().replace(",", ""))
            diff = float(diff_el.text.strip().replace(",", ""))
            pct = float(pct_el.text.strip().replace("%", "").replace(",", ""))
            return (last, diff, pct)
    except Exception:
        pass
    return None


def scrape_indo_benchmarks():
    return {
        "SCRAPE_INDO_10Y": scrape_tradingeconomics_quote(
            "https://tradingeconomics.com/indonesia/government-bond-yield"
        ),
        "SCRAPE_INDO_CDS": scrape_tradingeconomics_quote(
            "https://tradingeconomics.com/indonesia/5-year-cds"
        ),
        "SCRAPE_CPO": scrape_tradingeconomics_quote(
            "https://tradingeconomics.com/commodity/palm-oil"
        ),
    }


def fetch_headlines(max_items=7):
    headlines = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.title.strip().replace("\n", " ")
                if title not in headlines:
                    headlines.append(title)
                if len(headlines) >= max_items:
                    return headlines
        except Exception:
            continue
    return headlines


def fetch_market_data(sections):
    yf_tickers = list(
        {
            ticker
            for items in sections.values()
            for _, ticker in items
            if ticker is not None and not ticker.startswith("SCRAPE_")
        }
    )

    raw = yf.download(
        yf_tickers, period="5d", interval="1d", progress=False, threads=True
    )
    closes = raw["Close"] if "Close" in raw else raw

    results = {}
    for ticker in yf_tickers:
        try:
            series = closes[ticker].dropna()
            if len(series) >= 2:
                prev_close = float(series.iloc[-2])
                last_close = float(series.iloc[-1])
                diff = last_close - prev_close
                pct = (diff / prev_close) * 100
                results[ticker] = (last_close, diff, pct)
            elif len(series) == 1:
                results[ticker] = (float(series.iloc[-1]), 0.0, 0.0)
            else:
                results[ticker] = None
        except Exception:
            results[ticker] = None

    results.update(scrape_indo_benchmarks())
    results.update(get_ici_coal_cached())
    return results


# ==========================================
# 4. REPORT FORMATTER & TELEGRAM SENDER
# ==========================================
def format_row(label, data):
    if not label:
        return ""
    if data is None:
        return f"{label:<13} {'N/A':>10} {'N/A':>9} {'N/A':>8}"

    last, diff, pct = data
    alert = " !!" if abs(pct) >= 3.0 else ""
    return f"{label:<13} {last:>10,.2f} {diff:>+9,.2f} {pct:>+7.2f}%{alert}"


def generate_report():
    now_wib = datetime.now(WIB)
    timestamp_str = now_wib.strftime("%d-%b-%Y | %H:%M WIB")

    headlines = fetch_headlines(max_items=7)
    market_data = fetch_market_data(MARKET_SECTIONS)

    lines = [
        "TODAY'S MARKET OVERVIEW",
        timestamp_str,
        "",
        "HEADLINES",
    ]
    for h in headlines:
        lines.append(f"• {h}")
    lines.append("")

    for section_name, items in MARKET_SECTIONS.items():
        lines.append(section_name)
        for label, ticker in items:
            if ticker is None:
                lines.append("")
            else:
                lines.append(format_row(label, market_data.get(ticker)))
        lines.append("")

    return "\n".join(lines).strip()


def send_telegram_monospace(report_text, bot_token, chat_id):
    """
    Sends the report wrapped in a MarkdownV2 code block (```text ... ```)
    so fixed-width columns align cleanly on desktop and mobile Telegram.
    Splits cleanly on line boundaries if the report exceeds 4,096 chars.
    """
    if not bot_token or bot_token == "YOUR_BOT_TOKEN":
        raise ValueError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID before sending.")

    # Inside MarkdownV2 code blocks, only '\' and '`' must be escaped
    escaped = report_text.replace("\\", "\\\\").replace("`", "\\`")

    # Split safely below Telegram's 4,096-character limit (accounting for ``` fences)
    max_chunk = 3900
    chunks = []
    current_lines = []
    current_len = 0

    for line in escaped.splitlines():
        line_len = len(line) + 1
        if current_len + line_len > max_chunk and current_lines:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_len = line_len
        else:
            current_lines.append(line)
            current_len += line_len

    if current_lines:
        chunks.append("\n".join(current_lines))

    url = f"[https://api.telegram.org/bot](https://api.telegram.org/bot){bot_token}/sendMessage"
    responses = []

    for idx, chunk in enumerate(chunks):
        payload = {
            "chat_id": chat_id,
            "text": f"```text\n{chunk}\n```",
            "parse_mode": "MarkdownV2",
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        responses.append(resp.json())

        # Respect Telegram's ~1 msg/sec per-chat rate limit when multi-chunked
        if idx < len(chunks) - 1:
            time.sleep(1.1)

    return responses


if __name__ == "__main__":
    report = generate_report()
    print(report)

    # Uncomment or set env vars TELEGRAM_BOT_TOKEN & TELEGRAM_CHAT_ID to push
    if TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN":
        send_telegram_monospace(report, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        print("\n[OK] Sent monospace report to Telegram.")
