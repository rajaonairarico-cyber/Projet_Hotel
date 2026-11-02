# Gestion hôtelière

Application de gestion d'hôtel en Python : clients, chambres, réservations, paiements et reçus PDF.

## Démo

https://projet-hotel-bfwq.onrender.com

## Fonctionnalités

- Tableau de bord
- Gestion des clients et des chambres
- Création et suivi des réservations
- Paiements et génération de reçus PDF
- Archivage des clients et des réservations
- Authentification administrateur

## Stack

- Python 3.11, Flask 3
- SQLite
- ReportLab (reçus PDF)
- Gunicorn
- Render

## Structure

```
Projet_Hotel/
├── app.py
├── database.py
├── pdf_recu.py
├── templates/
├── static/
├── requirements.txt
└── render.yaml
```

## Configuration

Copier `.env.example` vers `.env` et renseigner :

| Variable | Description |
|---|---|
| `SECRET_KEY` | clé de session Flask |
| `ADMIN_USERNAME` | nom du compte administrateur |
| `ADMIN_PASSWORD` | mot de passe initial de l'administrateur |

## Lancer en local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Puis ouvrir http://127.0.0.1:5000.

## Déploiement

Le fichier `render.yaml` décrit le service Render.

> Sur Render, SQLite est stocké sur un disque éphémère : les données sont réinitialisées à chaque redéploiement. Pour une utilisation réelle, prévoir une base persistante.

## Sécurité

- La clé de session n'est plus codée en dur.
- Le compte administrateur se configure par variables d'environnement.
- Changer le mot de passe administrateur par défaut avant toute mise en ligne.
