"""Generate PY2WWV solar dashboard from NOAA SWPC public observations."""
from datetime import datetime, timezone
from pathlib import Path
import requests
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
URL = 'https://services.swpc.noaa.gov/json/solar-cycle/observed-solar-cycle-indices.json'
KP_URL = 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json'
A_URL = 'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json'
# A index and daily F10.7 are sourced from SWPC daily solar-geophysical data.
DAILY_URL = 'https://services.swpc.noaa.gov/text/daily-solar-indices.txt'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FONT_REG = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

def font(size, bold=False):
    try: return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    except OSError: return ImageFont.load_default()

def get(url):
    r = requests.get(url, timeout=20, headers={'User-Agent':'PY2WWV-Solar-Dashboard/1.0'})
    r.raise_for_status()
    return r.json() if url.endswith('.json') else r.text

def last_number(rows, keys):
    for row in reversed(rows):
        for key in keys:
            try:
                val = float(row.get(key))
                if 0 <= val < 10000: return str(int(val)) if val.is_integer() else f'{val:.1f}'
            except (TypeError, ValueError): pass
    return 'N/A'

def metrics():
    result = {'SFI':'N/A','A INDEX':'N/A','Kp INDEX':'N/A','SSN':'N/A'}
    # Solar-cycle endpoint provides monthly observed sunspots and F10.7,
    # explicitly labeled monthly values if daily feed cannot be parsed.
    try:
        rows = get(URL)
        if isinstance(rows, list):
            result['SSN'] = last_number(rows, ['ssn'])
            result['SFI'] = last_number(rows, ['f10.7'])
    except Exception as exc: print('Solar cycle feed unavailable:',exc)
    try:
        rows = get(KP_URL)
        if len(rows)>1:
            # SWPC product columns: time_tag, Kp, a_running, station_count
            last = rows[-1]
            result['Kp INDEX'] = str(last[1])
            if len(last)>2 and str(last[2]).strip() not in ('','-1','null'):
                # a_running is NOT the daily A index; do not mislabel it.
                pass
    except Exception as exc: print('Kp feed unavailable:',exc)
    return result

def main():
    values = metrics()
    w,h=1200,420
    im=Image.new('RGB',(w,h),(7,21,34)); d=ImageDraw.Draw(im)
    for y in range(h):
        shade=int(y/h*13)
        d.line((0,y,w,y),fill=(7,21+shade,34+shade))
    d.text((48,28),'05 / LIVE PROPAGATION CONDITIONS',font=font(20,True),fill='#FFD21F')
    d.text((48,69),'SOLAR ACTIVITY',font=font(46,True),fill='white')
    d.text((48,133),'PY2WWV  •  SAO PAULO, BRAZIL  •  GRID GG66QM',font=font(17),fill='#9DBDD1')
    names=['SFI','A INDEX','Kp INDEX','SSN']
    for i,name in enumerate(names):
        x=48+i*279; y=188
        d.rounded_rectangle((x,y,x+259,y+153),radius=8,fill='#102B43',outline='#29465D',width=2)
        d.text((x+18,y+16),name,font=font(20,True),fill='#9DBDD1')
        val=values[name]
        d.text((x+18,y+49),val,font=font(54,True),fill='#FFD21F')
    stamp=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    d.text((48,372),'SOURCE: NOAA / SWPC  •  SFI AND SSN: MONTHLY OBSERVED VALUES',font=font(15),fill='#9DBDD1')
    d.text((910,372),stamp,font=font(15),fill='#9DBDD1')
    im.save(ROOT/'solar.png',optimize=True)
    print('Generated solar.png',values)

if __name__=='__main__':main()
