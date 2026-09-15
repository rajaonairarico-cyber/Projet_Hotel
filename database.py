"""
database.py
------------
Gestion de la base de données SQLite pour l'application de gestion d'hôtel.
Tout est en Python pur (module sqlite3 de la bibliothèque standard) :
aucun serveur MySQL n'est nécessaire, le fichier hotel.db est créé
automatiquement au premier lancement.
"""

import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "hotel.db"


def get_db():
    """Retourne une connexion SQLite avec les lignes accessibles par nom de colonne."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateur (
    id_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS client (
    id_client   INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         TEXT NOT NULL,
    prenom      TEXT NOT NULL,
    email       TEXT NOT NULL,
    telephone   TEXT,
    cin         TEXT,
    archivee    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chambre (
    id_chambre  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero      TEXT UNIQUE NOT NULL,
    type        TEXT NOT NULL,
    prix_nuit   REAL NOT NULL,
    capacite    INTEGER NOT NULL,
    statut      TEXT NOT NULL DEFAULT 'libre'
);

CREATE TABLE IF NOT EXISTS reservation (
    id_reservation INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id      INTEGER NOT NULL,
    chambre_id     INTEGER NOT NULL,
    date_debut     TEXT NOT NULL,
    date_fin       TEXT NOT NULL,
    nb_nuits       INTEGER NOT NULL,
    montant_total  REAL NOT NULL,
    statut         TEXT NOT NULL DEFAULT 'confirmee',
    archivee       INTEGER NOT NULL DEFAULT 0,
    paye           INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (client_id)  REFERENCES client (id_client)  ON DELETE CASCADE,
    FOREIGN KEY (chambre_id) REFERENCES chambre (id_chambre) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS paiement (
    id_paiement   INTEGER PRIMARY KEY AUTOINCREMENT,
    reservation_id INTEGER NOT NULL,
    montant       REAL NOT NULL,
    date_paiement TEXT NOT NULL,
    mode          TEXT NOT NULL DEFAULT 'especes',
    archivee      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (reservation_id) REFERENCES reservation (id_reservation) ON DELETE CASCADE
);
"""


def init_db():
    """Crée les tables si besoin et insère un compte admin + quelques chambres de départ."""
    first_run = not DB_PATH.exists()
    conn = get_db()
    conn.executescript(SCHEMA)

    # Migration pour les bases existantes : ajouter les colonnes manquantes
    for table, colonne in (("client", "archivee"),
                           ("reservation", "archivee"),
                           ("reservation", "paye")):
        try:
            conn.execute(f"SELECT {colonne} FROM {table} LIMIT 1")
        except Exception:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} INTEGER NOT NULL DEFAULT 0")
            conn.commit()

    if first_run:
        # Compte administrateur par défaut : admin / admin123
        conn.execute(
            "INSERT INTO utilisateur (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123")),
        )
        # Quelques chambres d'exemple
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
