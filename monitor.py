import requests
from bs4 import BeautifulSoup
import json
import os
from urllib.parse import urljoin, urlparse
from datetime import datetime

NTFY_TOPIC = "moussa-news-1313"
STATE_FILE = "state.json"
MAX_NOTIF_PER_SITE = 5

SITES = {
    "CMF": "https://www.cmf.tn/",
    "BVMT": "https://tunis-stockexchange.com/",
    "WMC": "https://www.webmanagercenter.com/",
    "Economiste Maghrebin": "https://www.leconomistemaghrebin.com/",
    "Business News": "https://www.businessnews.com.tn/",
    "Tunisie Numérique" : "https://www.tunisienumerique.com/",
    "Kapitalis" : "https://kapitalis.com/tunisie/",
    "Tustex" : "https://www.tustex.com/",
    "Magazine Entreprise" : "https://www.entreprises-magazine.com",
    "Lapresse" : "https://www.lapresse.tn/",
    "Managers": "https://managers.tn/",
    "TAP": "https://www.tap.info.tn/fr",
    "BCT": "https://news.google.com/rss/search?q=site:bct.gov.tn&hl=fr&gl=TN&ceid=TN:fr",
    "tunisievaleurs": "https://www.tunisievaleurs.com/",
    "macsa": "https://www.macsa.com.tn/",
    "ilboursa": "https://news.google.com/rss/search?q=site:ilboursa.com&hl=fr&gl=TN&ceid=TN:fr",
    "African Manager": "https://news.google.com/rss/search?q=site:africanmanager.com&hl=fr&gl=TN&ceid=TN:fr",
     "Moodys Tunisie": "https://news.google.com/rss/search?q=Moody's+Tunisia+rating&hl=en&gl=US&ceid=US:en",
    "SP Tunisie": "https://news.google.com/rss/search?q=%22S%26P+Global%22+Tunisia&hl=en&gl=US&ceid=US:en",
    "Fitch Tunisie": "https://news.google.com/rss/search?q=Fitch+Ratings+Tunisia&hl=en&gl=US&ceid=US:en",
    "FMI Tunisie": "https://news.google.com/rss/search?q=site:imf.org+Tunisia&hl=en&gl=US&ceid=US:en",
    "Banque Mondiale Tunisie": "https://news.google.com/rss/search?q=site:banquemondiale.org+Tunisie&hl=fr&gl=TN&ceid=TN:fr",
    "OCDE Tunisie": "https://news.google.com/rss/search?q=site:oecd.org+Tunisie+OR+Tunisia&hl=fr&gl=TN&ceid=TN:fr",
    "Reuters Tunisie": "https://news.google.com/rss/search?q=site:reuters.com+Tunisia&hl=en&gl=US&ceid=US:en",
    "Bloomberg Tunisie": "https://news.google.com/rss/search?q=site:bloomberg.com+Tunisia&hl=en&gl=US&ceid=US:en",
    "Agence Ecofin Tunisie": "https://news.google.com/rss/search?q=site:agenceecofin.com+Tunisie&hl=fr&gl=TN&ceid=TN:fr",
    "Financial Afrik Tunisie": "https://news.google.com/rss/search?q=site:financialafrik.com+Tunisie&hl=fr&gl=TN&ceid=TN:fr",
    "BAD Tunisie": "https://news.google.com/rss/search?q=site:afdb.org+Tunisia+OR+Tunisie&hl=fr&gl=TN&ceid=TN:fr",
    "Jeune Afrique Tunisie": "https://news.google.com/rss/search?q=site:jeuneafrique.com+Tunisie&hl=fr&gl=TN&ceid=TN:fr",
   "La Tribune Afrique Tunisie": "https://news.google.com/rss/search?q=site:latribune.fr+Tunisie&hl=fr&gl=TN&ceid=TN:fr",
    "FT Tunisie": "https://news.google.com/rss/search?q=site:ft.com+Tunisia&hl=en&gl=US&ceid=US:en",
    "Le Monde Tunisie": "https://news.google.com/rss/search?q=site:lemonde.fr+Tunisie&hl=fr&gl=TN&ceid=TN:fr",
    "RFI Tunisie": "https://news.google.com/rss/search?q=site:rfi.fr+Tunisie&hl=fr&gl=TN&ceid=TN:fr",
    "sikafinances": "https://news.google.com/rss/search?q=site:sikafinance.com&hl=fr&gl=TN&ceid=TN:fr",
    "BCT Actualites": "https://www.bct.gov.tn/bct/siteprod/actualites.jsp",
    "INS": "https://www.ins.tn/communique-de-presse",
    "BVMT Publications": "https://tunis-stockexchange.com/publications-societes",
    "BVMT Avis": "https://tunis-stockexchange.com/avis-decisions",
    "CMF Communiques societes": "https://www.cmf.tn/?q=informations-des-soci-t-s",
    "CMF Etats financiers": "https://www.cmf.tn/?q=consultation-des-tats-financier-des-soci-t-s-faisant-ape",
    "CMF Indicateurs activite": "https://www.cmf.tn/?q=indicateurs-d-activit-",
    "CMF Visas titres creance": "https://www.cmf.tn/?q=visas-accord-s-par-le-cmf",
    "CMF Visas capital": "https://www.cmf.tn/?q=visas-capital",
    "CMF Avis": "https://www.cmf.tn/?q=avis-et-d-cisions-du-cmf",
}
EXCLUS = ["Information économique et financière", "Bloomberg LEI"]
import re
import unicodedata

# ---- FILTRAGE SPORT / GUERRE -------------------------------------------
# False = mode observation : on journalise sans filtrer.
FILTRAGE_ACTIF = False

SITES_EXEMPTES = {
    "CMF", "BVMT", "BCT", "BCT Actualites", "INS",
    "BVMT Publications", "BVMT Avis",
    "CMF Communiques societes", "CMF Etats financiers",
    "CMF Indicateurs activite", "CMF Visas titres creance",
    "CMF Visas capital", "CMF Avis",
    "tunisievaleurs", "macsa", "Tustex", "ilboursa",
    "Moodys Tunisie", "SP Tunisie", "Fitch Tunisie",
    "FMI Tunisie", "Banque Mondiale Tunisie", "OCDE Tunisie", "BAD Tunisie",
}

EXCEPTIONS = [
    "guerre commerciale", "guerre des prix", "guerre tarifaire",
    "guerre economique", "guerre des monnaies", "guerre des devises",
    "guerre froide", "guerre des talents", "guerre de l'energie",
    "offensive commerciale", "offensive marketing",
    "conflit d'interets", "club de paris",
    "transfert de fonds", "transferts des tunisiens",
    "coupe budgetaire", "coupes budgetaires", "credit scoring",
]

URL_EXCLUS = [
    "/sport", "/sports", "/football", "/foot/", "/basket", "/handball",
    "/volley", "/athletisme", "/tennis/", "/rugby", "/cyclisme",
    "/jeux-olympiques", "/ligue-1", "/ligue1", "/mondial-", "/can-20",
]

SPORT = [
    "football", "foot", "basketball", "basket-ball", "basket", "handball",
    "volley-ball", "volleyball", "rugby", "athletisme", "natation",
    "cyclisme", "judo", "boxe", "marathon",
    "jeux olympiques", "olympique", "olympiques",
    "championnat", "championnats", "ligue des champions",
    "coupe du monde", "coupe d'afrique", "coupe de tunisie", "supercoupe",
    "derby", "mercato", "penalty", "buteur", "gardien de but",
    "attaquant", "milieu de terrain", "selectionneur", "entraineur",
    "arbitre", "mi-temps", "tacle", "equipe nationale", "ballon d'or",
    "fifa", "uefa", "caf", "ftf",
    "esperance sportive", "esperance de tunis", "club africain",
    "etoile du sahel", "stade tunisien", "us monastir", "cs sfaxien",
    "ca bizertin", "joueur", "joueurs", "match", "matchs", "matches",
    "sportif", "sportifs", "sportive",
]

GUERRE = [
    "guerre", "guerres", "conflit arme", "offensive",
    "bombardement", "bombardements", "bombarde",
    "missile", "missiles", "roquette", "roquettes",
    "frappe aerienne", "frappes aeriennes", "cessez-le-feu", "treve",
    "belligerant", "milice", "milices", "djihadiste", "djihadistes",
    "terroriste", "terroristes", "attentat", "attentats",
    "insurrection", "coup d'etat", "junte", "genocide", "massacre",
    "soldat", "soldats", "armee israelienne", "tsahal",
    "hamas", "hezbollah", "houthis", "gaza", "cisjordanie",
]


def _norm(s):
    """Minuscules, sans accents, apostrophes uniformisees."""
    s = s.lower().replace("\u2019", "'").replace("\u02bc", "'")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _compile(mots):
    mots = sorted(mots, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(m) for m in mots) + r")\b")


_RE_SPORT = _compile(SPORT)
_RE_GUERRE = _compile(GUERRE)


def motif_rejet(site, title, href):
    """Motif de rejet, ou None si l'article doit passer."""
    if site in SITES_EXEMPTES:
        return None
    t = _norm(title)
    if any(e in t for e in EXCEPTIONS):
        return None
    u = _norm(href)
    for seg in URL_EXCLUS:
        if seg in u:
            return "url " + seg
    m = _RE_SPORT.search(t)
    if m:
        return "sport: " + m.group(1)
    m = _RE_GUERRE.search(t)
    if m:
        return "guerre: " + m.group(1)
    return None
# ------------------------------------------------------------------------



HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8'
}

def fetch(url):
    """Recupere la page, avec repli si certificat SSL invalide."""
    try:
        return requests.get(url, timeout=25, headers=HEADERS)
    except requests.exceptions.SSLError:
        import urllib3
        urllib3.disable_warnings()
        return requests.get(url, timeout=25, headers=HEADERS, verify=False)

def get_articles(url):
    """Retourne {lien: titre} des articles trouves sur la page."""
    try:
        r = fetch(url)
        print(f"   HTTP {r.status_code}")
        if r.status_code != 200:
            return {}
        soup = BeautifulSoup(r.content, 'html.parser')
        base = urlparse(url).netloc.replace('www.', '')
        min_len = 12 if "cmf.tn" in base else 30
        articles = {}
        for a in soup.find_all('a', href=True):
            title = a.get_text(strip=True)
            href = urljoin(url, a['href']).split('#')[0]
            dom = urlparse(href).netloc.replace('www.', '')
            if dom != base:
                continue
            if not title and href.lower().endswith('.pdf'):
                title = href.rsplit('/', 1)[-1].replace('_', ' ').replace('.pdf', '')
            if len(title) < min_len:
                continue
            if href not in articles:
                articles[href] = title[:200]
        return dict(list(articles.items())[:80])
    except Exception as e:
        print(f"   Erreur acces: {e}")
        return {}
        
def get_articles_rss(url):
    """Lit un flux RSS (Google News), articles de moins de 7 jours uniquement."""
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime
    from datetime import datetime, timezone, timedelta
    try:
        r = fetch(url)
        print(f"   HTTP {r.status_code} (RSS)")
        if r.status_code != 200:
            return {}
        root = ET.fromstring(r.content)
        articles = {}
        limite = datetime.now(timezone.utc) - timedelta(days=7)
        ignores = 0
        for item in root.iter('item'):
            title = (item.findtext('title') or '').strip()
            link = (item.findtext('link') or '').strip()
            pub = (item.findtext('pubDate') or '').strip()
            if pub:
                try:
                    if parsedate_to_datetime(pub) < limite:
                        ignores += 1
                        continue
                except Exception:
                    pass
            if title and link:
                articles[link] = title[:200]
        if ignores:
            print(f"   {ignores} article(s) ancien(s) ignore(s)")
        return dict(list(articles.items())[:60])
    except Exception as e:
        print(f"   Erreur RSS: {e}")
        return {}

def notify(site, title, link):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=title.encode('utf-8'),
            headers={
                "Title": site.encode('ascii', 'ignore').decode(),
                "Click": link,
                "Tags": "newspaper"
            },
            timeout=10
        )
        print(f"   Notif envoyee: {title[:60]}")
    except Exception as e:
        print(f"   Erreur notif: {e}")

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def monitor():
    print(f"[{datetime.now()}] Verification des sites...")
    state = load_state()

    for site, url in SITES.items():
        key = site + "|urls"
        print(f"-> {site}")
        if "news.google.com" in url:
            articles = get_articles_rss(url)
        else:
            articles = get_articles(url)
        if not articles:
            print("   Site inaccessible ou aucun article trouve")
            continue

        known = set(state.get(key, []))

        if not known:
            # Premiere fois pour ce site : on memorise sans notifier
            print(f"   Baseline: {len(articles)} articles memorises")
        else:
            new = {h: t for h, t in articles.items() if h not in known}
            if "Tunisie" in site:
                new = {h: t for h, t in new.items() if "tunis" in t.lower()}
                        for href, title in list(new.items()):
                motif = motif_rejet(site, title, href)
                if motif:
                    print(f"   [FILTRE {motif}] {title[:80]}")
                    if FILTRAGE_ACTIF:
                        del new[href]

            
            uniques = {}
            for h, t in new.items():
                if t not in uniques.values():
                    uniques[h] = t
            new = uniques
            new = {h: t for h, t in new.items() if not any(x in t for x in EXCLUS)}
            print(f"   {len(new)} nouveau(x) article(s)")
            for i, (href, title) in enumerate(new.items()):
                if i >= MAX_NOTIF_PER_SITE:
                    notify(site, f"+ {len(new) - MAX_NOTIF_PER_SITE} autres nouveaux articles", url)
                    break
                notify(site, title, href)

        # Memorise (garde les 300 derniers liens connus)
        state[key] = list(dict.fromkeys(list(articles.keys()) + list(known)))[:300]

    save_state(state)

if __name__ == "__main__":
    monitor()
