#!/usr/bin/env python3
"""
SEO Tracker - Suivi de positions de mots-clés
Compatible avec Appl'IA / projet indépendant
"""

import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

app = Flask(__name__)
app.secret_key = "seo-tracker-secret-change-me"  # changez en production

DB_PATH = "database.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            position INTEGER,
            date TEXT NOT NULL,
            url TEXT,
            notes TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE NOT NULL,
            target_url TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE INDEX IF NOT EXISTS idx_rankings_keyword_date
        ON rankings(keyword, date)
    """)
    conn.commit()
    conn.close()


def save_position(keyword: str, position: int, url: str = None, notes: str = None):
    """Enregistre une position pour un mot-clé (date du jour)."""
    conn = get_db()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")

    # Évite les doublons le même jour
    c.execute(
        "SELECT id FROM rankings WHERE keyword=? AND date=?",
        (keyword, today)
    )
    existing = c.fetchone()
    if existing:
        c.execute(
            "UPDATE rankings SET position=?, url=?, notes=? WHERE id=?",
            (position, url, notes, existing["id"])
        )
    else:
        c.execute(
            "INSERT INTO rankings(keyword, position, date, url, notes) VALUES(?,?,?,?,?)",
            (keyword, position, today, url, notes)
        )
    conn.commit()
    conn.close()


def get_history(keyword: str, days: int = 90):
    """Retourne l'historique (date, position) d'un mot-clé."""
    conn = get_db()
    c = conn.cursor()
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    c.execute(
        """
        SELECT date, position, url
        FROM rankings
        WHERE keyword=? AND date >= ?
        ORDER BY date ASC
        """,
        (keyword, since)
    )
    rows = c.fetchall()
    conn.close()
    return rows


def get_latest_positions():
    """Dernière position connue pour chaque mot-clé suivi."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT r.keyword, r.position, r.date, r.url,
               (SELECT position FROM rankings r2
                WHERE r2.keyword = r.keyword
                  AND r2.date < r.date
                ORDER BY r2.date DESC LIMIT 1) AS previous_position
        FROM rankings r
        INNER JOIN (
            SELECT keyword, MAX(date) AS max_date
            FROM rankings
            GROUP BY keyword
        ) latest ON r.keyword = latest.keyword AND r.date = latest.max_date
        ORDER BY r.keyword
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def get_alerts(threshold: int = 3):
    """
    Alertes de hausse / baisse significative.
    Hausse = position qui diminue (meilleure place).
    """
    alerts = []
    for row in get_latest_positions():
        prev = row["previous_position"]
        curr = row["position"]
        if prev is None or curr is None:
            continue
        delta = prev - curr  # positif = amélioration
        if abs(delta) >= threshold:
            alerts.append({
                "keyword": row["keyword"],
                "previous": prev,
                "current": curr,
                "delta": delta,
                "type": "up" if delta > 0 else "down",
                "date": row["date"]
            })
    return alerts


def add_keyword(keyword: str, target_url: str = None):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO keywords(keyword, target_url, created_at) VALUES(?,?,?)",
            (keyword.strip().lower(), target_url, datetime.now().isoformat())
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def list_keywords():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM keywords WHERE active=1 ORDER BY keyword")
    rows = c.fetchall()
    conn.close()
    return rows


# ---------- Routes ----------

@app.route("/")
def dashboard():
    latest = get_latest_positions()
    alerts = get_alerts(threshold=2)
    keywords = list_keywords()
    return render_template(
        "index.html",
        latest=latest,
        alerts=alerts,
        keywords=keywords
    )


@app.route("/keyword/<path:keyword>")
def keyword_detail(keyword):
    history = get_history(keyword)
    return render_template("keyword.html", keyword=keyword, history=history)


@app.route("/add-position", methods=["POST"])
def add_position():
    keyword = request.form.get("keyword", "").strip()
    position = request.form.get("position")
    url = request.form.get("url", "").strip() or None
    notes = request.form.get("notes", "").strip() or None

    if not keyword or not position:
        flash("Mot-clé et position obligatoires.", "error")
        return redirect(url_for("dashboard"))

    try:
        pos = int(position)
        if pos < 1 or pos > 100:
            raise ValueError
    except ValueError:
        flash("Position invalide (1-100).", "error")
        return redirect(url_for("dashboard"))

    save_position(keyword, pos, url, notes)
    # Ajoute aussi le mot-clé s'il n'existe pas
    add_keyword(keyword, url)
    flash(f"Position enregistrée : « {keyword} » → {pos}", "success")
    return redirect(url_for("dashboard"))


@app.route("/add-keyword", methods=["POST"])
def add_keyword_route():
    keyword = request.form.get("keyword", "").strip()
    target_url = request.form.get("target_url", "").strip() or None
    if not keyword:
        flash("Mot-clé obligatoire.", "error")
        return redirect(url_for("dashboard"))
    if add_keyword(keyword, target_url):
        flash(f"Mot-clé « {keyword} » ajouté.", "success")
    else:
        flash(f"« {keyword} » existe déjà.", "error")
    return redirect(url_for("dashboard"))


@app.route("/api/history/<path:keyword>")
def api_history(keyword):
    days = request.args.get("days", 90, type=int)
    history = get_history(keyword, days)
    return jsonify([
        {"date": r["date"], "position": r["position"], "url": r["url"]}
        for r in history
    ])


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Base de données initialisée.")


@app.cli.command("sync-gsc")
def sync_gsc_command():
    """
    Synchronise les positions depuis Google Search Console.
    Variables d'environnement :
      GSC_SITE_URL          (obligatoire)  ex: https://appl-ia.fr/  ou  sc-domain:appl-ia.fr
      GSC_CREDENTIALS       (optionnel)    chemin vers credentials.json (service account)
      GSC_CLIENT_SECRETS    (optionnel)    chemin vers client_secrets.json (OAuth)
      GSC_DAYS              (optionnel)    nombre de jours (défaut 7)
      GSC_MIN_IMPRESSIONS   (optionnel)    seuil d'impressions (défaut 5)
    """
    import os
    from gsc_client import GSCClient, sync_to_tracker

    site_url = os.environ.get("GSC_SITE_URL")
    if not site_url:
        print("Erreur : définissez GSC_SITE_URL (ex: https://appl-ia.fr/)")
        return

    creds_path = os.environ.get("GSC_CREDENTIALS", "credentials.json")
    client_secrets = os.environ.get("GSC_CLIENT_SECRETS", "client_secrets.json")
    days = int(os.environ.get("GSC_DAYS", "7"))
    min_impr = int(os.environ.get("GSC_MIN_IMPRESSIONS", "5"))

    try:
        if os.path.isfile(creds_path):
            print(f"Auth Service Account : {creds_path}")
            client = GSCClient.from_service_account(creds_path)
        else:
            print(f"Auth OAuth : {client_secrets}")
            client = GSCClient.from_oauth(client_secrets)
    except Exception as e:
        print(f"Erreur d'authentification : {e}")
        return

    print(f"Sites accessibles : {client.list_sites()}")
    print(f"Sync {site_url} (derniers {days} jours, min {min_impr} impressions)…")

    try:
        n = sync_to_tracker(
            client,
            site_url=site_url,
            days=days,
            min_impressions=min_impr,
        )
        print(f"✅ {n} positions enregistrées.")
    except Exception as e:
        print(f"Erreur sync : {e}")


if __name__ == "__main__":
    init_db()
    # Quelques données de démo si la base est vide
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM rankings").fetchone()[0] == 0:
        demo = [
            ("appl ia", 12),
            ("appl ia", 9),
            ("appl ia", 7),
            ("collegi hein", 28),
            ("collegi hein", 22),
            ("collegi hein", 18),
            ("appl-ia.fr", 4),
            ("appl-ia.fr", 3),
        ]
        # on simule des dates
        base = datetime.now() - timedelta(days=len(demo))
        for i, (kw, pos) in enumerate(demo):
            d = (base + timedelta(days=i)).strftime("%Y-%m-%d")
            conn.execute(
                "INSERT INTO rankings(keyword, position, date) VALUES(?,?,?)",
                (kw, pos, d)
            )
            add_keyword(kw)
        conn.commit()
        print("Données de démonstration ajoutées.")
    conn.close()

    app.run(debug=True, host="0.0.0.0", port=5000)
