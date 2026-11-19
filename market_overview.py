from datetime import datetime, timedelta
import html
import json
import os
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import feedparser
import holidays
import requests
import yfinance as yf

# ==========================================
# 1. TELEGRAM & ENVIRONMENT SETTINGS
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

WIB = ZoneInfo("Asia/Jakarta")
CACHE_FILE = Path("ici_coal_cache.json")

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
# 2. TELEGRAM FUNCTION (HTML <pre> FORMAT)
# ==========================================
def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        raise ValueError("BOT_TOKEN or CHAT_ID environment variable is missing.")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    escaped = html.escape(message)

    # Split safely below Telegram's 4,096-character limit (accounting for <pre></pre>)
    max_chunk = 3950
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

    for idx, chunk in enumerate(chunks):
        payload = {
            "chat_id": CHAT_ID,
            "text": f"<pre>{chunk}</pre>",
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        response = requests.post(url, data=payload, timeout=15)
        print(response.status_code)
        print(response.text)
        response.raise_for_status()

        if idx < len(chunks) - 1:
            time.sleep(1.1)


# ==========================================
# 3. WEEKLY ICI COAL CACHING & SCRAPER
# ==========================================
def _should_refresh_ici_cache(cache_payload, now_wib):
    if not cache_payload or "updated_at" not in cache_payload:
        return True

    try:
        last_updated = datetime.fromisoformat(cache_payload["updated_at"])
        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=WIB)
    except ValueError:
        return True

    if now_wib - last_updated > timedelta(days=7):
        return True

    days_since_friday = (now_wib.weekday() - 4) % 7
    latest_friday_release = (now_wib - timedelta(days=days_since_friday)).replace(
        hour=17, minute=0, second=0, microsecond=0
    )
    if latest_friday_release > now_wib:
        latest_friday_release -= timedelta(days=7)

    return last_updated < latest_friday_release


def get_ici_coal_cached(now_wib, force_refresh=False):
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

    if cache_payload.get("data"):
        return {
            k: tuple(v) if isinstance(v, list) else None
            for k, v in cache_payload["data"].items()
        }

    return fresh_data


# ==========================================
# 4. BENCHMARK SCRAPERS, YFINANCE & RSS
# ==========================================
def scrape_tradingeconomics_quote(url):
    try:
        resp = requests
