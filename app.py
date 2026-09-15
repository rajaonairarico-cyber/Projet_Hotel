"""
app.py
------
Application de Gestion d'Hôtel — entièrement en Python (Flask + SQLite).

Lancement local :
    python app.py
Puis ouvrir : http://127.0.0.1:5000
Compte de démonstration : admin / admin123
"""

import os
from datetime import datetime, date
from functools import wraps
import re
import io

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from werkzeug.security import check_password_hash

from database import get_db, init_db
from pdf_recu import generer_recu_pdf

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_temporaire_pas_securise")


# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM utilisateur WHERE username = ?", (username,)
        ).fetchone()
        db.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id_utilisateur"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))

        flash("Identifiant ou mot de passe incorrect.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Tableau de bord
# ---------------------------------------------------------------------------
@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    nb_clients = db.execute("SELECT COUNT(*) AS n FROM client").fetchone()["n"]
    nb_chambres = db.execute("SELECT COUNT(*) AS n FROM chambre").fetchone()["n"]
    nb_libres = db.execute(
        "SELECT COUNT(*) AS n FROM chambre WHERE statut = 'libre'"
    ).fetchone()["n"]
    nb_occupees = nb_chambres - nb_libres
    nb_reservations = db.execute(
        "SELECT COUNT(*) AS n FROM reservation WHERE statut = 'confirmee'"
    ).fetchone()["n"]
    revenu_total = db.execute(
        "SELECT COALESCE(SUM(montant_total), 0) AS total FROM reservation WHERE statut = 'confirmee'"
    ).fetchone()["total"]
    db.close()

    return render_template(
        "dashboard.html",
        nb_clients=nb_clients,
        nb_chambres=nb_chambres,
        nb_libres=nb_libres,
        nb_occupees=nb_occupees,
        nb_reservations=nb_reservations,
        revenu_total=revenu_total,
    )


# ---------------------------------------------------------------------------
# CLIENTS
# ---------------------------------------------------------------------------
@app.route("/clients")
@login_required
def clients():
    db = get_db()
    liste = db.execute("SELECT * FROM client WHERE archivee = 0 ORDER BY nom").fetchall()
    db.close()
    return render_template("clients.html", clients=liste, edit_client=None)


@app.route("/clients/ajouter", methods=["POST"])
@login_required
def ajouter_client():
    d = request.form
    cin = d.get("cin", "").strip()
    tel = d.get("telephone", "").strip()
    if cin and not re.fullmatch(r'\d{12}', cin):
        flash("Le CIN doit contenir exactement 12 chiffres.")
        return redirect(url_for("clients"))
    if tel and not re.fullmatch(r'\d{10}', tel):
        flash("Le téléphone doit contenir exactement 10 chiffres.")
        return redirect(url_for("clients"))
    db = get_db()
    db.execute(
        "INSERT INTO client (nom, prenom, email, telephone, cin) VALUES (?,?,?,?,?)",
        (d["nom"], d["prenom"], d["email"], tel, cin),
    )
    db.commit()
    db.close()
    return redirect(url_for("clients"))


@app.route("/clients/modifier/<int:cid>", methods=["GET", "POST"])
@login_required
def modifier_client(cid):
    db = get_db()
    if request.method == "POST":
        d = request.form
        cin = d.get("cin", "").strip()
        tel = d.get("telephone", "").strip()
        if cin and not re.fullmatch(r'\d{12}', cin):
            flash("Le CIN doit contenir exactement 12 chiffres.")
            return redirect(url_for("modifier_client", cid=cid))
        if tel and not re.fullmatch(r'\d{10}', tel):
            flash("Le téléphone doit contenir exactement 10 chiffres.")
            return redirect(url_for("modifier_client", cid=cid))
        db.execute(
            "UPDATE client SET nom=?, prenom=?, email=?, telephone=?, cin=? WHERE id_client=?",
            (d["nom"], d["prenom"], d["email"], tel, cin, cid),
        )
        db.commit()
        db.close()
        return redirect(url_for("clients"))

    edit_client = db.execute("SELECT * FROM client WHERE id_client=?", (cid,)).fetchone()
    liste = db.execute("SELECT * FROM client WHERE archivee = 0 ORDER BY nom").fetchall()
    db.close()
    return render_template("clients.html", clients=liste, edit_client=edit_client)


@app.route("/clients/supprimer/<int:cid>", methods=["POST"])
@login_required
def supprimer_client(cid):
    db = get_db()
    active = db.execute(
        """
        SELECT COUNT(*) AS n FROM reservation
        WHERE client_id = ?
          AND archivee = 0
          AND (statut = 'confirmee' OR paye = 0)
        """,
        (cid,),
    ).fetchone()["n"]
    if active > 0:
        db.close()
        flash("Impossible de supprimer ce client : il a encore une ou plusieurs réservations en cours (non payées).")
        return redirect(url_for("clients"))

    db.execute("DELETE FROM reservation WHERE client_id=?", (cid,))
    db.execute("DELETE FROM client WHERE id_client=?", (cid,))
    db.commit()
    db.close()
    return redirect(url_for("clients"))


# ---------------------------------------------------------------------------
# CHAMBRES
# ---------------------------------------------------------------------------
@app.route("/chambres")
@login_required
def chambres():
    db = get_db()
    liste = db.execute("SELECT * FROM chambre ORDER BY numero").fetchall()
    db.close()
    return render_template("chambres.html", chambres=liste, edit_chambre=None)


@app.route("/chambres/ajouter", methods=["POST"])
@login_required
def ajouter_chambre():
    d = request.form
    db = get_db()
    db.execute(
        "INSERT INTO chambre (numero, type, prix_nuit, capacite, statut) VALUES (?,?,?,?,?)",
        (d["numero"], d["type"], d["prix_nuit"], d["capacite"], d.get("statut", "libre")),
    )
    db.commit()
    db.close()
    return redirect(url_for("chambres"))


@app.route("/chambres/modifier/<int:chid>", methods=["GET", "POST"])
@login_required
def modifier_chambre(chid):
    db = get_db()
    if request.method == "POST":
        d = request.form
        db.execute(
            "UPDATE chambre SET numero=?, type=?, prix_nuit=?, capacite=?, statut=? WHERE id_chambre=?",
            (d["numero"], d["type"], d["prix_nuit"], d["capacite"], d.get("statut", "libre"), chid),
        )
        db.commit()
        db.close()
        return redirect(url_for("chambres"))

    edit_chambre = db.execute("SELECT * FROM chambre WHERE id_chambre=?", (chid,)).fetchone()
    liste = db.execute("SELECT * FROM chambre ORDER BY numero").fetchall()
    db.close()
    return render_template("chambres.html", chambres=liste, edit_chambre=edit_chambre)


@app.route("/chambres/supprimer/<int:chid>", methods=["POST"])
@login_required
def supprimer_chambre(chid):
    db = get_db()
    db.execute("DELETE FROM reservation WHERE chambre_id=?", (chid,))
    db.execute("DELETE FROM chambre WHERE id_chambre=?", (chid,))
    db.commit()
    db.close()
    return redirect(url_for("chambres"))


# ---------------------------------------------------------------------------
# RÉSERVATIONS
# ---------------------------------------------------------------------------
@app.route("/reservations")
@login_required
def reservations():
    db = get_db()
    liste = db.execute(
        """
        SELECT r.*, c.nom AS client_nom, c.prenom AS client_prenom,
               ch.numero AS chambre_numero, ch.type AS chambre_type
        FROM reservation r
        JOIN client c  ON c.id_client  = r.client_id
        JOIN chambre ch ON ch.id_chambre = r.chambre_id
        WHERE r.archivee = 0
        ORDER BY r.date_debut DESC
        """
    ).fetchall()
    tous_clients = db.execute("SELECT * FROM client WHERE archivee = 0 ORDER BY nom").fetchall()
    chambres_dispo = db.execute(
        "SELECT * FROM chambre WHERE statut='libre' ORDER BY numero"
    ).fetchall()
    db.close()
    today = date.today().isoformat()
    return render_template(
        "reservations.html",
        reservations=liste,
        tous_clients=tous_clients,
        chambres_dispo=chambres_dispo,
        today=today,
    )


@app.route("/reservations/ajouter", methods=["POST"])
@login_required
def ajouter_reservation():
    d = request.form
    db = get_db()

    chambre = db.execute(
        "SELECT * FROM chambre WHERE id_chambre=? AND statut='libre'", (d["chambre_id"],)
    ).fetchone()

    if not chambre:
        db.close()
        flash("Cette chambre n'est plus disponible.")
        return redirect(url_for("reservations"))

    debut = datetime.strptime(d["date_debut"], "%Y-%m-%d")
    fin = datetime.strptime(d["date_fin"], "%Y-%m-%d")

    if debut.date() < date.today():
        db.close()
        flash("La date de début ne peut pas être dans le passé.")
        return redirect(url_for("reservations"))

    if fin <= debut:
        db.close()
        flash("La date de fin doit être après la date de début.")
        return redirect(url_for("reservations"))

    nb_nuits = max((fin - debut).days, 1)
    montant = nb_nuits * float(chambre["prix_nuit"])

    db.execute(
        """INSERT INTO reservation
           (client_id, chambre_id, date_debut, date_fin, nb_nuits, montant_total, statut)
           VALUES (?,?,?,?,?,?, 'confirmee')""",
        (d["client_id"], d["chambre_id"], d["date_debut"], d["date_fin"], nb_nuits, montant),
    )
    db.execute("UPDATE chambre SET statut='occupee' WHERE id_chambre=?", (d["chambre_id"],))
    db.commit()
    db.close()
    return redirect(url_for("reservations"))


@app.route("/reservations/supprimer/<int:rid>", methods=["POST"])
@login_required
def supprimer_reservation(rid):
    db = get_db()
    row = db.execute(
        "SELECT chambre_id FROM reservation WHERE id_reservation=?", (rid,)
    ).fetchone()
    if row:
        db.execute("UPDATE chambre SET statut='libre' WHERE id_chambre=?", (row["chambre_id"],))
    db.execute("DELETE FROM reservation WHERE id_reservation=?", (rid,))
    db.commit()
    db.close()
    return redirect(url_for("reservations"))


# ---------------------------------------------------------------------------
# PAIEMENTS & RECUS
# ---------------------------------------------------------------------------
@app.route("/reservations/payer/<int:rid>", methods=["POST"])
@login_required
def payer_reservation(rid):
    db = get_db()
    res = db.execute("SELECT * FROM reservation WHERE id_reservation=?", (rid,)).fetchone()
    if not res:
        db.close()
        return redirect(url_for("reservations"))

    montant = float(request.form.get("montant", res["montant_total"]))
    mode = request.form.get("mode", "especes")

    db.execute(
        "INSERT INTO paiement (reservation_id, montant, date_paiement, mode) VALUES (?,?,?,?)",
        (rid, montant, date.today().isoformat(), mode),
    )

    total_paye = db.execute(
        "SELECT COALESCE(SUM(montant), 0) AS t FROM paiement WHERE reservation_id=?",
        (rid,),
    ).fetchone()["t"]

    if total_paye >= res["montant_total"]:
        db.execute("UPDATE reservation SET paye = 1 WHERE id_reservation=?", (rid,))
    db.commit()
    db.close()
    flash("Paiement enregistré avec succès.")
    return redirect(url_for("reservations"))


@app.route("/reservations/recu/<int:rid>")
@login_required
def recu_reservation(rid):
    db = get_db()
    res = db.execute(
        """
        SELECT r.*, c.nom AS client_nom, c.prenom AS client_prenom, c.cin AS client_cin,
               ch.numero AS chambre_numero, ch.type AS chambre_type, ch.prix_nuit
        FROM reservation r
        JOIN client c  ON c.id_client  = r.client_id
        JOIN chambre ch ON ch.id_chambre = r.chambre_id
        WHERE r.id_reservation = ?
        """,
        (rid,),
    ).fetchone()
    if not res:
        db.close()
        return redirect(url_for("reservations"))

    total_paye = db.execute(
        "SELECT COALESCE(SUM(montant), 0) AS t FROM paiement WHERE reservation_id=?",
        (rid,),
    ).fetchone()["t"]
    db.close()

    donnees = {
        "numero_recu": res["id_reservation"],
        "date_recu": date.today().isoformat(),
        "client_nom": res["client_nom"],
        "client_prenom": res["client_prenom"],
        "client_cin": res["client_cin"],
        "chambre_numero": res["chambre_numero"],
        "chambre_type": res["chambre_type"],
        "date_debut": res["date_debut"],
        "date_fin": res["date_fin"],
        "nb_nuits": res["nb_nuits"],
        "prix_nuit": res["prix_nuit"],
        "montant_total": res["montant_total"],
        "montant_paye": total_paye,
        "operateur": session.get("username", ""),
    }

    pdf = generer_recu_pdf(donnees)
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"recu_reservation_{rid}.pdf",
    )


# ---------------------------------------------------------------------------
# FIN DE LOCATION (libérer la chambre)
# ---------------------------------------------------------------------------
@app.route("/reservations/terminer/<int:rid>", methods=["POST"])
@login_required
def terminer_reservation(rid):
    db = get_db()
    row = db.execute(
        "SELECT chambre_id FROM reservation WHERE id_reservation=?", (rid,)
    ).fetchone()
    if row:
        db.execute("UPDATE chambre SET statut='libre' WHERE id_chambre=?", (row["chambre_id"],))
        db.execute("UPDATE reservation SET statut='terminee' WHERE id_reservation=?", (rid,))
        db.commit()
    db.close()
    flash("Réservation terminée, la chambre est maintenant libre.")
    return redirect(url_for("reservations"))


@app.route("/clients/archives")
@login_required
def clients_archives():
    db = get_db()
    liste = db.execute("SELECT * FROM client WHERE archivee = 1 ORDER BY nom").fetchall()
    db.close()
    return render_template("clients_archives.html", clients=liste)


@app.route("/clients/archiver/<int:cid>", methods=["POST"])
@login_required
def archiver_client(cid):
    db = get_db()
    db.execute("UPDATE client SET archivee = 1 WHERE id_client = ?", (cid,))
    db.commit()
    db.close()
    flash("Client archivé avec succès.")
    return redirect(url_for("clients"))


@app.route("/clients/retirer/<int:cid>", methods=["POST"])
@login_required
def retirer_client(cid):
    db = get_db()
    db.execute("UPDATE client SET archivee = 0 WHERE id_client = ?", (cid,))
    db.commit()
    db.close()
    flash("Client restauré.")
    return redirect(url_for("clients_archives"))


@app.route("/reservations/archives")
@login_required
def reservations_archives():
    db = get_db()
    liste = db.execute(
        """
        SELECT r.*, c.nom AS client_nom, c.prenom AS client_prenom,
               ch.numero AS chambre_numero, ch.type AS chambre_type
        FROM reservation r
        JOIN client c  ON c.id_client  = r.client_id
        JOIN chambre ch ON ch.id_chambre = r.chambre_id
        WHERE r.archivee = 1
        ORDER BY r.date_debut DESC
        """
    ).fetchall()
    db.close()
    return render_template("reservations_archives.html", reservations=liste)


@app.route("/reservations/archiver/<int:rid>", methods=["POST"])
@login_required
def archiver_reservation(rid):
    db = get_db()
    row = db.execute(
        "SELECT chambre_id FROM reservation WHERE id_reservation=?", (rid,)
    ).fetchone()
    if row:
        db.execute("UPDATE chambre SET statut='libre' WHERE id_chambre=?", (row["chambre_id"],))
    db.execute("UPDATE reservation SET archivee = 1 WHERE id_reservation = ?", (rid,))
    db.commit()
    db.close()
    flash("Réservation archivée, la chambre est libre.")
    return redirect(url_for("reservations"))


@app.route("/reservations/retirer/<int:rid>", methods=["POST"])
@login_required
def retirer_reservation(rid):
    db = get_db()
    db.execute("UPDATE reservation SET archivee = 0 WHERE id_reservation = ?", (rid,))
    db.commit()
    db.close()
    flash("Réservation restaurée.")
    return redirect(url_for("reservations_archives"))


# ---------------------------------------------------------------------------
# INITIALISATION (exécutée par Gunicorn au démarrage)
# ---------------------------------------------------------------------------
init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)