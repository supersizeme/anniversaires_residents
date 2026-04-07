"""
Script de rappel des échéances de procédure d'asile.
Lit la base "Procédures & RDV Résidents" dans Notion et envoie :
  - Un email J-1 (la veille du RDV) : rappel avant le rendez-vous
  - Un email J+1 (le lendemain du RDV) : invitation à noter le résultat

Variables d'environnement requises (GitHub Secrets) :
  RESEND_API_KEY          : Clé API Resend (ex: re_xxxxxxxxxx)
  NOTION_TOKEN            : Token d'intégration Notion (ex: ntn_xxxxxxxxxx)
  NOTION_PROCEDURES_DB_ID : ID de la base "Procédures & RDV Résidents"
"""

import os
import sys
import requests
from datetime import date, timedelta

# ── Configuration ──────────────────────────────────────────────────────────────

RESEND_API_KEY          = os.environ.get("RESEND_API_KEY", "")
NOTION_TOKEN            = os.environ.get("NOTION_TOKEN", "")
NOTION_PROCEDURES_DB_ID = os.environ.get("NOTION_PROCEDURES_DB_ID", "")

RECIPIENT_EMAIL = "xavier.doutrelepont@gmail.com"
SENDER_EMAIL    = "onboarding@resend.dev"
SENDER_NAME     = "Rappel Procédures Résidents"

NOTION_API_VERSION = "2022-06-28"

TYPE_EMOJI = {
    "CGRA":    "🏛️",
    "Avocat":  "⚖️",
    "CPAS":    "🏢",
    "Médical": "🏥",
    "Divers":  "📌",
}

# ── Notion ─────────────────────────────────────────────────────────────────────

def get_procedures_from_notion():
    """Récupère tous les RDV depuis la base Notion."""
    url = f"https://api.notion.com/v1/databases/{NOTION_PROCEDURES_DB_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }

    procedures = []
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

            # Résident (Title)
            resident_list = props.get("Résident", {}).get("title", [])
            resident = resident_list[0]["plain_text"] if resident_list else ""

            # Type de RDV (Select)
            type_prop = props.get("Type de RDV", {}).get("select")
            type_rdv = type_prop["name"] if type_prop else "Divers"

            # Date du RDV (Date)
            date_prop = props.get("Date du RDV", {}).get("date")
            if not date_prop or not date_prop.get("start"):
                continue

            try:
                date_rdv = date.fromisoformat(date_prop["start"][:10])
            except ValueError:
                continue

            # Notes (Rich Text)
            notes_list = props.get("Notes", {}).get("rich_text", [])
            notes = notes_list[0]["plain_text"] if notes_list else ""

            procedures.append({
                "resident": resident,
                "type_rdv": type_rdv,
                "date_rdv": date_rdv,
                "notes": notes,
            })

    return procedures


# ── Construction des emails ────────────────────────────────────────────────────

def _card_style(color):
    return (
        f"background:#fff;border-radius:8px;padding:20px 28px;margin-bottom:16px;"
        f"border-left:5px solid {color};box-shadow:0 1px 4px rgba(0,0,0,0.07);"
    )

def _build_rdv_card(rdv, color):
    emoji = TYPE_EMOJI.get(rdv["type_rdv"], "📌")
    notes_html = (
        f"<p style='margin:8px 0 0;font-size:13px;color:#555'>"
        f"<em>Notes : {rdv['notes']}</em></p>"
        if rdv["notes"] else ""
    )
    return (
        f"<div style='{_card_style(color)}'>"
        f"<strong style='font-size:15px'>{rdv['resident']}</strong> &nbsp;"
        f"<span style='background:{color};color:#fff;border-radius:4px;"
        f"padding:2px 8px;font-size:12px'>{emoji} {rdv['type_rdv']}</span>"
        f"<p style='margin:6px 0 0;color:#444'>"
        f"📅 {rdv['date_rdv'].strftime('%A %d/%m/%Y').capitalize()}</p>"
        f"{notes_html}"
        f"</div>"
    )

def build_html(rdvs, title, subtitle, color, footer_msg):
    cards = "".join(_build_rdv_card(r, color) for r in rdvs)
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<style>
  body{{font-family:Arial,sans-serif;color:#222;background:#f5f5f5;padding:20px}}
  .wrap{{background:#fff;border-radius:10px;padding:32px 40px;max-width:580px;
         margin:auto;border-top:5px solid {color};box-shadow:0 2px 8px rgba(0,0,0,0.09)}}
  h1{{color:{color};font-size:21px;margin-top:0}}
  .sub{{color:#666;margin:-8px 0 20px;font-size:14px}}
  .footer{{font-size:12px;color:#999;margin-top:24px;border-top:1px solid #eee;padding-top:12px}}
</style>
</head><body><div class="wrap">
  <h1>{title}</h1>
  <p class="sub">{subtitle}</p>
  {cards}
  <p>{footer_msg}</p>
  <div class="footer">Message automatique — Croix-Rouge de Belgique</div>
</div></body></html>"""


# ── Envoi email ────────────────────────────────────────────────────────────────

def send_email(subject, html_body, text_body):
    response = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": f"{SENDER_NAME} <{SENDER_EMAIL}>",
            "to": [RECIPIENT_EMAIL],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        },
        timeout=30,
    )
    if response.status_code in (200, 201):
        print(f"  → Email envoyé (id: {response.json().get('id')})")
    else:
        print(f"  → Erreur envoi ({response.status_code}): {response.text}")
        sys.exit(1)


def send_reminder_j_minus_1(rdvs, tomorrow):
    """Email de rappel la veille du RDV."""
    date_str = tomorrow.strftime("%A %d/%m/%Y").capitalize()
    if len(rdvs) == 1:
        subject = f"⏰ RDV demain — {rdvs[0]['resident']} ({rdvs[0]['type_rdv']})"
    else:
        noms = ", ".join(r["resident"] for r in rdvs)
        subject = f"⏰ {len(rdvs)} RDV demain — {noms}"

    html = build_html(
        rdvs,
        title="⏰ Rappel : RDV demain",
        subtitle=f"Le {date_str}, vous avez {len(rdvs)} rendez-vous prévu(s).",
        color="#E52020",
        footer_msg="Pensez à préparer les documents nécessaires !",
    )
    text = f"RAPPEL — RDV demain ({date_str}) :\n" + "\n".join(
        f"- {r['resident']} ({r['type_rdv']})" + (f" : {r['notes']}" if r["notes"] else "")
        for r in rdvs
    )
    print(f"J-1 : {len(rdvs)} RDV demain ({date_str})")
    send_email(subject, html, text)


def send_followup_j_plus_1(rdvs, yesterday):
    """Email de suivi le lendemain du RDV."""
    date_str = yesterday.strftime("%A %d/%m/%Y").capitalize()
    if len(rdvs) == 1:
        subject = f"📋 Suivi RDV d'hier — {rdvs[0]['resident']} ({rdvs[0]['type_rdv']})"
    else:
        noms = ", ".join(r["resident"] for r in rdvs)
        subject = f"📋 Suivi {len(rdvs)} RDV d'hier — {noms}"

    html = build_html(
        rdvs,
        title="📋 Suivi : RDV d'hier",
        subtitle=f"Le {date_str}, {len(rdvs)} rendez-vous avait/avaient lieu.",
        color="#4A90D9",
        footer_msg="N'oubliez pas de noter le résultat dans Notion !",
    )
    text = f"SUIVI — RDV d'hier ({date_str}) :\n" + "\n".join(
        f"- {r['resident']} ({r['type_rdv']})" for r in rdvs
    ) + "\n\nN'oubliez pas de noter le résultat dans Notion !"
    print(f"J+1 : {len(rdvs)} RDV d'hier ({date_str})")
    send_email(subject, html, text)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    today     = date.today()
    tomorrow  = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)

    print(f"Vérification des procédures pour le {today.strftime('%d/%m/%Y')}...")

    missing = [v for v in ["RESEND_API_KEY", "NOTION_TOKEN", "NOTION_PROCEDURES_DB_ID"]
               if not os.environ.get(v)]
    if missing:
        print(f"Erreur : variables manquantes : {', '.join(missing)}")
        sys.exit(1)

    procedures = get_procedures_from_notion()
    print(f"{len(procedures)} procédure(s) trouvée(s) dans Notion.")

    j_minus_1 = [p for p in procedures if p["date_rdv"] == tomorrow]
    j_plus_1  = [p for p in procedures if p["date_rdv"] == yesterday]

    if not j_minus_1 and not j_plus_1:
        print("Aucun rappel à envoyer aujourd'hui.")
        return

    if j_minus_1:
        send_reminder_j_minus_1(j_minus_1, tomorrow)

    if j_plus_1:
        send_followup_j_plus_1(j_plus_1, yesterday)


if __name__ == "__main__":
    main()
