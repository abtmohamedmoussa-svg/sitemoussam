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
    "BCT": "https://www.bct.gov.tn/",
    "CMF": "https://www.cmf.tn/",
    "BVMT2": "https://tunis-stockexchange.com/",
    "ilboursa": "https://www.ilboursa.com/",
    "WMC": "https://www.webmanagercenter.com/",
    "African Manager": "https://africanmanager.com/",
    "Economiste Maghrebin": "https://www.leconomistemaghrebin.com/",
    "Business News": "https://www.businessnews.com.tn/",
    "Tunisie Numérique" : "https://www.tunisienumerique.com/",
    "Kapitalis" : "https://kapitalis.com/tunisie/",
    "Tustex" : "https://www.tustex.com/",
    "Magazine Entreprise" : "https://www.entreprises-magazine.com",
    "Lapresse" : https://www.lapresse.tn/",
    "Managers": "https://managers.tn/",
    "TAP": "https://www.tap.info.tn/fr",
    "INS": "https://www.ins.tn/"
}

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_articles(url):
    """Retourne {lien: titre} des articles trouves sur la page."""
    try:
        r = requests.get(url, timeout=20, headers=HEADERS)
        soup = BeautifulSoup(r.content, 'html.parser')
        base = urlparse(url).netloc.replace('www.', '')
        articles = {}
        for a in soup.find_all('a', href=True):
            title = a.get_text(strip=True)
            href = urljoin(url, a['href']).split('#')[0]
            dom = urlparse(href).netloc.replace('www.', '')
            # Garde uniquement les liens du meme site avec un vrai titre
            if dom != base or len(title) < 30:
                continue
            if href not in articles:
                articles[href] = title[:200]
        return dict(list(articles.items())[:60])
    except Exception as e:
        print(f"   Erreur acces: {e}")
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
