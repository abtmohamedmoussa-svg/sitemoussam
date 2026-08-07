import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime

NTFY_TOPIC = "moussa-news-1313"
STATE_FILE = "state.json"

SITES = {
    "BCT": "https://www.bct.gov.tn/",
    "CMF": "https://www.cmf.org.tn/",
    "BVMT": "https://www.bvmt.com.tn/",
    "BVMT2": "https://tunis-stockexchange.com/",
    "ilboursa" : "https://www.ilboursa.com/",
    "WMC" : "https://www.webmanagercenter.com/",
    "African Manager" : "https://africanmanager.com/",
    "Economiste Maghrebin" : "https://www.leconomistemaghrebin.com/",
    "Business news" : "https://www.businessnews.com.tn/",
    "Managers" : "https://managers.tn/",
    "Tunisie Numérique" : "https://www.tunisienumerique.com/",
    "Kapitalis" : "https://kapitalis.com/tunisie/",
    "Tustex" : "https://www.tustex.com/",
    "Magazine Entreprise" : "https://www.entreprises-magazine.com",
    "Lapresse" : https://www.lapresse.tn/",
    "TAP": "https://www.tap.info.tn/fr",    
    "INS": "https://www.ins.tn/"
}

def get_site_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, timeout=15, headers=headers)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'a']):
            text = tag.get_text(strip=True)
            if len(text) > 15 and text not in articles:
                articles.append(text[:150])
        return articles[:30]
    except Exception as e:
        print(f"Erreur sur {url}: {e}")
        return []

def send_notification(site_name, url, new_items):
    message = "\n".join(f"- {item}" for item in new_items[:5])
    message += f"\n\n{url}"
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={
                "Title": f"{site_name} : nouvelle publication",
                "Priority": "default",
                "Tags": "newspaper"
            },
            timeout=10
        )
        print(f"   Notification envoyee pour {site_name}")
    except Exception as e:
        print(f"   Erreur notification: {e}")

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
    first_run = not state

    for site_name, url in SITES.items():
        print(f"-> Verification {site_name}...")
        current = get_site_content(url)
        if not current:
            continue
        previous = set(state.get(site_name, []))
        new_items = [item for item in current if item not in previous]

        if new_items and not first_run:
            print(f"   {len(new_items)} nouveaute(s) detectee(s)")
            send_notification(site_name, url, new_items)
        elif first_run:
            print(f"   Premiere execution : {len(current)} elements memorises")
        else:
            print("   Rien de nouveau")

        state[site_name] = current

    save_state(state)
    if first_run:
        try:
            requests.post(
                f"https://ntfy.sh/{NTFY_TOPIC}",
                data="Le monitoring BCT / CMF / BVMT / INS est actif. Tu recevras une notification a chaque nouvelle publication.".encode('utf-8'),
                headers={"Title": "Monitoring active", "Tags": "white_check_mark"},
                timeout=10
            )
        except Exception:
            pass

if __name__ == "__main__":
    monitor()
