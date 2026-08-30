import re
import unicodedata
import os
import socket
import requests
import urllib3.util.connection as _u3conn
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from datetime import datetime

# Les runners GitHub n'ont pas de route IPv6. ntfy.sh publie un AAAA :
# requests tente l'IPv6 en premier et echoue en "Network is unreachable".
# On force la resolution en IPv4 pour tout le script.
_u3conn.allowed_gai_family = lambda: socket.AF_INET

SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=1.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"])))

NTFY_TOPIC = "moussa-news-1313"

# Page unique irbe7 : tableau des actions + tableau des indices, tous deux
# avec le SIGNE de la variation. Remplace les 10 pages individuelles, ou le
# signe est absent du texte et ou la colonne 'Cloture Veille' reprend le
# cours du jour au lieu de celui de la veille.
IRBE7_URL = "https://irbe7.com/actifs"

# (libelle affiche, libelle exact dans le tableau irbe7)
CIBLES_BVMT = [
    ("TUNINDEX",            "TUNINDEX"),
    ("Indice BANQUES",      "BANQUES"),
    ("Indice SERVICES FIN", "SERVICES FINANCIER"),
    ("Attijari Bank",       "ATTIJARI BANK"),
    ("Attijari Leasing",    "ATTIJARI LEASING"),
    ("Amen Bank",           "AMEN BANK"),
    ("BIAT",                "BIAT"),
    ("Poulina PGH",         "POULINA GP HOLDING"),
    ("SFBT",                "SFBT"),
    ("TPR",                 "TPR"),
]

# Clotures du 31/12/2025 - source : Physionomie Boursiere BVMT, seance
# n°248 du mercredi 31 decembre 2025. A remplacer chaque 2 janvier.
#
# ATTENTION : le YTD calcule ici est une performance de COURS, pas une
# performance totale. Il ne neutralise ni les detachements de dividende
# ni les operations sur titres (actions gratuites, augmentations de
# capital, splits). Il sous-estime donc la performance reelle des lignes
# ayant detache un coupon en 2026.
CLOTURE_2025 = {
    "TUNINDEX":            13449.95,   # bloc indice, page 2 du rapport
    "Indice BANQUES":       9669.60,   # INDICE DES BANQUES, "Indice du Jour"
    "Indice SERVICES FIN": 18731.77,   # INDICE DES SERVICES FINANCIERS
    "Attijari Bank":          66.890,  # colonne "Cloture", page 6
    "Attijari Leasing":       29.250,
    "Amen Bank":              50.000,
    "BIAT":                  111.000,
    "Poulina PGH":            18.500,
    "SFBT":                   12.600,
    "TPR":                    11.500,
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

BCT_URLS = [
    "https://www.bct.gov.tn/bct/siteprod/indicateurs.jsp",
    "https://www.bct.gov.tn/bct/siteprod/index.jsp",
    "https://www.bct.gov.tn/",
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# Nombre francais avec milliers groupes par 3 : '19 450,38', '87,15'.
# Le (?<!\w) evite de mordre sur le '1' d'un ticker type 'PX1'.
_MONTANT = re.compile(r"(?<!\w)\d{1,3}(?:[ \u00a0\u202f]\d{3})*,\d+")
_PCT = re.compile(r"([+-])\s?(\d+,\d+)\s*%")

_NB = r"(\d[\d\s\u00a0\u202f]*(?:,\d+)?)"
P_DEVISES = re.compile(
    r"AVOIRS NETS EN DEVISES\s+AU\s+(\d{2}/\d{2}/\d{4}).{0,20}?EN MDT\s*:?\s*"
    + _NB + r".{0,40}?IMPORTATION\s*:?\s*" + _NB)
P_BILLETS = re.compile(
    r"BILLETS ET MONNAIES EN CIRCULATION\s+AU\s+(\d{2}/\d{2}/\d{4})\s*:?\s*" + _NB)
P_REFI = re.compile(
    r"VOLUME GLOBAL DE REFINANCEMENT\s+AU\s+(\d{2}/\d{2}/\d{4})\s*:?\s*" + _NB)


# ---------------------------------------------------------------- utilitaires

def _num(s):
    return float(re.sub(r"[^\d,.-]", "", s).replace(",", "."))


def _fr(x, dec=2):
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")


def _plat(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().upper()


def _signe(x, dec=2):
    return f"{'+' if x >= 0 else '-'}{_fr(abs(x), dec)}"


# ------------------------------------------------------------------ BVMT

def get_bvmt():
    """Cours et variations signees, en un seul appel sur irbe7.com/actifs."""
    lines = ["== BOURSE DE TUNIS =="]
    try:
        r = SESSION.get(IRBE7_URL, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            print(f"irbe7: HTTP {r.status_code}")
            return lines + ["Indisponible"]

        soup = BeautifulSoup(r.content, 'html.parser')
        rangs = []
        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2:
                rangs.append((_plat(cells[0]), _plat(" ".join(cells))))
        print(f"irbe7: {len(rangs)} lignes de tableau")

        for nom, lib in CIBLES_BVMT:
            trouve = None
            for premier, texte in rangs:
                # (\s|$) evite que 'TUNINDEX' capture la ligne 'TUNINDEX20'
                if re.match(re.escape(lib) + r"(\s|$)", premier):
                    trouve = texte
                    break
            if not trouve:
                print(f"irbe7: '{lib}' introuvable")
                lines.append(f"{nom} : indisponible")
                continue
            pct = _PCT.search(trouve)
            montants = _MONTANT.findall(trouve)
            if not (pct and montants):
                print(f"irbe7: '{lib}' non parse | {trouve[:110]}")
                lines.append(f"{nom} : indisponible")
                continue
            prix = _num(montants[0])
            var = (-1 if pct.group(1) == "-" else 1) * _num(pct.group(2))

            parts = [f"{_signe(var)}%"]
            ref = CLOTURE_2025.get(nom)
            if ref:
                parts.append(f"YTD {_signe((prix / ref - 1) * 100)}%")
            print(f"OK {nom} {prix} {var:+.2f}%")
            lines.append(f"{nom} : {_fr(prix)} ({' | '.join(parts)})")
    except Exception as e:
        print(f"Erreur irbe7: {e}")
        return lines + ["Indisponible"]
    return lines


# --------------------------------------------------------------------- BCT

def _bct_texte():
    """Concatene le texte des pages BCT candidates.

    Le bloc de synthese (avoirs nets, billets, refinancement) n'est pas
    forcement sur indicateurs.jsp : on balaie plusieurs pages et on
    journalise celle qui porte l'information.
    """
    morceaux = []
    for url in BCT_URLS:
        try:
            r = SESSION.get(url, headers=HEADERS, timeout=30)
            if r.status_code != 200:
                print(f"BCT {url}: HTTP {r.status_code}")
                continue
            # windows-1252 force : sinon BeautifulSoup decode en iso-8859-2.
            soup = BeautifulSoup(r.content, 'html.parser', from_encoding='windows-1252')
            t = _plat(soup.get_text(" ", strip=True))
            print(f"BCT {url}: {len(t)} car. | AVOIRS={'AVOIRS' in t} "
                  f"BILLETS={'BILLETS' in t} REFI={'REFINANCEMENT' in t}")
            morceaux.append(t)
        except Exception as e:
            print(f"BCT {url}: {e}")
    return " ".join(morceaux)


def _bct_diag(txt, mot):
    """Affiche le contexte brut autour d'un mot-cle non reconnu."""
    for i, m in enumerate(re.finditer(mot, txt)):
        print(f"   [{mot} #{i}] ...{txt[max(0, m.start()-60):m.end()+170]}...")
        if i >= 1:
            return
    print(f"   [{mot}] absent du texte recupere")


def get_bct():
    """Indicateurs quotidiens BCT : reserves, billets, refinancement."""
    lines = ["== BCT =="]
    try:
        txt = _bct_texte()
        if not txt:
            return lines + ["Indisponible"]

        m = P_DEVISES.search(txt)
        if m:
            lines.append(f"Reserves de change ({m.group(1)[:5]}) : "
                         f"{_fr(_num(m.group(2)), 0)} MDT - "
                         f"{_fr(_num(m.group(3)), 0)} j import.")
            print(f"OK BCT devises {m.group(2)} MDT / {m.group(3)} jours")
        else:
            lines.append("Reserves de change : indisponible")
            print("BCT: avoirs nets en devises non reconnus")
            _bct_diag(txt, "AVOIRS NETS EN DEVISES")

        m = P_BILLETS.search(txt)
        if m:
            lines.append(f"Billets en circulation ({m.group(1)[:5]}) : "
                         f"{_fr(_num(m.group(2)), 0)} MDT")
            print(f"OK BCT billets {m.group(2)}")
        else:
            lines.append("Billets en circulation : indisponible")
            print("BCT: billets non reconnus")
            _bct_diag(txt, "BILLETS ET MONNAIES")

        m = P_REFI.search(txt)
        if m:
            lines.append(f"Refinancement ({m.group(1)[:5]}) : "
                         f"{_fr(_num(m.group(2)), 0)} MDT")
            print(f"OK BCT refinancement {m.group(2)}")
        else:
            lines.append("Refinancement : indisponible")
            print("BCT: refinancement non reconnu")
            _bct_diag(txt, "REFINANCEMENT")
    except Exception as e:
        print(f"Erreur BCT: {e}")
        return lines + ["Indisponible"]
    return lines


# -------------------------------------------------------------------- Yahoo

def get_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = SESSION.get(url, headers=HEADERS, timeout=15)
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
        res = SESSION.get(url, headers=HEADERS, timeout=15).json()["chart"]["result"][0]
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

def send_telegram(message):
    """Envoie le message via un bot Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    
    if not bot_token or not chat_id:
        print("Telegram non configure (BOT_TOKEN ou CHAT_ID absent)")
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        SESSION.post(url, json={
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=15)
        print("Resume Telegram envoye")
    except Exception as e:
        print(f"Envoi Telegram KO (non bloquant): {e}")


def main():
    lines = get_bvmt()

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
    print("\n" + message + "\n")

    # Format Telegram : emojis pour direction + gras pour titres + italique pour YTD
    message_telegram = message.replace(
        "== ", "<b>== ").replace(" ==", " ==</b>"
    ).replace("YTD ", "<i>YTD </i>")
    
    # Ajouter emojis de direction : (+ ou - suivi de chiffres et %)
    import re
    message_telegram = re.sub(
        r"(\()([\+\-]\d+,\d+%)",
        lambda m: m.group(1) + ("📈 " if m.group(2).startswith("+") else "📉 ") + m.group(2),
        message_telegram)
    
    try:
        SESSION.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": f"Marches du {datetime.now().strftime('%d/%m %H:%M')}",
                "Tags": "chart_with_upwards_trend",
                "Priority": "default"
            },
            timeout=20
        )
        print("Resume envoye")
    except Exception as e:
        # Le resume est deja dans les logs ci-dessus : on n'echoue pas le run.
        print(f"Envoi ntfy KO (non bloquant): {e}")

    send_telegram(message_telegram)


if __name__ == "__main__":
    main()
