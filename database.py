"""
database.py
------------
Gestion de la base de données de l'application de gestion d'hôtel.
SQLite en local, PostgreSQL via DATABASE_URL en production.
"""

import os
import secrets
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "hotel.db"


def _database_url():
    return os.environ.get("DATABASE_URL", "").strip()


class _PgConnection:
    def __init__(self, conn):
        self._conn = conn

    def _cursor(self):
        from psycopg2.extras import RealDictCursor

        return self._conn.cursor(cursor_factory=RealDictCursor)

    def execute(self, sql, params=()):
        cursor = self._cursor()
        cursor.execute(sql.replace("?", "%s"), params)
        return cursor

    def executemany(self, sql, seq_of_params):
        cursor = self._cursor()
        cursor.executemany(sql.replace("?", "%s"), seq_of_params)
        return cursor

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def get_db():
    url = _database_url()
    if url:
        import psycopg2

        return _PgConnection(psycopg2.connect(url))
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _build_schema(pk, numeric):
    return f"""
CREATE TABLE IF NOT EXISTS utilisateur (
    id_utilisateur {pk},
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client (
    id_client   {pk},
    nom         TEXT NOT NULL,
    prenom      TEXT NOT NULL,
    email       TEXT NOT NULL,
    telephone   TEXT,
    cin         TEXT,
    archivee    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chambre (
    id_chambre  {pk},
    numero      TEXT UNIQUE NOT NULL,
    type        TEXT NOT NULL,
    prix_nuit   {numeric} NOT NULL,
    capacite    INTEGER NOT NULL,
    statut      TEXT NOT NULL DEFAULT 'libre'
);

CREATE TABLE IF NOT EXISTS reservation (
    id_reservation {pk},
    client_id      INTEGER NOT NULL,
    chambre_id     INTEGER NOT NULL,
    date_debut     TEXT NOT NULL,
    date_fin       TEXT NOT NULL,
    nb_nuits       INTEGER NOT NULL,
    montant_total  {numeric} NOT NULL,
    statut         TEXT NOT NULL DEFAULT 'confirmee',
    archivee       INTEGER NOT NULL DEFAULT 0,
    paye           INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (client_id)  REFERENCES client (id_client)  ON DELETE CASCADE,
    FOREIGN KEY (chambre_id) REFERENCES chambre (id_chambre) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS paiement (
    id_paiement   {pk},
    reservation_id INTEGER NOT NULL,
    montant       {numeric} NOT NULL,
    date_paiement TEXT NOT NULL,
    mode          TEXT NOT NULL DEFAULT 'especes',
    archivee      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (reservation_id) REFERENCES reservation (id_reservation) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS demande_reservation (
    id_demande       {pk},
    public_token     TEXT NOT NULL,
    guest_name       TEXT NOT NULL,
    email            TEXT NOT NULL,
    phone            TEXT NOT NULL,
    room_type        TEXT NOT NULL,
    check_in         TEXT NOT NULL,
    check_out        TEXT NOT NULL,
    guests_count     INTEGER NOT NULL DEFAULT 2,
    special_requests TEXT,
    status           TEXT NOT NULL DEFAULT 'En attente',
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_demande_token ON demande_reservation(public_token);
"""


SCHEMA_SQLITE = _build_schema("INTEGER PRIMARY KEY AUTOINCREMENT", "REAL")
SCHEMA_PG = _build_schema("SERIAL PRIMARY KEY", "NUMERIC(12,2)")


def init_db():
    url = _database_url()
    sqlite_first_run = not url and not DB_PATH.exists()
    conn = get_db()

    if url:
        for statement in SCHEMA_PG.strip().split(";"):
            if statement.strip():
                conn.execute(statement)
        conn.commit()
        first_run = conn.execute("SELECT COUNT(*) AS n FROM utilisateur").fetchone()["n"] == 0
    else:
        conn.executescript(SCHEMA_SQLITE)
        first_run = sqlite_first_run

    for table, colonne in (("client", "archivee"),
                           ("reservation", "archivee"),
                           ("reservation", "paye")):
        try:
            conn.execute(f"SELECT {colonne} FROM {table} LIMIT 1")
        except Exception:
            conn.rollback()
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} INTEGER NOT NULL DEFAULT 0")
            conn.commit()

    if first_run:
        admin_user = os.environ.get("ADMIN_USERNAME", "admin")
        admin_pass = os.environ.get("ADMIN_PASSWORD")
        if not admin_pass:
            admin_pass = secrets.token_urlsafe(12)
            print(f"[init] Mot de passe administrateur généré : {admin_pass}")
        conn.execute(
            "INSERT INTO utilisateur (username, password_hash) VALUES (?, ?)",
            (admin_user, generate_password_hash(admin_pass)),
        )
        chambres_demo = [
            ("101", "Simple", 30000, 1, "libre"),
            ("102", "Premium", 50000, 2, "libre"),
            ("201", "VIP", 90000, 4, "libre"),
        ]
        conn.executemany(
            "INSERT INTO chambre (numero, type, prix_nuit, capacite, statut) VALUES (?,?,?,?,?)",
            chambres_demo,
        )
        conn.commit()

    conn.close()
