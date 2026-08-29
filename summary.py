import re
import unicodedata
import requests
from bs4 import BeautifulSoup
from datetime import datetime

NTFY_TOPIC = "moussa-news-1313"

# Diagnostics ponctuels. Remettre a False une fois le probleme identifie.
PROBE_IRBE7 = False
PROBE_BCT = False

BVMT_ASSETS = [
    ("TUNINDEX", "https://irbe7.com/actifs/TUNINDEX/TN0009050014"),
    ("Indice BANQUES", "https://irbe7.com/actifs/BANQUES/TN0009050030"),
    ("Indice SERVICES FIN", "https://irbe7.com/actifs/SERVICES%20FINANCIER/TN0009050055"),
    ("Attijari Bank", "https://irbe7.com/actifs/TJARI/TN0001600154"),
    ("Attijari Leasing", "https://irbe7.com/actifs/ATTIJARI%20LEASING/TN0006610018"),
    ("Amen Bank", "https://irbe7.com/actifs/AMEN%20BANK/TN0003400058"),
    ("BIAT", "https://irbe7.com/actifs/BIAT/TN0001800457"),
    ("Poulina PGH", "https://irbe7.com/actifs/POULINA%20GP%20HOLDING/TN0005700018"),
    ("SFBT", "https://irbe7.com/actifs/SFBT/TN0001100254"),
    ("TPR", "https://irbe7.com/actifs/TPR/TN0007270010"),
]

# Clotures du 31/12/2025, a renseigner une fois par an.
# None = mention YTD simplement omise, sans erreur.
CLOTURE_2025 = {
    "TUNINDEX": None,
    "Indice BANQUES": None,
    "Indice SERVICES FIN": None,
    "Attijari Bank": None,
    "Attijari Leasing": None,
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

BCT_URL = "https://www.bct.gov.tn/bct/siteprod/indicateurs.jsp"

# Libelles cibles sur la page BCT. Plusieurs variantes par indicateur :
# le libelle exact n'est confirme que pour les billets en circulation.
BCT_CIBLES = [
    ("Reserves de change", [
        r"AVOIRS\s+NETS\s+EN\s+DEVISES",
        r"RESERVES\s+EN\s+DEVISES",
        r"RESERVES\s+DE\s+CHANGE",
        r"AVOIRS\s+EN\s+DEVISES",
    ]),
    ("Billets en circulation", [
        r"BILLETS\s+ET\s+MONNAIES\s+EN\s+CIRCULATION",
    ]),
    ("Refinancement", [
        r"VOLUME\s+GLOBAL\s+DE\s+REFINANCEMENT",
        r"VOLUME\s+DE\s+REFINANCEMENT",
        r"REFINANCEMENT\s+GLOBAL",
        r"REFINANCEMENT",
    ]),
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Nombre francais : '19 450,38', '19 450,38' (espace fine), '30186', '-126,2'
RE_NOMBRE = re.compile(
    r"-?\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?"
)


# ---------------------------------------------------------------- utilitaires

def _num(s):
    """'19 450,38' -> 19450.38 (tolere toutes les variantes d'espace)."""
    return float(re.sub(r"[^\d,.-]", "", s).replace(",", "."))


def _fr(x, dec=2):
    """19450.38 -> '19 450,38'"""
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def _plat(s):
    """Minuscules -> majuscules, sans accents, espaces normalises."""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).upper()


# ------------------------------------------------------------------ irbe7 BVMT

def probe_irbe7():
    """HTML brut autour des pourcentages : identifie le balisage du signe."""
    url = "https://irbe7.com/actifs/TJARI/TN0001600154"
    html = requests.get(url, headers=HEADERS, timeout=20).text
    for i, m in enumerate(re.finditer(r"\d+,\d+\s*%", html)):
        print(f"--- occurrence {i} ---")
        print(html[max(0, m.start() - 500):m.end() + 120])
        if i >= 2:
            break


def get_irbe7(name, url):
    """Cours BVMT depuis irbe7.com.

    irbe7 n'ecrit pas le signe de la variation dans le texte : le sens est
    reconstruit a partir de la ligne 'Cloture veille'. Si elle est
    introuvable, la variation est marquee '?' plutot que d'afficher un
    signe invente.
    """
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"Echec {name}: HTTP {r.status_code}")
            return f"{name} : indisponible"
        text = BeautifulSoup(r.content, 'html.parser').get_text(" ", strip=True)

        m = re.search(r"(\d[\d\s\u00a0\u202f]*,\d+)\s+(\d[\d\s\u00a0\u202f]*,\d+)\s*%", text)
        if not m:
            print(f"Echec extraction {name}: {text[:120]}")
            return f"{name} : indisponible"

        prix = _num(m.group(1))
        var = _num(m.group(2))

        signe = None
        v = re.search(r"veille\D{0,10}(\d[\d\s\u00a0\u202f]*,\d+)", text, re.I)
        if v:
            veille = _num(v.group(1))
            if veille > 0:
                ecart = (prix / veille - 1) * 100
                if abs(ecart) >= 0.005:
                    signe = -1 if ecart < 0 else 1
                elif var < 0.005:
                    signe = 1
        else:
            i = text.lower().find("veille")
            extrait = text[max(0, i - 90):i + 90] if i >= 0 else "MOT ABSENT | " + text[:200]
            print(f"   veille ? {name}: {extrait}")

        if signe is None:
            bloc = f"({_fr(var)}% ?)"
        else:
            bloc = f"({'+' if signe > 0 else '-'}{_fr(var)}%"
            ref = CLOTURE_2025.get(name)
            if ref:
                ytd = (prix / ref - 1) * 100
                bloc += f" | YTD {'+' if ytd >= 0 else '-'}{_fr(abs(ytd))}%"
            bloc += ")"

        print(f"OK {name}")
        return f"{name} : {_fr(prix)} {bloc}"
    except Exception as e:
        print(f"Erreur {name}: {e}")
    return f"{name} : indisponible"


# --------------------------------------------------------------------- BCT

def _bct_texte():
    """Texte de la page indicateurs BCT, encodage force.

    La page est servie en windows-1252 ; sans from_encoding, BeautifulSoup
    la decode en iso-8859-2 et produit 'Mis ŕ jour' au lieu de 'Mis a jour'.
    """
    r = requests.get(BCT_URL, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        print(f"BCT: HTTP {r.status_code}")
        return None
    soup = BeautifulSoup(r.content, 'html.parser', from_encoding='windows-1252')
    return soup.get_text(" ", strip=True)


def probe_bct():
    """Liste les intitules de rubriques de la page BCT."""
    text = _bct_texte()
    if not text:
        return
    txt = _plat(text)
    d = re.search(r"(\d{2}/\d{2}/\d{4})", txt)
    print("BCT date:", d.group(1) if d else "inconnue")
    print("BCT rubriques trouvees :")
    for m in re.finditer(r"\b([IVX]{1,5})-\s*([A-Z'()/ ]{6,70})", txt):
        suite = txt[m.end():m.end() + 90]
        print(f"   {m.group(1)}- {m.group(2).strip()}  >>>  {suite[:70]}")


def _bct_ligne(txt, motifs):
    """Retourne (date, [valeurs]) pour le premier motif qui matche."""
    for p in motifs:
        m = re.search(p, txt)
        if not m:
            continue
        suite = txt[m.end():m.end() + 200]
        d = re.match(r"\s*(\d{1,2}/\d{1,2})", suite)
        date = d.group(1) if d else None
        if d:
            suite = suite[d.end():]
        vals = [_num(x) for x in RE_NOMBRE.findall(suite)[:3]]
        if vals:
            return date, vals, m.group(0)
    return None, [], None


def get_bct():
    """Indicateurs quotidiens BCT : reserves, billets, refinancement.

    Colonnes de la page (verifiees sur la ligne 'BILLETS ET MONNAIES') :
    [0] jour J, [1] jour j-1, [2] meme jour annee precedente.
    """
    lines = []
    try:
        text = _bct_texte()
        if not text:
            return ["BCT : indisponible"]
        txt = _plat(text)

        d = re.search(r"(\d{2}/\d{2}/\d{4})", txt)
        lines.append(f"== BCT ({d.group(1) if d else 'date inconnue'}) ==")

        for nom, motifs in BCT_CIBLES:
            date, vals, libelle = _bct_ligne(txt, motifs)
            if not vals:
                print(f"BCT: '{nom}' introuvable")
                lines.append(f"{nom} : indisponible")
                continue
            ligne = f"{nom} : {_fr(vals[0], 1)} MDT"
            if len(vals) >= 2:
                delta = vals[0] - vals[1]
                ligne += f" (j-1 {'+' if delta >= 0 else '-'}{_fr(abs(delta), 1)}"
                if len(vals) >= 3 and vals[2]:
                    an = (vals[0] / vals[2] - 1) * 100
                    ligne += f" | 1 an {'+' if an >= 0 else '-'}{_fr(abs(an))}%"
                ligne += ")"
            print(f"OK BCT {nom} [{libelle}] {vals}")
            lines.append(ligne)
    except Exception as e:
        print(f"Erreur BCT: {e}")
        return ["BCT : indisponible"]
    return lines


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
    if PROBE_IRBE7:
        probe_irbe7()
        return
    if PROBE_BCT:
        probe_bct()
        return

    lines = ["== BOURSE DE TUNIS =="]
    for name, url in BVMT_ASSETS:
        lines.append(get_irbe7(name, url))

    lines.append("")
    lines.extend(get_bct())

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
