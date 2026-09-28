# SEO Tracker – Référencement Google

Outil de suivi SEO (positions de mots-clés, historique, alertes, tableau de bord).

Compatible avec **Appl'IA**, **Collégi'hein ?** et [appl-ia.fr](https://appl-ia.fr).

## Fonctionnalités

- Surveillance de mots-clés
- Historique des positions (SQLite)
- Évolution quotidienne
- Alertes de hausse / baisse (seuil configurable)
- Tableau de bord clair + graphique par mot-clé
- Ajout manuel de positions (idéal en attendant l’API Search Console)

## Structure

```
Google/
│
├── app.py
├── database.db          # créé automatiquement
├── templates/
│   ├── index.html
│   └── keyword.html
├── static/
│   └── style.css
├── requirements.txt
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

## Utilisation

1. **Ajouter un mot-clé** à suivre (optionnel, se fait aussi automatiquement).
2. **Enregistrer une position** manuellement (mot-clé + position 1-100).
3. Consulter le **tableau de bord** et les **alertes**.
4. Cliquer sur un mot-clé pour voir l’**historique + graphique**.

## Passage pro : Google Search Console API

Le scraping Google est interdit et fragile.  
Pour un usage sérieux :

1. Créez un projet Google Cloud + activez l’API Search Console.
2. Créez un compte de service (ou OAuth) et liez-le à votre propriété Search Console.
3. Utilisez la bibliothèque `google-api-python-client` pour récupérer les performances par requête.
4. Remplacez l’ajout manuel par un job planifié (cron / Celery / APScheduler) qui appelle l’API et enregistre les positions via `save_position()`.

Exemple de flux cible :

```
Google Search Console API
        ↓
  Collecte quotidienne
        ↓
     SQLite
        ↓
  Tableau de bord Flask + alertes
```

## Notes

- La base est purement locale (fichier `database.db`).
- Changez `app.secret_key` en production.
- Pour déployer : Gunicorn + reverse proxy (nginx) ou un PaaS (Render, Railway, etc.).

Bon suivi SEO !
