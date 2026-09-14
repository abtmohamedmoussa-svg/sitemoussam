import os
import json
import re
import requests
import time
from datetime import datetime, timedelta

NTFY_TOPIC = "moussa-news-1313"
JOURNAL_FILE = "journal.json"
OUT_DIR = "public"
MODELES = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-flash-latest"]

owner = os.getenv("GITHUB_REPOSITORY_OWNER", "").lower()
BASE_URL = f"https://{owner}.github.io/veille-tunisie"

CONSIGNE = """Tu es analyste pour le responsable de la banque de financement et d'investissement d'une grande banque tunisienne.
A partir de la liste d'articles ci-dessous (titre + source + lien), redige une synthese de la journee en francais.

REGLES:
- Concentre-toi sur l'economie, la banque, la finance, la bourse et la reglementation financiere.
- N'inclus une information politique QUE si elle a un impact economique ou financier fort.
- Ignore le sport, la culture, les faits divers, les sujets sans lien avec l'economie tunisienne ou son environnement.
- Regroupe par familles, dans cet ordre, en omettant toute famille vide:
  1. Regulateurs et institutions (BCT, CMF, BVMT, INS)
  2. Bourse et societes cotees
  3. Banques et secteur financier
  4. Macroeconomie et conjoncture tunisienne
  5. International et notations souveraines
  6. Politique a fort impact economique
- Pour chaque famille: des puces courtes et factuelles. Une puce = un fait, avec le lien source en HTML.
- Regroupe les doublons entre sources en une seule puce citant les sources principales.
- Commence par un paragraphe "L'essentiel" de 3 a 5 lignes sur les faits les plus importants du jour.
- Sois factuel, pas de remplissage, pas de superlatifs. Si une information est mince, ne la gonfle pas.

FORMAT DE SORTIE: uniquement du HTML (h2, p, ul, li, a). Pas de <html> ni <body>, pas de balises de code markdown.

ARTICLES DU JOUR:
"""

def modeles_disponibles(key):
    try:
        r = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}", timeout=30)
        if r.status_code == 200:
            noms = [m["name"].replace("models/", "") for m in r.json().get("models", [])
                    if "generateContent" in m.get("supportedGenerationMethods", [])]
            print("Modeles disponibles: " + ", ".join(noms))
            return noms
        print(f"ListModels: HTTP {r.status_code}")
    except Exception as e:
        print(f"ListModels erreur: {e}")
    return []

EXCLUS_MODELES = ("image", "tts", "transcribe", "omni", "robotics", "lyria",
                  "nano", "deep-research", "computer-use", "embedding", "gemma", "2.5")

def gemini(prompt):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("GEMINI_API_KEY absente")
        return None

    dispo = modeles_disponibles(key)
    bons = list(MODELES)
    for m in dispo:
        if ("flash" in m and "lite" not in m
                and not any(x in m for x in EXCLUS_MODELES) and m not in bons):
            bons.append(m)
    secours = [m for m in dispo
               if "lite" in m and not any(x in m for x in EXCLUS_MODELES)]

    def essayer(liste):
        for m in liste:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
            try:
                r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=180)
                if r.status_code == 200:
                    print(f"Modele utilise: {m}")
                    return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                print(f"{m}: HTTP {r.status_code}")
            except Exception as e:
                print(f"{m}: erreur {e}")
        return None

    for tentative in range(4):
        res = essayer(bons)
        if res:
            return res
        print(f"Surcharge Google (essai {tentative + 1}/4), attente 60s...")
        time.sleep(60)

    print("Repli sur les modeles alleges")
    return essayer(secours)

def nettoyer(txt):
    t = txt.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        t = t.rsplit("```", 1)[0]
    return t.strip()

CSS = """body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:820px;margin:0 auto;
padding:20px;line-height:1.6;color:#1a1a1a;background:#fafafa}
h1{font-size:1.5em;border-bottom:3px solid #0a4d8c;padding-bottom:10px;color:#0a4d8c}
h2{font-size:1.15em;margin-top:28px;color:#0a4d8c;border-left:4px solid #0a4d8c;padding-left:10px}
a{color:#0a4d8c}li{margin-bottom:8px}
.meta{color:#666;font-size:.85em}
.nav{margin:20px 0;padding:12px;background:#fff;border-radius:6px}
.essentiel{background:#fff;padding:14px;border-radius:6px;border-left:4px solid #d97706}"""

def page(titre, corps):
    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titre}</title><style>{CSS}</style></head><body>
<h1>{titre}</h1>{corps}
<div class="nav"><a href="index.html">Toutes les syntheses</a></div>
</body></html>"""

def html_vers_texte(h):
    t = re.sub(r"<(strong|b)>", "<b>", h, flags=re.I)
    t = re.sub(r"</(strong|b)>", "</b>", t, flags=re.I)
    t = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n\n<b>\1</b>", t, flags=re.S | re.I)
    t = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", t, flags=re.S | re.I)
    t = re.sub(r"</?(p|ul|ol|div|span|em|i|br|hr)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def telegram(message, parse="HTML"):
    token = os.getenv("TELEGRAM_TOKEN1")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("Telegram non configure")
        return
    payload = {"chat_id": chat, "text": message, "disable_web_page_preview": True}
    if parse:
        payload["parse_mode"] = parse
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json=payload, timeout=30)
        if r.status_code == 200:
            print("Telegram: envoye")
            return
        print(f"Telegram: HTTP {r.status_code} - {r.text[:200]}")
    except Exception as e:
        print(f"Telegram: erreur {e}")
    if parse:
        print("Telegram: nouvel essai en texte brut")
        telegram(re.sub(r"<[^>]+>", "", message), parse=None)

def main():
    with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
        journal = json.load(f)

    jour = datetime.now().strftime("%Y-%m-%d")
    articles = journal.get(jour, [])
    print(f"{len(articles)} article(s) collecte(s) le {jour}")

    os.makedirs(OUT_DIR, exist_ok=True)

    if not articles:
        corps = "<p>Aucun article collecte aujourd'hui.</p>"
    else:
        liste = "\n".join(
            f"- [{a['site']}] {a['titre']} ({a['lien']})" for a in articles[:400]
        )
        texte = gemini(CONSIGNE + liste)
        if texte:
            corps = nettoyer(texte)
        else:
            corps = "<p>Synthese IA indisponible. Liste brute des articles :</p><ul>" + "".join(
                f"<li><strong>{a['site']}</strong> : <a href=\"{a['lien']}\">{a['titre']}</a></li>"
                for a in articles
            ) + "</ul>"

    corps += f"<p class='meta'>{len(articles)} articles analyses - genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')}</p>"

    with open(f"{OUT_DIR}/{jour}.html", "w", encoding="utf-8") as f:
        f.write(page(f"Veille du {datetime.now().strftime('%d/%m/%Y')}", corps))

    # Index des 30 derniers jours
    limite = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    jours = sorted([d for d in journal if d >= limite], reverse=True)
    liens = "".join(
        f"<li><a href='{d}.html'>{datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m/%Y')}</a>"
        f" <span class='meta'>({len(journal[d])} articles)</span></li>" for d in jours
    )
    with open(f"{OUT_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(page("Syntheses quotidiennes", f"<ul>{liens}</ul>"))

    lien_jour = f"{BASE_URL}/{jour}.html"
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=f"Synthese du {datetime.now().strftime('%d/%m/%Y')} - {len(articles)} articles analyses".encode('utf-8'),
        headers={"Title": "Veille quotidienne", "Click": lien_jour, "Tags": "memo"},
        timeout=10
    )
    print(f"Publie: {lien_jour}")
    entete = (f"<b>Veille du {datetime.now().strftime('%d/%m/%Y')}</b> - "
              f"{len(articles)} articles\n{lien_jour}\n")
    telegram((entete + "\n" + html_vers_texte(corps))[:3900])
  
if __name__ == "__main__":
    main()
