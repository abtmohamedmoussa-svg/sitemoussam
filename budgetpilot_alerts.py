"""
Relais Telegram pour les alertes BudgetPilot.

BudgetPilot est une app locale sans serveur : elle ne peut pas notifier
"en temps reel" quand elle est fermee. A la place, un bouton manuel dans
BudgetPilot (Parametres > Rappels Telegram) pousse ici un export minimal
de ses alertes ACTIVES (budgetpilot-alerts.json) via l'API GitHub Contents.

Ce script tourne sur un planning (voir budgetpilot-alerts.yml) et relaie
vers Telegram les alertes pas encore notifiees, en gardant un etat local
(budgetpilot-notified.json) pour ne jamais renvoyer deux fois la meme.

Limite assumee : ceci relit un instantane pousse manuellement depuis
BudgetPilot, pas une connexion live a une banque. Un rappel porte donc sur
des alertes deja actives au moment de la derniere synchro, jamais sur un
evenement survenu depuis.
"""

import os
import json
import requests
from datetime import datetime, timezone

ALERTS_FILE = "budgetpilot-alerts.json"
STATE_FILE = "budgetpilot-notified.json"
STALE_HOURS = 24  # au-dela de ce delai depuis la derniere synchro, on le signale dans le message

SEVERITY_EMOJI = {"critical": "\U0001F534", "warning": "\U0001F7E0", "info": "\U0001F535"}


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_telegram(message):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        print("Telegram non configure (BOT_TOKEN ou CHAT_ID absent)")
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(
            url,
            data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=15,
        )
        print("Alerte BudgetPilot envoyee sur Telegram")
    except Exception as e:
        print(f"Envoi Telegram KO (non bloquant): {e}")


def stale_warning(synced_at):
    if not synced_at:
        return ""
    try:
        synced_dt = datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
    except ValueError:
        return ""
    age_hours = (datetime.now(timezone.utc) - synced_dt).total_seconds() / 3600
    if age_hours > STALE_HOURS:
        return f"\n\n⚠️ Derniere synchro BudgetPilot il y a {age_hours:.0f}h — pensez a resynchroniser."
    return ""


def main():
    payload = load_json(ALERTS_FILE, None)
    if payload is None:
        print(f"{ALERTS_FILE} absent — aucune synchronisation BudgetPilot recue pour l'instant.")
        return

    alerts = payload.get("alerts", [])
    note = stale_warning(payload.get("syncedAt"))

    notified = load_json(STATE_FILE, {})
    current_ids = {a["id"] for a in alerts}

    # Une alerte qui n'est plus dans l'export (resolue/ignoree cote app, ou
    # condition disparue) est retiree de l'etat : si elle redevient active
    # plus tard sous le meme id, elle doit pouvoir renotifier.
    notified = {alert_id: sent_at for alert_id, sent_at in notified.items() if alert_id in current_ids}

    new_alerts = [a for a in alerts if a["id"] not in notified and a.get("severity") != "info"]

    for alert in new_alerts:
        emoji = SEVERITY_EMOJI.get(alert.get("severity"), "\U0001F514")
        message = f"{emoji} <b>{alert['title']}</b>\n{alert['message']}{note}"
        send_telegram(message)
        notified[alert["id"]] = datetime.now(timezone.utc).isoformat()

    save_json(STATE_FILE, notified)
    print(f"{len(new_alerts)} nouvelle(s) alerte(s) BudgetPilot notifiee(s), {len(alerts)} active(s) au total.")


if __name__ == "__main__":
    main()
