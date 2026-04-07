# Rappel d'anniversaire des résidents

Application de rappel automatique des anniversaires des résidents du centre Croix-Rouge.

Chaque matin, un email est envoyé automatiquement à **xavier.doutrelepont@croix-rouge.be** si c'est l'anniversaire d'un ou plusieurs résidents.

---

## Comment ça fonctionne

```
Notion (liste des résidents)
       ↓  chaque matin à 8h
GitHub Actions (vérification automatique)
       ↓  si anniversaire aujourd'hui
Resend (envoi de l'email)
       ↓
xavier.doutrelepont@croix-rouge.be
```

---

## Configuration initiale (à faire une seule fois)

### Étape 1 — Créer un compte Resend (envoi d'emails gratuit)

1. Aller sur [resend.com](https://resend.com) et créer un compte gratuit
2. Dans le tableau de bord, aller dans **API Keys** → **Create API Key**
3. Copier la clé (commence par `re_...`)

### Étape 2 — Configurer Notion

1. Aller sur [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Cliquer **New integration** → donner un nom (ex: "Rappel Anniversaires") → **Submit**
3. Copier le **Internal Integration Token** (commence par `secret_...`)
4. Ouvrir votre base de données Notion des résidents
5. Cliquer sur **...** (menu 3 points) en haut à droite → **Add connections** → choisir votre intégration
6. Copier l'**ID de la base de données** depuis l'URL de la page Notion :
   ```
   https://www.notion.so/votreworkspace/XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX?v=...
                                        ↑ c'est l'ID de la base de données
   ```

### Étape 3 — Ajouter les secrets dans GitHub

1. Aller sur votre dépôt GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Cliquer **New repository secret** et ajouter les 3 secrets suivants :

| Nom du secret        | Valeur                                      |
|----------------------|---------------------------------------------|
| `RESEND_API_KEY`     | Votre clé API Resend (`re_...`)             |
| `NOTION_TOKEN`       | Votre token Notion (`secret_...`)           |
| `NOTION_DATABASE_ID` | L'ID de votre base de données Notion        |

---

## Structure de la base de données Notion

Votre base de données Notion doit avoir exactement ces colonnes :

| Colonne              | Type dans Notion | Exemple              |
|----------------------|------------------|----------------------|
| **Prénom**           | Title            | Ali                  |
| **Nom**              | Text             | Hassan               |
| **Date de naissance**| Date             | 1995-04-07           |

---

## Tester manuellement

1. Aller sur votre dépôt GitHub → onglet **Actions**
2. Cliquer sur **Vérification quotidienne des anniversaires**
3. Cliquer **Run workflow** → **Run workflow**
4. Vérifier les logs et la réception de l'email

---

## Exécution automatique

Le script s'exécute automatiquement tous les jours à **8h du matin** (heure de Bruxelles, heure d'hiver).

> En heure d'été (avril–octobre), il s'exécutera à 9h. Pour ajuster, modifier le cron dans `.github/workflows/check_birthdays.yml` : remplacer `0 7 * * *` par `0 6 * * *`.

---

## Structure des fichiers

```
anniversaires_residents/
├── .github/
│   └── workflows/
│       └── check_birthdays.yml   # Planificateur GitHub Actions
├── scripts/
│   └── check_birthdays.py        # Script principal
├── requirements.txt
└── README.md
```
