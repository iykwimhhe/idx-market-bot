
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

        tables = pd.read_html(html)

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
