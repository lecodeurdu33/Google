# SEO Tracker – Référencement Google

Outil de suivi SEO (positions de mots-clés, historique, alertes, tableau de bord).

Compatible avec **Appl'IA**, **Collégi'hein ?** et [appl-ia.fr](https://appl-ia.fr).

## Fonctionnalités

- Surveillance de mots-clés
- Historique des positions (SQLite)
- Évolution quotidienne
- Alertes de hausse / baisse (seuil configurable)
- Tableau de bord clair + graphique par mot-clé
- Ajout manuel de positions
- **Sync automatique via Google Search Console API**

## Structure

```
Google/
├── app.py                 # Flask + CLI (init-db, sync-gsc)
├── gsc_client.py          # Client Search Console (Service Account + OAuth)
├── database.db            # créé automatiquement
├── templates/
│   ├── index.html
│   └── keyword.html
├── static/
│   └── style.css
├── requirements.txt
├── credentials.json       # (à créer) Service Account – ne pas committer
├── client_secrets.json    # (à créer) OAuth – ne pas committer
└── README.md
```

## Installation

```bash
git clone https://github.com/lecodeurdu33/Google.git
cd Google
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Ouvrez http://127.0.0.1:5000

Des données de démo (Appl'IA, Collégi'hein, appl-ia.fr) sont injectées au premier lancement.

## Utilisation manuelle

1. **Ajouter un mot-clé** à suivre
2. **Enregistrer une position** manuellement (mot-clé + position 1-100)
3. Consulter le **tableau de bord** et les **alertes**
4. Cliquer sur un mot-clé pour voir l’**historique + graphique**

## Sync Google Search Console

### 1. Activer l’API

1. [Google Cloud Console](https://console.cloud.google.com/) → créer un projet
2. APIs & Services → Library → **Google Search Console API** → Enable
3. Créer des credentials :

**Option A – Service Account (recommandé pour cron)**
- Credentials → Create credentials → Service account
- Télécharger le JSON → renommer `credentials.json`
- Dans Search Console → Paramètres → Utilisateurs → ajouter l’email du service account (droit « Complet »)

**Option B – OAuth (desktop)**
- Credentials → Create credentials → OAuth client ID → Desktop app
- Télécharger → renommer `client_secrets.json`

### 2. Lancer la synchronisation

```bash
# Service Account
export GSC_SITE_URL="https://appl-ia.fr/"   # ou sc-domain:appl-ia.fr
export GSC_CREDENTIALS="credentials.json"
flask --app app sync-gsc

# OAuth (premier lancement ouvre le navigateur)
export GSC_SITE_URL="https://appl-ia.fr/"
export GSC_CLIENT_SECRETS="client_secrets.json"
flask --app app sync-gsc
```

Options supplémentaires :
```bash
export GSC_DAYS=14
export GSC_MIN_IMPRESSIONS=10
```

### 3. Automatiser (cron)

```bash
# Tous les jours à 6h
0 6 * * * cd /chemin/vers/Google && \
  GSC_SITE_URL="https://appl-ia.fr/" \
  GSC_CREDENTIALS="credentials.json" \
  /chemin/venv/bin/flask --app app sync-gsc >> /var/log/seo-tracker.log 2>&1
```

## Notes

- La base est purement locale (`database.db`)
- Changez `app.secret_key` en production
- Ne committez **jamais** `credentials.json`, `client_secrets.json` ni `token.json`
- Pour déployer : Gunicorn + nginx, ou Render / Railway / Fly.io

Bon suivi SEO !
