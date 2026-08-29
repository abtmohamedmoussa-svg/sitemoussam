import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime

NTFY_TOPIC = "moussa-news-1313"

# Mettre a True pour dumper le HTML brut d'irbe7 (diagnostic du signe).
PROBE = False

BVMT_ASSETS = [
    ("TUNINDEX", "https://irbe7.com/actifs/TUNINDEX/TN0009050014"),
    ("Indice BANQUES", "https://irbe7.com/actifs/BANQUES/TN0009050030"),
    ("Indice SERVICES FIN", "https://irbe7.com/actifs/SERVICES%20FINANCIER/TN0009050055"),
    ("Attijari Bank", "https://irbe7.com/actifs/TJARI/TN0001600154"),
    ("Amen Bank", "https://irbe7.com/actifs/AMEN%20BANK/TN0003400058"),
    ("BIAT", "https://irbe7.com/actifs/BIAT/TN0001800457"),
    ("Poulina PGH", "https://irbe7.com/actifs/POULINA%20GP%20HOLDING/TN0005700018"),
    ("SFBT", "https://irbe7.com/actifs/SFBT/TN0001100254"),
    ("TPR", "https://irbe7.com/actifs/TPR/TN0007270010"),
]

# Clotures du 31/12/2025, a renseigner une fois par an.
# Laisser a None tant que la valeur n'est pas connue : la ligne YTD
# est alors simplement omise, sans faire echouer le script.
CLOTURE_2025 = {
    "TUNINDEX": None,
    "Indice BANQUES": None,
    "Indice SERVICES FIN": None,
    "Attijari Bank": None,
    "Amen Bank": None,
    "BIAT": None,
    "Poulina PGH": None,
    "SFBT": None,
    "TPR": None,
}

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


# ---------------------------------------------------------------- utilitaires

def _num(s):
    """'19 450,38' -> 19450.38"""   
    return float(re.sub(r"[^\d,.-]", "", s).replace(",", "."))


def _fr(x, dec=2):
    """19450.38 -> '19 450,38'"""
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


# ------------------------------------------------------------------ irbe7 BVMT

def probe_irbe7():
    """Diagnostic ponctuel : HTML brut autour des pourcentages."""
    url = "https://irbe7.com/actifs/TJARI/TN0001600154"
    html = requests.get(url, headers=HEADERS, timeout=20).text
    for i, m in enumerate(re.finditer(r"\d+,\d+\s*%", html)):
        print(f"--- occurrence {i} ---")
        print(html[max(0, m.start() - 500):m.end() + 120])
        if i >= 2:
            break


def get_irbe7(name, url):
    """Cours BVMT depuis irbe7.com.

    irbe7 n'ecrit PAS le signe de la variation dans le texte (les baisses
    du bloc 'Top BAISSES' sont affichees sans '-'). Le sens est donc
    reconstruit en comparant le cours a la ligne 'Cloture veille'.
    Si cette ligne est absente, la variation est marquee '?'.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"Echec {name}: HTTP {r.status_code}")
            return f"{name} : indisponible"
        text = BeautifulSoup(r.content, 'html.parser').get_text(" ", strip=True)

        m = re.search(r"(\d[\d\s\u00a0]*,\d+)\s+(\d[\d\s\u00a0]*,\d+)\s*%", text)
        if not m:
            print(f"Echec extraction {name}: {text[:120]}")
            return f"{name} : indisponible"

        prix = _num(m.group(1))
        var = _num(m.group(2))

        # --- reconstruction du signe ---
        signe = None
        v = re.search(r"Cl[\w\u00f4]*ture\s+veille\s+(\d[\d\s\u00a0]*,\d+)", text)
        if v:
            veille = _num(v.group(1))
            if veille > 0:
                ecart = (prix / veille - 1) * 100
                # On ne retient le signe que s'il est franc.
                if abs(ecart) >= 0.005:
                    signe = -1 if ecart < 0 else 1
                elif var < 0.005:
                    signe = 1  # variation nulle des deux cotes
        if signe is None:
            bloc = f"({_fr(var)}% ?)"
        else:
            bloc = f"({'+' if signe > 0 else '-'}{_fr(var)}%"
            ref = CLOTURE_2025.get(name)
            if ref:
                bloc += f" | YTD {(prix / ref - 1) * 100:+.2f}%".replace(".", ",")
            bloc += ")"

        if signe is not None and CLOTURE_2025.get(name) is None:
            pass  # YTD absent : rien a ajouter

        print(f"OK {name}")
        return f"{name} : {_fr(prix)} {bloc}"
    except Exception as e:
        print(f"Erreur {name}: {e}")
    return f"{name} : indisponible"


# -------------------------------------------------------------------- Yahoo

def get_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    meta = r.json()["chart"]["result"][0]["meta"]
    price = meta["regularMarketPrice"]
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = (price - prev) / prev * 100 if prev else None
    return price, change


def get_ytd(symbol):
    """Variation depuis la cloture du 31/12, via la serie YTD de Yahoo."""
    try:
        url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
               "?range=ytd&interval=1d")
        res = requests.get(url, headers=HEADERS, timeout=15).json()["chart"]["result"][0]
        closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
        ref = res["meta"].get("chartPreviousClose") or (closes[0] if closes else None)
        prix = res["meta"]["regularMarketPrice"]
        return (prix / ref - 1) * 100 if ref else None
    except Exception as e:
        print(f"YTD indisponible {symbol}: {e}")
        return None


def fmt(price, change, unit, ytd=None):
    p = f"{price:.4f}" if price < 10 else f"{price:,.2f}".replace(",", " ")
    u = f" {unit}" if unit else ""
    parts = []
    if change is not None:
        parts.append(f"{change:+.2f}%")
    if ytd is not None:
        parts.append(f"YTD {ytd:+.2f}%")
    c = f" ({' | '.join(parts)})" if parts else ""
    return f"{p}{u}{c}"


# ---------------------------------------------------------------------- main

def main():
    if PROBE:
        probe_irbe7()
        return

    lines = ["== BOURSE DE TUNIS =="]
    for name, url in BVMT_ASSETS:
        lines.append(get_irbe7(name, url))

    lines.append("")
    lines.append("== INTERNATIONAL ==")
    for name, symbol, unit in INSTRUMENTS:
        try:
            price, change = get_quote(symbol)
            lines.append(f"{name} : {fmt(price, change, unit, get_ytd(symbol))}")
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
