"""One-off probe #2: Stockbee sheet frame URLs, cell colours (27/11/26)"""
import re, requests
SHEET = "1O6OhS7ciA8zwfycBfGPbP2fWJnR0pn2UUvFZVDP9jpE"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"}
t = requests.get(f"https://docs.google.com/spreadsheets/d/{SHEET}/pubhtml", headers=UA, timeout=30).text
print("iframes:", re.findall(r'<iframe[^>]+src="([^"]+)"', t)[:5])
print("gids:", sorted(set(re.findall(r"gid[=:]\\?\"?(\d+)", t)))[:10])
print("names:", re.findall(r'class="[^"]*sheet-button[^"]*"[^>]*>(.*?)</', t, re.S)[:6])
for url in [f"https://docs.google.com/spreadsheets/d/{SHEET}/pubhtml/sheet?headers=false&gid=0",
            f"https://docs.google.com/spreadsheets/d/{SHEET}/htmlview/sheet?headers=true&gid=0"]:
    r = requests.get(url, headers=UA, timeout=30); x = r.text
    css = re.findall(r"\.s(\d+)\{([^}]*)\}", x)
    bg = {k: re.search(r"background-color:\s*(#[0-9a-fA-F]+)", v).group(1) for k, v in css if "background-color" in v}
    cells = re.findall(r'<td class="s(\d+)"[^>]*>(.*?)</td>', x, re.S)[:40]
    print(f"[{url[-40:]}] HTTP {r.status_code} {len(x)}B; styles {len(css)}; bg {sorted(set(bg.values()))[:15]}")
    print("   cells:", [(c, re.sub('<[^>]+>', '', v)[:12]) for c, v in cells[:40]])
