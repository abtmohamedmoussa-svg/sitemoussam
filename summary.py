import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

NTFY_TOPIC = "moussa-news-1313"

INSTRUMENTS = [
    ("USD/TND", "TND=X", ""),
    ("EUR/TND", "EURTND=X", ""),
    ("EUR/USD", "EURUSD=X", ""),
    ("Petrole Brent", "BZ=F", "USD"),
    ("Petrole WTI", "CL=F", "USD"),
    ("Or (once)", "GC=F", "USD"),
    ("Bitcoin", "BTC-USD", "USD"),
    ("Dow Jones", "^DJI", "pts"),
    ("Nasdaq", "^IXIC", "pts"),
    ("S&P 500", "^GSPC", "pts"),
    ("Euro Stoxx 50", "^STOXX50E", "pts"),
    ("CAC 40", "^FCHI", "pts"),
    ("VIX", "^VIX", "pts"),
]

ACTIONS_BVMT = [
    ("Attijari Bank", "https://finansya.tn/societes/banque-attijari-de-tunisie"),
    ("Amen Bank", "https://finansya.tn/societes/amen-bank"),
    ("BIAT", "https://finansya.tn/societes/banque-internationale-arabe-de-tunisie"),
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    meta = r.json()["chart"]["result"][0]["meta"]
    price = meta["regularMarketPrice"]
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = (price - prev) / prev * 100 if prev else None
    return price, change

def fmt(price, change, unit):
    if price < 10:
        p = f"{price:.4f}"
    else:
        p = f"{price:,.2f}".replace(",", " ")
    c = f" ({change:+.2f}%)" if change is not None else ""
    u = f" {unit}" if unit else ""
    return f"{p}{u}{c}"

def get_indices_bvmt():
    """Tous les indices BVMT depuis finansya.tn (differe 15 min)."""
    lines = []
    try:
        r = requests.get("https://finansya.tn/palmares-indices", headers=HEADERS, timeout=20)
        print(f"   finansya indices: HTTP {r.status_code}, taille {len(r.content)} octets")
        soup = BeautifulSoup(r.content, 'html.parser')
        print(f"   extrait page: {soup.get_text(' ', strip=True)[:200]}")
        for tr in soup.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all('td')]
            if len(cells) >= 3 and cells[1] and cells[0] and "Aucun" not in cells[0]:
                lines.append(f"{cells[0]} : {cells[1]} pts ({cells[2]})")
        print(f"OK indices BVMT ({len(lines)})")
    except Exception as e:
        print(f"Erreur indices BVMT: {e}")
    return lines

def get_action(name, url):
    """Cours d'une action depuis sa fiche finansya.tn."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        text = BeautifulSoup(r.content, 'html.parser').get_text(" ", strip=True)
        m = re.search(r"(\d[\d\s]*\.\d+)\s*TND\s*([+-]?\d+\.\d+)%", text)
        if m:
            print(f"OK {name}")
            return f"{name} : {m.group(1)} TND ({m.group(2)}%)"
        print(f"Echec extraction {name}: HTTP {r.status_code}, extrait: {text[:150]}")
    except Exception as e:
        print(f"Erreur {name}: {e}")
    return f"{name} : indisponible"

def main():
    lines = ["== BOURSE DE TUNIS =="]
    lines += get_indices_bvmt() or ["Indices BVMT : indisponibles"]

    lines.append("")
    lines.append("== ACTIONS ==")
    for name, url in ACTIONS_BVMT:
        lines.append(get_action(name, url))

    lines.append("")
    lines.append("== INTERNATIONAL ==")
    for name, symbol, unit in INSTRUMENTS:
        try:
            price, change = get_quote(symbol)
            lines.append(f"{name} : {fmt(price, change, unit)}")
            print(f"OK {name}")
        except Exception as e:
            lines.append(f"{name} : indisponible")
            print(f"Erreur {name}: {e}")

    message = "\n".join(lines)
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode('utf-8'),
        headers={
            "Title": f"Marches du {datetime.now().strftime('%d/%m %H:%M')}",
            "Tags": "chart_with_upwards_trend",
            "Priority": "default"
        },
        timeout=10
    )
    print("Resume envoye")

if __name__ == "__main__":
    main()
