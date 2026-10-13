
"""PY2WWV solar dashboard - NOAA/SWPC observations."""

from datetime import datetime, timezone
from pathlib import Path
import re
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

WWV_URL = "https://services.swpc.noaa.gov/text/wwv.txt"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
CYCLE_URL = "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(size, bold=False):
    try:
        return ImageFont.truetype(
            FONT_BOLD if bold else FONT_REG, size
        )
    except OSError:
        return ImageFont.load_default()


def get(url):
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "PY2WWV-Solar-Dashboard/2.0"}
    )
    response.raise_for_status()

    if url.endswith(".json"):
        return response.json()

    return response.text


def format_number(value, decimals=1):
    try:
        number = float(value)

        if number < 0:
            return "N/A"

        if number.is_integer():
            return str(int(number))

        return f"{number:.{decimals}f}"

    except (TypeError, ValueError):
        return "N/A"


def monthly_ssn():
    """Most recent available observed monthly SSN."""

    try:
        rows = get(CYCLE_URL)

        for row in reversed(rows):
            if not isinstance(row, dict):
                continue

            value = format_number(row.get("ssn"), 1)

            if value != "N/A":
                return value

    except Exception as exc:
        print("Monthly SSN unavailable:", exc)

    return "N/A"


def read_wwv():
    """Read official NOAA WWV geophysical bulletin."""

    result = {
        "SFI": "N/A",
        "A INDEX": "N/A",
        "Kp INDEX": "N/A"
    }

    try:
        bulletin = get(WWV_URL)

        flux = re.search(
            r"Solar flux\s+([\d.]+)",
            bulletin,
            re.IGNORECASE
        )

        a_index = re.search(
            r"estimated planetary A-index\s+([\d.]+)",
            bulletin,
            re.IGNORECASE
        )

        k_index = re.search(
            r"estimated planetary K-index.*?was\s+([\d.]+)",
            bulletin,
            re.IGNORECASE | re.DOTALL
        )

        if flux:
            result["SFI"] = format_number(flux.group(1))

        if a_index:
            result["A INDEX"] = format_number(
                a_index.group(1)
            )

        if k_index:
            result["Kp INDEX"] = format_number(
                k_index.group(1), 2
            )

        print("WWV bulletin:", result)

    except Exception as exc:
        print("WWV bulletin unavailable:", exc)

    return result


def read_kp_json():
    """Read NOAA Kp JSON in new or legacy format."""

    try:
        rows = get(KP_URL)

        if not isinstance(rows, list):
            return "N/A"

        # New NOAA format: list of dictionaries
        for row in reversed(rows):

            if isinstance(row, dict):
                value = format_number(
                    row.get("Kp", row.get("kp")), 2
                )

                if value != "N/A":
                    return value

            # Legacy format: list of arrays
            elif isinstance(row, list) and len(row) > 1:
                value = format_number(row[1], 2)

                if value != "N/A" and float(value) <= 9:
                    return value

    except Exception as exc:
        print("Kp JSON unavailable:", exc)

    return "N/A"


def metrics():
    values = read_wwv()

    # Prefer the most recent Kp from the JSON product.
    kp = read_kp_json()

    if kp != "N/A":
        values["Kp INDEX"] = kp

    values["SSN"] = monthly_ssn()

    print("Final solar metrics:", values)

    return values


def main():
    values = metrics()

    w, h = 1200, 420

    im = Image.new("RGB", (w, h), (7, 21, 34))
    d = ImageDraw.Draw(im)

    # Original dark navy gradient
    for y in range(h):
        shade = int(y / h * 13)

        d.line(
            (0, y, w, y),
            fill=(7, 21 + shade, 34 + shade)
        )

    # Dashboard header
    d.text(
        (48, 28),
        "05 / LIVE PROPAGATION CONDITIONS",
        font=font(20, True),
        fill="#FFD21F"
    )

    d.text(
        (48, 69),
        "SOLAR ACTIVITY",
        font=font(46, True),
        fill="white"
    )

    d.text(
        (48, 133),
        "PY2WWV  •  SAO PAULO, BRAZIL  •  GRID GG66QM",
        font=font(17),
        fill="#9DBDD1"
    )

    names = [
        "SFI",
        "A INDEX",
        "Kp INDEX",
        "SSN"
    ]

    # Four original metric cards
    for i, name in enumerate(names):
        x = 48 + i * 279
        y = 188

        d.rounded_rectangle(
            (x, y, x + 259, y + 153),
            radius=8,
            fill="#102B43",
            outline="#29465D",
            width=2
        )

        d.text(
            (x + 18, y + 16),
            name,
            font=font(20, True),
            fill="#9DBDD1"
        )

        d.text(
            (x + 18, y + 49),
            values[name],
            font=font(54, True),
            fill="#FFD21F"
        )

    # Source and timestamp
    stamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    d.text(
        (48, 365),
        "NOAA / SWPC  •  SFI & A: DAILY  •  Kp: 3H  •  SSN: MONTHLY",
        font=font(14),
        fill="#9DBDD1"
    )

    d.text(
        (910, 390),
        stamp,
        font=font(15),
        fill="#9DBDD1"
    )

    output = ROOT / "solar.png"

    im.save(output, optimize=True)

    print("Generated:", output)
    print("Values:", values)


if __name__ == "__main__":
    main()
