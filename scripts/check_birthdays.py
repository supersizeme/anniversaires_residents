"""
Script de vérification des anniversaires des résidents.
Lit la base de données Notion, vérifie si c'est l'anniversaire d'un résident aujourd'hui,
et envoie un email de rappel via l'API Resend.

Variables d'environnement requises (GitHub Secrets):
  RESEND_API_KEY      : Clé API Resend (ex: re_xxxxxxxxxx)
  NOTION_TOKEN        : Token d'intégration Notion (ex: secret_xxxxxxxxxx)
  NOTION_DATABASE_ID  : ID de la base de données Notion (ex: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
"""

import os
import sys
import json
import requests
from datetime import date, datetime

# ── Configuration ──────────────────────────────────────────────────────────────

RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
NOTION_TOKEN       = os.environ.get("NOTION_TOKEN", "")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "")

RECIPIENT_EMAIL    = "xavier.doutrelepont@croix-rouge.be"
SENDER_EMAIL       = "anniversaires@resend.dev"   # Domaine sandbox Resend (gratuit, sans config DNS)
SENDER_NAME        = "Rappel Anniversaires Résidents"

NOTION_API_VERSION = "2022-06-28"

# ── Notion ─────────────────────────────────────────────────────────────────────

def get_residents_from_notion():
    """Récupère tous les résidents depuis la base de données Notion."""
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }

    residents = []
    has_more = True
    next_cursor = None

    while has_more:
        body = {"page_size": 100}
        if next_cursor:
            body["start_cursor"] = next_cursor

        response = requests.post(url, headers=headers, json=body, timeout=30)

        if response.status_code != 200:
            print(f"Erreur Notion ({response.status_code}): {response.text}")
            sys.exit(1)

        data = response.json()
        has_more = data.get("has_more", False)
        next_cursor = data.get("next_cursor")

        for page in data.get("results", []):
            props = page.get("properties", {})

            # Prénom (Title)
            prenom_list = props.get("Prénom", {}).get("title", [])
            prenom = prenom_list[0]["plain_text"] if prenom_list else ""

            # Nom (Text)
            nom_list = props.get("Nom", {}).get("rich_text", [])
            nom = nom_list[0]["plain_text"] if nom_list else ""

            # Date de l'anniversaire (Date)
            date_prop = props.get("Date de l'anniversaire", {}).get("date")
            if not date_prop or not date_prop.get("start"):
                continue  # Ignorer les résidents sans date d'anniversaire

            date_naissance_str = date_prop["start"]  # Format: YYYY-MM-DD

            try:
                date_naissance = date.fromisoformat(date_naissance_str)
            except ValueError:
                print(f"Date invalide pour {prenom} {nom}: {date_naissance_str}")
                continue

            residents.append({
                "prenom": prenom,
                "nom": nom,
                "date_naissance": date_naissance,
            })

    return residents


def find_birthday_residents(residents, today=None):
    """Retourne les résidents dont c'est l'anniversaire aujourd'hui."""
    if today is None:
        today = date.today()

    birthday_residents = []
    for r in residents:
        if r["date_naissance"].month == today.month and r["date_naissance"].day == today.day:
            age = today.year - r["date_naissance"].year
            birthday_residents.append({**r, "age": age})

    return birthday_residents


# ── Email ──────────────────────────────────────────────────────────────────────

def build_email_html(residents, today):
    """Construit le contenu HTML de l'email de rappel."""
    today_str = today.strftime("%d/%m/%Y")
    noms_complets = [f"<strong>{r['prenom']} {r['nom']}</strong> ({r['age']} ans)" for r in residents]

    if len(residents) == 1:
        intro = f"Aujourd'hui, le {today_str}, c'est l'anniversaire d'un(e) de vos résident(e)s&nbsp;:"
    else:
        intro = f"Aujourd'hui, le {today_str}, c'est l'anniversaire de plusieurs de vos résident(e)s&nbsp;:"

    liste_html = "<ul>" + "".join(f"<li>{nom}</li>" for nom in noms_complets) + "</ul>"

    return f"""
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; color: #222; background: #f9f9f9; padding: 20px; }}
    .card {{ background: #fff; border-radius: 8px; padding: 30px 40px; max-width: 550px; margin: auto;
             border-top: 5px solid #E52020; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    h1 {{ color: #E52020; font-size: 22px; margin-top: 0; }}
    ul {{ padding-left: 20px; line-height: 1.8; }}
    .footer {{ font-size: 12px; color: #888; margin-top: 24px; border-top: 1px solid #eee; padding-top: 12px; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>🎂 Rappel Anniversaire</h1>
    <p>{intro}</p>
    {liste_html}
    <p>N'oubliez pas de leur souhaiter un joyeux anniversaire !</p>
    <div class="footer">
      Ce message est envoyé automatiquement par le système de rappel d'anniversaires des résidents.<br>
      Croix-Rouge de Belgique
    </div>
  </div>
</body>
</html>
"""


def build_email_text(residents, today):
    """Construit la version texte brut de l'email."""
    today_str = today.strftime("%d/%m/%Y")
    lignes = [f"- {r['prenom']} {r['nom']} ({r['age']} ans)" for r in residents]
    noms_str = "\n".join(lignes)

    return (
        f"Rappel Anniversaire — {today_str}\n\n"
        f"Aujourd'hui, c'est l'anniversaire de :\n{noms_str}\n\n"
        f"N'oubliez pas de leur souhaiter un joyeux anniversaire !\n\n"
        f"-- Système de rappel d'anniversaires des résidents, Croix-Rouge de Belgique"
    )


def send_birthday_email(residents, today):
    """Envoie l'email de rappel via l'API Resend."""
    if len(residents) == 1:
        subject = f"🎂 Anniversaire de {residents[0]['prenom']} {residents[0]['nom']} aujourd'hui !"
    else:
        prenoms = ", ".join(r["prenom"] for r in residents)
        subject = f"🎂 Anniversaires aujourd'hui : {prenoms}"

    payload = {
        "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
        "to": [RECIPIENT_EMAIL],
        "subject": subject,
        "html": build_email_html(residents, today),
        "text": build_email_text(residents, today),
    }

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if response.status_code in (200, 201):
        print(f"Email envoyé avec succès à {RECIPIENT_EMAIL} (id: {response.json().get('id')})")
    else:
        print(f"Erreur envoi email ({response.status_code}): {response.text}")
        sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    today = date.today()
    print(f"Vérification des anniversaires pour le {today.strftime('%d/%m/%Y')}...")

    # Validation des variables d'environnement
    missing = [v for v in ["RESEND_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID"] if not os.environ.get(v)]
    if missing:
        print(f"Erreur : variables d'environnement manquantes : {', '.join(missing)}")
        sys.exit(1)

    # Lecture des résidents depuis Notion
    residents = get_residents_from_notion()
    print(f"{len(residents)} résident(s) trouvé(s) dans Notion.")

    # Recherche des anniversaires du jour
    birthday_residents = find_birthday_residents(residents, today)

    if not birthday_residents:
        print("Aucun anniversaire aujourd'hui. Aucun email envoyé.")
        return

    print(f"{len(birthday_residents)} anniversaire(s) aujourd'hui :")
    for r in birthday_residents:
        print(f"  - {r['prenom']} {r['nom']} ({r['age']} ans)")

    # Envoi de l'email
    send_birthday_email(birthday_residents, today)


if __name__ == "__main__":
    main()
