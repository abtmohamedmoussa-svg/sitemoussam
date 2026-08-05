import requests
from bs4 import BeautifulSoup
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os

# Configuration des sites à monitorer
SITES = {
    "BCT": "https://www.bct.gov.tn/",
    "CMF": "https://www.cmf.org.tn/",
    "TSE": "https://www.bvmt.com.tn/",
    "INS": "https://www.ins.tn/"
}

# Fonction pour extraire le contenu d'un site
def get_site_content(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extrait les titres (nouvelles publications)
        articles = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'a']):
            text = tag.get_text(strip=True)
            if len(text) > 10:
                articles.append(text[:100])
        
        return articles[:10]  # Top 10 articles
    except Exception as e:
        return [f"Erreur: {str(e)}"]

# Fonction pour envoyer un email
def send_email(subject, body, recipient):
    try:
        sender_email = os.getenv("EMAIL_USER")
        sender_password = os.getenv("EMAIL_PASSWORD")
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        print(f"✓ Email envoyé à {recipient}")
        return True
    except Exception as e:
        print(f"✗ Erreur email: {str(e)}")
        return False

# Fonction principale
def monitor():
    print(f"[{datetime.now()}] Vérification des sites...")
    
    results = {}
    new_content = False
    email_body = "<h2>📰 Rapport de Monitoring - " + datetime.now().strftime("%d/%m/%Y %H:%M") + "</h2><br>"
    
    for site_name, url in SITES.items():
        print(f"\n→ Vérification {site_name}...")
        content = get_site_content(url)
        results[site_name] = content
        
        if content and content[0] != "Erreur":
            new_content = True
            email_body += f"<h3>🔵 {site_name}</h3>"
            email_body += f"<p><strong>URL:</strong> <a href='{url}'>{url}</a></p>"
            email_body += "<ul>"
            for item in content[:5]:
                email_body += f"<li>{item}</li>"
            email_body += "</ul><br>"
            print(f"   ✓ {len(content)} éléments trouvés")
        else:
            email_body += f"<h3>❌ {site_name}</h3><p>Impossible d'accéder au site</p><br>"
    
    # Envoyer email si nouveau contenu
    if new_content:
        recipient = os.getenv("EMAIL_RECIPIENT")
        send_email("🔔 Nouvelle Publication Détectée", email_body, recipient)
    else:
        print("\n✓ Pas de nouveau contenu détecté")
    
    return results

if __name__ == "__main__":
    monitor()
