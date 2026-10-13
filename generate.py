
"""PY2WWV Solar Dashboard - NOAA/SWPC observations."""

from datetime import datetime, timezone
from pathlib import Path
import re
import math
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent

WWV_URL = "https://services.swpc.noaa.gov/text/wwv.txt"
KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
CYCLE_URL = "https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

GREEN = "#24D52B"
YELLOW = "#FFD21F"
RED = "#FF3038"
MUTED = "#9DBDD1"
WHITE = "#FFFFFF"


def font(size, bold=False):
    try:
        return ImageFont.truetype(
            FONT_BOLD if bold else FONT_REG, size
        )
    except OSError:
        return ImageFont.load_default()


def get(url):
    r = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "PY2WWV-Solar-Dashboard/3.1"}
    )
    r.raise_for_status()
    return r.json() if url.endswith(".json") else r.text


def number(value):
    try:
        n = float(value)
        if not math.isfinite(n) or n < 0:
            return None
        return n
    except (TypeError, ValueError):
        return None


def display(value):
    if value is None:
        return "N/A"
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}"


def monthly_ssn():
    """Most recent available monthly sunspot number."""
    try:
        rows = get(CYCLE_URL)
        for row in reversed(rows):
            if isinstance(row, dict):
                value = number(row.get("ssn"))
                if value is not None:
                    return value
    except Exception as exc:
        print("SSN unavailable:", exc)
    return None


def read_wwv():
    """Read official NOAA WWV geophysical bulletin."""
    values = {
        "SFI": None,
        "A INDEX": None,
        "Kp INDEX": None
    }

    try:
        bulletin = get(WWV_URL)

        patterns = {
            "SFI": r"Solar flux\s+([\d.]+)",
            "A INDEX": r"estimated planetary A-index\s+([\d.]+)",
            "Kp INDEX": r"estimated planetary K-index.*?was\s+([\d.]+)"
        }

        for key, pattern in patterns.items():
            match = re.search(
                pattern,
                bulletin,
                re.IGNORECASE | re.DOTALL
            )
            if match:
                values[key] = number(match.group(1))

    except Exception as exc:
        print("WWV unavailable:", exc)

    return values


def read_kp():
    """Read the latest available planetary Kp index."""
    try:
        rows = get(KP_URL)

        if not isinstance(rows, list):
            return None

        for row in reversed(rows):
            if isinstance(row, dict):
                value = number(row.get("Kp", row.get("kp")))
            elif isinstance(row, list) and len(row) > 1:
                value = number(row[1])
            else:
                continue

            if value is not None and value <= 9:
                return value

    except Exception as exc:
        print("Kp unavailable:", exc)

    return None


def metrics():
    values = read_wwv()
    kp = read_kp()

    if kp is not None:
        values["Kp INDEX"] = kp

    values["SSN"] = monthly_ssn()

    print("Final solar metrics:", values)
    return values


def condition(name, value):
    """
    HF operational color classification.

    SFI: higher generally favors higher HF bands.
    A/Kp: lower indicates quieter geomagnetic conditions.
    SSN: higher indicates greater solar activity.
    """

    if value is None:
        return MUTED, "NO DATA", "DATA UNAVAILABLE"

    # SOLAR FLUX INDEX
    if name == "SFI":
        if value >= 180:
            return GREEN, "HIGH", "HIGH SOLAR FLUX"
        if value >= 120:
            return YELLOW, "MODERATE", "MODERATE SOLAR FLUX"
        return RED, "LOW", "LOW SOLAR FLUX"

    # PLANETARY A INDEX
    if name == "A INDEX":
        if value < 7:
            return GREEN, "QUIET", "FAVORABLE CONDITIONS"
        if value <= 20:
            return YELLOW, "UNSETTLED", "VARIABLE CONDITIONS"
        return RED, "DISTURBED", "GEOMAGNETIC ACTIVITY"

    # PLANETARY Kp INDEX
    if name == "Kp INDEX":
        if value < 3:
            return GREEN, "QUIET", "FAVORABLE CONDITIONS"
        if value < 5:
            return YELLOW, "UNSETTLED", "VARIABLE CONDITIONS"
        return RED, "STORM", "GEOMAGNETIC STORM"

    # SUNSPOT NUMBER
    if name == "SSN":
        if value >= 100:
            return GREEN, "HIGH", "HIGH SOLAR ACTIVITY"
        if value >= 50:
            return YELLOW, "MODERATE", "MODERATE SOLAR ACTIVITY"
        return RED, "LOW", "LOW SOLAR ACTIVITY"

    return MUTED, "UNKNOWN", ""


def centered(draw, text, box, fnt, fill):
    left, top, right, bottom = box

    bounds = draw.textbbox((0, 0), text, font=fnt)
    tw = bounds[2] - bounds[0]
    th = bounds[3] - bounds[1]

    x = left + (right - left - tw) / 2
    y = top + (bottom - top - th) / 2 - bounds[1]

    draw.text((x, y), text, font=fnt, fill=fill)


def main():
    values = metrics()

    w, h = 1200, 420
    im = Image.new("RGB", (w, h), (7, 21, 34))
    d = ImageDraw.Draw(im)

    # Dark navy background gradient
    for y in range(h):
        shade = int(y / h * 13)
        d.line(
            (0, y, w, y),
            fill=(7, 21 + shade, 34 + shade)
        )

    # Header
    d.text(
        (48, 23),
        "05 / LIVE PROPAGATION CONDITIONS",
        font=font(20, True),
        fill=YELLOW
    )

    d.text(
        (48, 62),
        "SOLAR ACTIVITY",
        font=font(46, True),
        fill=WHITE
    )

    d.text(
        (48, 125),
        "PY2WWV  •  SAO PAULO, BRAZIL  •  GRID GG66QM",
        font=font(17),
        fill=MUTED
    )

    names = ["SFI", "A INDEX", "Kp INDEX", "SSN"]

    # Four original metric cards
    for i, name in enumerate(names):
        x = 48 + i * 279
        y = 174

        value = values.get(name)
        color, status, description = condition(name, value)

        d.rounded_rectangle(
            (x, y, x + 259, y + 174),
            radius=8,
            fill="#102B43",
            outline="#365F7E",
            width=2
        )

        d.text(
            (x + 14, y + 13),
            name,
            font=font(18, True),
            fill="#DCE8F1"
        )

        d.text(
            (x + 14, y + 43),
            display(value),
            font=font(49, True),
            fill=color
        )

        # Automatic colored condition label
        d.rounded_rectangle(
            (x + 14, y + 109, x + 245, y + 140),
            radius=6,
            fill=color
        )

        centered(
            d,
            status,
            (x + 14, y + 109, x + 245, y + 140),
            font(15, True),
            "#071522"
        )

        centered(
            d,
            description,
            (x + 8, y + 146, x + 251, y + 168),
            font(11),
            MUTED
        )

    # NOAA source and UTC timestamp
    stamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    d.text(
        (48, 375),
        "NOAA / SWPC  •  SFI & A: DAILY  •  Kp: 3H  •  SSN: MONTHLY",
        font=font(13),
        fill=MUTED
    )

    d.text(
        (942, 395),
        stamp,
        font=font(13),
        fill=MUTED
    )

    output = ROOT / "solar.png"
    im.save(output, optimize=True)

    print("Generated:", output)
    print("Values:", values)


if __name__ == "__main__":
    main()
