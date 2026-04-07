"""
Script de vérification des anniversaires des résidents.
Lit la base de données Notion, vérifie si c'est l'anniversaire d'un résident aujourd'hui,
et envoie un email de rappel via l'API Resend.

Variables d'environnement requises (GitHub Secrets):
  RESEND_API_KEY      : Clé API Resend (ex: re_xxxxxxxxxx)
  NOTION_TOKEN        : Token d'intégration Notion (ex: ntn_xxxxxxxxxx)
  NOTION_DATABASE_ID  : ID de la base de données Notion (ex: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx)
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

RECIPIENT_EMAIL    = "xavier.doutrelepont@gmail.com"
SENDER_EMAIL       = "onboarding@resend.dev"   # Adresse sandbox Resend (gratuit, sans config DNS)
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


def find_upcoming_birthdays(residents, today=None, days=7):
    """Retourne les résidents dont l'anniversaire tombe dans les 'days' prochains jours."""
    if today is None:
        today = date.today()

    upcoming = []
    for r in residents:
        dn = r["date_naissance"]
        # Date anniversaire cette année
        try:
            birthday_this_year = dn.replace(year=today.year)
        except ValueError:
            # 29 février en année non bissextile
            birthday_this_year = dn.replace(year=today.year, day=28)

        # Si déjà passé cette année, regarder l'année prochaine
        if birthday_this_year < today:
            try:
                birthday_this_year = dn.replace(year=today.year + 1)
            except ValueError:
                birthday_this_year = dn.replace(year=today.year + 1, day=28)

        delta = (birthday_this_year - today).days
        if 0 <= delta < days:
            age = birthday_this_year.year - dn.year
            upcoming.append({**r, "age": age, "date_anniversaire": birthday_this_year, "dans_jours": delta})

    # Trier par ordre chronologique
    upcoming.sort(key=lambda x: x["date_anniversaire"])
    return upcoming


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


def build_weekly_html(upcoming, today):
    """Construit le HTML du résumé hebdomadaire."""
    week_end = today + __import__('datetime').timedelta(days=6)
    periode = f"du {today.strftime('%d/%m/%Y')} au {week_end.strftime('%d/%m/%Y')}"

    if not upcoming:
        contenu = "<p>Aucun anniversaire cette semaine. Bonne semaine !</p>"
    else:
        lignes = ""
        for r in upcoming:
            jour_label = "Aujourd'hui" if r["dans_jours"] == 0 else (
                "Demain" if r["dans_jours"] == 1 else r["date_anniversaire"].strftime("%A %d/%m").capitalize()
            )
            lignes += (
                f"<tr>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee'><strong>{r['prenom']} {r['nom']}</strong></td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee'>{r['date_anniversaire'].strftime('%d/%m/%Y')}</td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee'>{r['age']} ans</td>"
                f"<td style='padding:8px 12px;border-bottom:1px solid #eee;color:#E52020'>{jour_label}</td>"
                f"</tr>"
            )
        contenu = f"""
        <table style='width:100%;border-collapse:collapse;font-size:14px'>
          <thead>
            <tr style='background:#f5f5f5'>
              <th style='padding:8px 12px;text-align:left'>Résident(e)</th>
              <th style='padding:8px 12px;text-align:left'>Date</th>
              <th style='padding:8px 12px;text-align:left'>Âge</th>
              <th style='padding:8px 12px;text-align:left'>Quand</th>
            </tr>
          </thead>
          <tbody>{lignes}</tbody>
        </table>"""

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; color: #222; background: #f9f9f9; padding: 20px; }}
    .card {{ background: #fff; border-radius: 8px; padding: 30px 40px; max-width: 600px; margin: auto;
             border-top: 5px solid #E52020; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    h1 {{ color: #E52020; font-size: 22px; margin-top: 0; }}
    .footer {{ font-size: 12px; color: #888; margin-top: 24px; border-top: 1px solid #eee; padding-top: 12px; }}
  </style>
</head>
<body><div class="card">
  <h1>📅 Anniversaires de la semaine</h1>
  <p style="color:#666">{periode}</p>
  {contenu}
  <div class="footer">Ce message est envoyé automatiquement chaque lundi.<br>Croix-Rouge de Belgique</div>
</div></body></html>"""


def send_weekly_email(upcoming, today):
    """Envoie le résumé hebdomadaire via l'API Resend."""
    week_end = today + __import__('datetime').timedelta(days=6)
    subject = f"📅 Anniversaires du {today.strftime('%d/%m')} au {week_end.strftime('%d/%m/%Y')}"

    if upcoming:
        noms = ", ".join(f"{r['prenom']} {r['nom']}" for r in upcoming)
        text_body = f"Anniversaires cette semaine :\n" + "\n".join(
            f"- {r['prenom']} {r['nom']} : {r['date_anniversaire'].strftime('%d/%m/%Y')} ({r['age']} ans)"
            for r in upcoming
        )
    else:
        text_body = "Aucun anniversaire cette semaine."

    payload = {
        "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
        "to": [RECIPIENT_EMAIL],
        "subject": subject,
        "html": build_weekly_html(upcoming, today),
        "text": text_body,
    }

    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )

    if response.status_code in (200, 201):
        print(f"Résumé hebdomadaire envoyé à {RECIPIENT_EMAIL} (id: {response.json().get('id')})")
    else:
        print(f"Erreur envoi email ({response.status_code}): {response.text}")
        sys.exit(1)


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
    weekly_mode = os.environ.get("WEEKLY_SUMMARY", "").lower() == "true"

    print(f"Mode : {'résumé hebdomadaire' if weekly_mode else 'vérification quotidienne'}")
    print(f"Date : {today.strftime('%d/%m/%Y')}")

    # Validation des variables d'environnement
    missing = [v for v in ["RESEND_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID"] if not os.environ.get(v)]
    if missing:
        print(f"Erreur : variables d'environnement manquantes : {', '.join(missing)}")
        sys.exit(1)

    # Lecture des résidents depuis Notion
    residents = get_residents_from_notion()
    print(f"{len(residents)} résident(s) trouvé(s) dans Notion.")

    if weekly_mode:
        upcoming = find_upcoming_birthdays(residents, today, days=7)
        print(f"{len(upcoming)} anniversaire(s) dans les 7 prochains jours.")
        for r in upcoming:
            print(f"  - {r['prenom']} {r['nom']} : {r['date_anniversaire'].strftime('%d/%m/%Y')} ({r['age']} ans)")
        send_weekly_email(upcoming, today)
    else:
        birthday_residents = find_birthday_residents(residents, today)
        if not birthday_residents:
            print("Aucun anniversaire aujourd'hui. Aucun email envoyé.")
            return
        print(f"{len(birthday_residents)} anniversaire(s) aujourd'hui :")
        for r in birthday_residents:
            print(f"  - {r['prenom']} {r['nom']} ({r['age']} ans)")
        send_birthday_email(birthday_residents, today)


if __name__ == "__main__":
    main()
