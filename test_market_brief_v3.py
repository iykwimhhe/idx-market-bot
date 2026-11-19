import requests
import pandas as pd
import re
from io import StringIO
from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# SETTINGS
# ============================================================

WIB = ZoneInfo("Asia/Jakarta")
now = datetime.now(WIB)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
    )
}


# ============================================================
# HELPERS
# ============================================================

def get_page(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        response.raise_for_status()
        return response.text

    except Exception as e:
        print(f"ERROR fetching {url}")
        print(f"  {e}")
        return None


def get_tables(url):
    try:
        return pd.read_html(
            requests.get(
                url,
                headers=HEADERS,
                timeout=20
            ).text
        )

    except Exception as e:
        print(f"ERROR reading tables from {url}")
        print(f"  {e}")
        return []


def print_section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ============================================================
# HEADER
# ============================================================

print("=" * 70)
print("MARKET BRIEF — SECOND STAGE DATA TEST")
print(f"{now.strftime('%d-%b-%Y | %H:%M')} WIB")
print("=" * 70)


# ============================================================
# US GOVERNMENT BONDS
# ============================================================

def get_us_treasury_yields():
    year = 2026

    csv_url = (
        f"https://home.treasury.gov/resource-center/data-chart-center/"
        f"interest-rates/daily-treasury-rates.csv/{year}/all"
        f"?type=daily_treasury_yield_curve"
        f"&field_tdr_date_value={year}"
        f"&page&_format=csv"
    )

    try:
        df = pd.read_csv(csv_url)

        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")

        latest = df.iloc[-1]
        previous = df.iloc[-2]

        results = {}

        for maturity, column in {
            "US 2Y": "2 Yr",
            "US 10Y": "10 Yr",
            "US 20Y": "20 Yr",
        }.items():

            current = float(latest[column])
            prev = float(previous[column])

            change = current - prev
            pct = (change / prev * 100) if prev else None

            results[maturity] = {
                "date": latest["Date"].strftime("%Y-%m-%d"),
                "level": current,
                "change": change,
                "pct": pct,
            }

        return results

    except Exception as e:
        print(f"Treasury data error: {e}")
        return {}


# ============================================================
# INDONESIA GOVERNMENT BONDS
# ============================================================

print_section("INDONESIA GOVERNMENT BONDS")

asian_bonds_url = (
    "https://asianbondsonline.adb.org/indonesia/"
)


def get_indonesia_bonds():
    try:
        html = get_page(asian_bonds_url)

        if not html:
            return {}

        results = {}

        # Parse the specific government-bond rows directly from the HTML.
        # This avoids pandas trying to interpret the large HTML response
        # and avoids printing the entire page when parsing fails.
        for maturity in ["2 Year", "5 Year", "10 Year"]:

            row_match = re.search(
                rf"<tr[^>]*>.*?{re.escape(maturity)}.*?</tr>",
                html,
                flags=re.IGNORECASE | re.DOTALL
            )

            if not row_match:
                continue

            row_html = row_match.group(0)

            # Remove HTML tags.
            clean_row = re.sub(r"<[^>]+>", " ", row_html)

            # Normalize whitespace and HTML entities.
            clean_row = re.sub(r"&nbsp;", " ", clean_row)
            clean_row = re.sub(r"\s+", " ", clean_row).strip()

            # Extract numeric values.
            numbers = re.findall(
                r"\d+(?:,\d{3})*(?:\.\d+)?",
                clean_row
            )

            # Example:
            # 2 Year | 7.065 | ▲ 4.6 | ▲ 7.0 | ▲ 196.3
            #
            # The first number is the "2" from "2 Year".
            # The next number is Latest Yield.
            # The next number is Previous Day change in bps.
            if len(numbers) < 3:
                continue

            latest = float(numbers[1].replace(",", ""))
            change_bps = float(numbers[2].replace(",", ""))

            # AsianBondsOnline reports yield changes in basis points.
            change = change_bps / 100.0

            # Reconstruct the previous day's yield.
            previous_yield = latest - change

            pct = (
                (change / previous_yield * 100)
                if previous_yield != 0
                else None
            )

            results[maturity] = {
                "level": latest,
                "change": change,
                "pct": pct,
                "change_bps": change_bps,
            }

        return results

    except Exception as e:
        print(f"AsianBondsOnline parsing error: {e}")
        return {}


indo_bonds = get_indonesia_bonds()

for name in ["2 Year", "5 Year", "10 Year"]:
    if name in indo_bonds:
        x = indo_bonds[name]

        print(
            f"{name} "
            f"{x['level']:.3f} "
            f"{x['change']:+.3f} "
            f"{x['pct']:+.2f}%"
        )
    else:
        print(f"{name} n/a")


# ============================================================
# INDONESIA 1Y BOND
# ============================================================

print_section("INDONESIA 1Y BOND")

indo_1y_url = (
    "https://www.investing.com/rates-bonds/"
    "indonesia-1-year-bond-yield"
)

html = get_page(indo_1y_url)

if html:

    # Try to locate the current yield.
    patterns = [
        r'"last":([0-9.]+)',
        r'"last_close":([0-9.]+)',
        r'"value":([0-9.]+)',
    ]

    found = False

    for pattern in patterns:

        match = re.search(pattern, html)

        if match:

            print(
                f"Possible current 1Y yield: "
                f"{match.group(1)}"
            )

            found = True
            break

    if not found:
        print(
            "Could not extract 1Y automatically."
        )

else:
    print("n/a")


# ============================================================
# INDONESIA 5Y CDS
# ============================================================

print_section("INDONESIA 5Y CDS")

cds_url = (
    "https://id.investing.com/rates-bonds/"
    "indonesia-cds-5-years-usd"
)

html = get_page(cds_url)

if html:

    patterns = [
        r'"last":([0-9.]+)',
        r'"last_close":([0-9.]+)',
        r'"value":([0-9.]+)',
    ]

    found = False

    for pattern in patterns:

        match = re.search(pattern, html)

        if match:

            print(
                f"Possible current CDS: "
                f"{match.group(1)}"
            )

            found = True
            break

    if not found:
        print("Could not extract CDS automatically.")

else:
    print("n/a")


# ============================================================
# LME METALS
# ============================================================

print_section("LME 3-MONTH METALS")

lme_url = (
    "https://www.lme.com/Market-data/"
    "Reports-and-data/LME-Official-Prices"
)

html = get_page(lme_url)

if html:

    try:

        tables = pd.read_html(StringIO(html))

        found = False

        for table in tables:

            text = table.to_string()

            if "Nickel" in text and "Tin" in text:

                print(table.to_string(index=False))

                found = True
                break

        if not found:
            print("LME table not found.")

    except Exception as e:
        print(f"LME parsing error: {e}")

else:
    print("n/a")


# ============================================================
# NEWCASTLE COAL
# ============================================================

print_section("NEWCASTLE COAL")

newcastle_url = (
    "https://www.investing.com/commodities/"
    "newcastle-coal-futures"
)

html = get_page(newcastle_url)

if html:

    print(
        "Newcastle page successfully retrieved."
    )

    # Look for contract/month information
    months = re.findall(
        r'(Nov|Dec|Jan|Feb|Mar)\s*[\' ]?26|'
        r'(Nov|Dec|Jan|Feb|Mar)\s*27',
        html,
        flags=re.IGNORECASE
    )

    print(
        f"Contract month references found: "
        f"{len(months)}"
    )

else:
    print("n/a")


# ============================================================
# ROTTERDAM COAL
# ============================================================

print_section("ROTTERDAM COAL")

rotterdam_url = (
    "https://www.tradingview.com/symbols/"
    "ICEEUR-ATW1%21/contracts/"
)

html = get_page(rotterdam_url)

if html:

    print(
        "TradingView Rotterdam contracts page "
        "successfully retrieved."
    )

    # Extract contract rows containing API2
    lines = html.splitlines()

    matches = []

    for line in lines:

        if "API2 Rotterdam Coal Futures" in line:

            matches.append(
                re.sub("<.*?>", " ", line)
            )

    if matches:

        for match in matches[:10]:
            print(match[:500])

    else:
        print(
            "Could not extract contract rows "
            "from raw HTML."
        )

else:
    print("n/a")


# ============================================================
# ICI
# ============================================================

print_section("INDONESIA COAL INDEX — ICI")

ici_url = (
    "https://www.iomi-coal.com/"
)

html = get_page(ici_url)

if html:

    print(
        "IOMI ICI page successfully retrieved."
    )

    try:

        tables = pd.read_html(StringIO(html))

        found = False

        for table in tables:

            text = table.to_string()

            if "ICI 1" in text:

                print(table.to_string(index=False))

                found = True
                break

        if not found:
            print(
                "ICI table not found in HTML."
            )

    except Exception as e:
        print(f"ICI parsing error: {e}")

else:
    print("n/a")


# ============================================================
# DONE
# ============================================================

print_section("SECOND-STAGE TEST COMPLETE")

print(
    "\nNo Telegram message was sent."
)

print(
    "No existing IDX bot files were modified."
)
