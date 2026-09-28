#!/usr/bin/env python3
"""
Client Google Search Console pour le SEO Tracker.
Supporte Service Account (recommandé pour cron) et OAuth (desktop).

Usage rapide :
    from gsc_client import GSCClient
    client = GSCClient.from_service_account("credentials.json")
    rows = client.query_positions(site_url="https://appl-ia.fr/", days=7)
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Optional

# Dépendances Google (installées via requirements.txt)
try:
    from google.oauth2 import service_account
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    raise ImportError(
        "Installez les dépendances Google :\n"
        "  pip install google-api-python-client google-auth google-auth-oauthlib\n"
        f"Erreur originale : {e}"
    ) from e


SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
API_SERVICE = "searchconsole"
API_VERSION = "v1"


class GSCClient:
    """Client léger autour de l'API Search Console (Search Analytics)."""

    def __init__(self, credentials):
        self.credentials = credentials
        self.service = build(API_SERVICE, API_VERSION, credentials=credentials)

    # ------------------------------------------------------------------
    # Constructeurs
    # ------------------------------------------------------------------

    @classmethod
    def from_service_account(cls, json_path: str) -> "GSCClient":
        """Auth via compte de service (idéal pour cron / serveur)."""
        if not os.path.isfile(json_path):
            raise FileNotFoundError(f"Fichier credentials introuvable : {json_path}")
        creds = service_account.Credentials.from_service_account_file(
            json_path, scopes=SCOPES
        )
        return cls(creds)

    @classmethod
    def from_oauth(
        cls,
        client_secrets: str = "client_secrets.json",
        token_path: str = "token.json",
    ) -> "GSCClient":
        """
        Auth OAuth (desktop).
        Au premier lancement un navigateur s'ouvre pour autoriser.
        Le token est ensuite sauvegardé dans token_path.
        """
        creds = None
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.isfile(client_secrets):
                    raise FileNotFoundError(
                        f"Fichier OAuth introuvable : {client_secrets}\n"
                        "Téléchargez-le depuis Google Cloud Console "
                        "(Credentials → OAuth client ID → Desktop)."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets, SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as f:
                f.write(creds.to_json())

        return cls(creds)

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def list_sites(self) -> list[str]:
        """Liste les propriétés (sites) accessibles."""
        try:
            result = self.service.sites().list().execute()
            return [s["siteUrl"] for s in result.get("siteEntry", [])]
        except HttpError as e:
            raise RuntimeError(f"Erreur list_sites : {e}") from e

    def query_positions(
        self,
        site_url: str,
        days: int = 7,
        row_limit: int = 1000,
        start_row: int = 0,
        dimensions: Optional[list[str]] = None,
        search_type: str = "web",
    ) -> list[dict[str, Any]]:
        """
        Récupère les positions moyennes par requête (mot-clé).

        Returns:
            Liste de dicts :
            {
                "keyword": str,
                "position": float,      # position moyenne
                "clicks": int,
                "impressions": int,
                "ctr": float,
            }
        """
        if dimensions is None:
            dimensions = ["query"]

        end = date.today() - timedelta(days=3)  # données GSC souvent en retard de 2-3 j
        start = end - timedelta(days=days - 1)

        request_body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": dimensions,
            "rowLimit": min(row_limit, 25000),
            "startRow": start_row,
            "type": search_type,
        }

        try:
            response = (
                self.service.searchanalytics()
                .query(siteUrl=site_url, body=request_body)
                .execute()
            )
        except HttpError as e:
            raise RuntimeError(f"Erreur query_positions : {e}") from e

        rows = []
        for row in response.get("rows", []):
            keys = row.get("keys", [])
            rows.append(
                {
                    "keyword": keys[0] if keys else "",
                    "position": round(row.get("position", 0), 1),
                    "clicks": int(row.get("clicks", 0)),
                    "impressions": int(row.get("impressions", 0)),
                    "ctr": round(row.get("ctr", 0) * 100, 2),  # en %
                }
            )
        return rows

    def query_all_positions(
        self,
        site_url: str,
        days: int = 7,
        max_rows: int = 5000,
    ) -> list[dict[str, Any]]:
        """Pagination automatique jusqu'à max_rows."""
        all_rows: list[dict[str, Any]] = []
        start_row = 0
        page_size = 1000

        while len(all_rows) < max_rows:
            batch = self.query_positions(
                site_url=site_url,
                days=days,
                row_limit=page_size,
                start_row=start_row,
            )
            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < page_size:
                break
            start_row += page_size

        return all_rows[:max_rows]


def sync_to_tracker(
    client: GSCClient,
    site_url: str,
    days: int = 7,
    min_impressions: int = 5,
    max_keywords: int = 500,
) -> int:
    """
    Récupère les positions GSC et les enregistre dans le SEO Tracker
    via save_position().

    Returns:
        Nombre de positions enregistrées.
    """
    from app import save_position, add_keyword  # import local pour éviter cycle

    rows = client.query_all_positions(site_url=site_url, days=days, max_rows=max_keywords)
    count = 0

    for row in rows:
        if row["impressions"] < min_impressions:
            continue
        keyword = row["keyword"].strip()
        if not keyword:
            continue
        # Position GSC est une moyenne (float) → on prend l'entier le plus proche
        position = max(1, min(100, round(row["position"])))
        save_position(
            keyword=keyword,
            position=position,
            notes=f"GSC • {row['impressions']} impr. • CTR {row['ctr']}%",
        )
        add_keyword(keyword)
        count += 1

    return count
