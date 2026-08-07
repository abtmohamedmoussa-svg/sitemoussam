import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

NTFY_TOPIC = "moussa-news-1313"

BVMT_ASSETS = [
    ("TUNINDEX", "https://irbe7.com/actifs/TUNINDEX/TN0009050014"),
    ("Indice BANQUES", "https://irbe7.com/actifs/BANQUES/TN0009050030"),
    ("Indice SERVICES FIN", "https://irbe7.com/actifs/SERVICES%20FINANCIER/TN0009050055"),
    ("Attijari Bank", "https://irbe7.com/actifs/TJARI/TN0001600154"),
    ("Amen Bank", "https://irbe7.com/actifs/AMEN%20BANK/TN0003400058"),
    ("BIAT", "https://irbe7.com/actifs/BIAT/TN0001800457"),
]

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

def get_irbe7(name, url):
    """Cours d'un actif BVMT depuis irbe7.com."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"Echec {name}: HTTP {r.status_code}")
            return f"{name} : indisponible"
        text = BeautifulSoup(r.content, 'html.parser').get_text(" ", strip=True)
        m = re.search(r"(\d[\d\s]*,\d+)\s+(\d[\d\s]*,\d+)\s*%", text)
        if m:
            print(f"OK {name}")
            return f"{name} : {m.group(1)} (var. {m.group(2)}%)"
        print(f"Echec extraction {name}: {text[:120]}")
    except Exception as e:
        print(f"Erreur {name}: {e}")
    return f"{name} : indisponible"

def probe_bct():
    """Test temporaire d'acces a la page indicateurs BCT."""
    try:
        r = requests.get("https://www.bct.gov.tn/bct/siteprod/indicateurs.jsp",
                         headers=HEADERS, timeout=30)
        print(f"BCT: HTTP {r.status_code}, taille {len(r.content)} octets")
        text = BeautifulSoup(r.content, 'html.parser').get_text(" ", strip=True)
        print(f"BCT extrait: {text[:3000]}")
    except Exception as e:
        print(f"BCT erreur: {e}")

def main(): probe_bct()
    lines = ["== BOURSE DE TUNIS =="]
    for name, url in BVMT_ASSETS:
        lines.append(get_irbe7(name, url))

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
