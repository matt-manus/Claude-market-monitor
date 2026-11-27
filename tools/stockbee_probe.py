"""One-off probe: can we read Stockbee's sheet with its cell colours? (27/11/26)"""
import re, requests
SHEET = "1O6OhS7ciA8zwfycBfGPbP2fWJnR0pn2UUvFZVDP9jpE"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"}
for name, url in [("pubhtml", f"https://docs.google.com/spreadsheets/d/{SHEET}/pubhtml"),
                  ("htmlview", f"https://docs.google.com/spreadsheets/d/{SHEET}/htmlview"),
                  ("gviz html", f"https://docs.google.com/spreadsheets/d/{SHEET}/gviz/tq?tqx=out:html")]:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        t = r.text
        bg = re.findall(r"\.s\d+\{[^}]*background-color:\s*(#[0-9a-fA-F]{3,6})", t)
        tds = re.findall(r'<td class="s\d+"[^>]*>([^<]{0,15})<', t)[:12]
        dates = re.findall(r">(\d{1,2}/\d{1,2}/20\d\d)<", t)[:3]
        sheets = re.findall(r'id="sheet-button-(\d+)"[^>]*>.*?<a[^>]*>([^<]+)<', t, re.S)[:6]
        print(f"[{name}] HTTP {r.status_code} {len(t)} bytes; css bg colours {len(bg)} (distinct {sorted(set(bg))[:12]}); first dates {dates}; tabs {sheets}; td sample {tds}")
    except Exception as e:
        print(f"[{name}] FAIL {e!r}")
