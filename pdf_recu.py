"""
pdf_recu.py
-----------
Génère un reçu de paiement au format PDF, sans bibliothèque externe.
Écrit un fichier PDF minimal (format A5) avec Python pur.
"""


def _escape(text):
    s = str(text)
    s = s.replace("\\", "\\\\")
    s = s.replace("(", "\\(")
    s = s.replace(")", "\\)")
    return s


def generer_recu_pdf(donnees):
    """
    donnees: dict avec les clés suivantes :
        numero_recu, date_recu, client_nom, client_prenom, client_cin,
        chambre_numero, chambre_type, date_debut, date_fin, nb_nuits,
        prix_nuit, montant_total, montant_paye, operateur
    Retourne les octets du PDF.
    """
    # Initialisation de l'objet PDF simple (structure minimale avec un flux)
    objects = []

    # Objet 1 : catalogue
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    # Objet 2 : pages
    objects.append("<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # Objet 3 : page A5 portrait (419 x 595 points)
    objects.append(
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 419 595] "
        "/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
    )
    # Objet 4 : police Helvetica (encodage WinAnsi pour les accents)
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    # Objet 5 : police Helvetica-Bold
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    # ----- Construction du contenu texte -----
    lignes = []

    def ajouter_ligne(texte, x, y, taille=11, police="F1"):
        lignes.append(f"BT /{police} {taille} Tf 1 0 0 1 {x} {y} Tm ({_escape(texte)}) Tj ET")

    x = 30
    y = 545

    # En-tête
    ajouter_ligne("RÉSERVATION HOTEL", x, y, 16, "F2")
    y -= 22
    ajouter_ligne("RECU DE PAIEMENT", x, y, 12, "F2")
    y -= 24

    # Numéro / date
    ajouter_ligne(f"Reçu N°: {donnees['numero_recu']}", x, y, 10)
    ajouter_ligne(f"Date: {donnees['date_recu']}", 230, y, 10)
    y -= 22
    ajouter_ligne(f"Opérateur: {donnees['operateur']}", x, y, 10)
    y -= 30

    # Séparateur
    lignes.append(f"{x} {y} m 390 {y} l S")
    y -= 20

    # Client
    ajouter_ligne("CLIENT", x, y, 11, "F2")
    y -= 18
    ajouter_ligne(f"Nom: {donnees['client_nom']} {donnees['client_prenom']}", x, y, 11)
    y -= 16
    ajouter_ligne(f"CIN: {donnees['client_cin'] or '-'}", x, y, 11)
    y -= 26

    # Chambre
    ajouter_ligne("CHAMBRE", x, y, 11, "F2")
    y -= 18
    ajouter_ligne(f"N° {donnees['chambre_numero']} - {donnees['chambre_type']}", x, y, 11)
    y -= 16
    ajouter_ligne(f"Du {donnees['date_debut']} au {donnees['date_fin']}", x, y, 11)
    y -= 16
    ajouter_ligne(f"Durée : {donnees['nb_nuits']} nuit(s)", x, y, 11)
    y -= 26

    # Récapitulatif
    ajouter_ligne("RÉCAPITULATIF", x, y, 11, "F2")
    y -= 18
    ajouter_ligne(f"Prix par nuit : {donnees['prix_nuit']:.0f} Ar", x, y, 11)
    y -= 16
    ajouter_ligne(f"Montant total : {donnees['montant_total']:.0f} Ar", x, y, 11, "F2")
    y -= 16
    ajouter_ligne(f"Payé : {donnees['montant_paye']:.0f} Ar", x, y, 11, "F2")
    y -= 30

    # Séparateur + montant restant
    lignes.append(f"{x} {y} m 390 {y} l S")
    y -= 18
    reste = max(donnees["montant_total"] - donnees["montant_paye"], 0)
    if reste == 0:
        ajouter_ligne("STATUT : PAYÉ INTÉGRALEMENT", x, y, 12, "F2")
    else:
        ajouter_ligne(f"Reste à payer : {reste:.0f} Ar", x, y, 12, "F2")
    y -= 26

    # Signature
    ajouter_ligne("Signature / Cachet", 275, y, 10)

    # Objet 6 : contenu (avec longueur)
    stream = "\n".join(lignes)
    objects.append(
        f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream"
    )

    # ----- Assemblage du fichier PDF -----
    header = b"%PDF-1.4\n"
    data = header
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")

    xref_offset = len(data)
    data += f"xref\n0 {len(objects)+1}\n".encode("latin-1")
    data += b"0000000000 65535 f \n"
    for off in offsets:
        data += f"{off:010d} 00000 n \n".encode("latin-1")

    data += f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin-1")

    return data
