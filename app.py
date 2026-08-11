# -*- coding: utf-8 -*-
"""
GP AI — Application web d'aide à l'orientation diagnostique des troubles génétiques chez l'enfant.
Charge le modèle entraîné (Forêt aléatoire) et propose, à partir des données cliniques d'un enfant,
les 3 maladies génétiques les plus probables.
"""
import functools
import json
import os
import pickle
import pandas as pd
from datetime import datetime
from flask import (Flask, Response, redirect, render_template, request,
                   session, url_for)

import database
import pdf_rapport

CHEMIN_MODELE = os.path.join("model", "modele_gpai.pkl")
CHEMIN_CONTEXTE = os.path.join("model", "contexte_maladies.json")

app = Flask(__name__)
# Clé de session (à surcharger par variable d'environnement en production)
app.secret_key = os.environ.get("SECRET_KEY", "genoped-cle-de-session-dev")

with open(CHEMIN_MODELE, "rb") as f:
    BUNDLE = pickle.load(f)

PIPELINE = BUNDLE["pipeline"]
CLASSES = BUNDLE["classes"]
NUMERIQUES = BUNDLE["features"]["numeriques"]
SYMPTOMES = BUNDLE["features"]["symptomes"]
CATEGORIELLES = BUNDLE["features"]["categorielles"]
ORDRE = BUNDLE["ordre_features"]
VALEURS_CAT = BUNDLE["valeurs_categorielles"]
BORNES_NUM = BUNDLE["bornes_numeriques"]
META = BUNDLE["meta"]

# Contexte médical : description, famille et signature clinique réelle de chaque maladie
with open(CHEMIN_CONTEXTE, encoding="utf-8") as f:
    CONTEXTE = json.load(f)

SEUIL_RARE = 200        # en dessous, la maladie est rare : prédiction moins fiable
SEUIL_FREQUENT = 50     # % à partir duquel un symptôme est considéré typique d'une maladie

# Identifiants du back-office (à surcharger par variables d'environnement en production)
ADMIN_UTILISATEUR = os.environ.get("ADMIN_UTILISATEUR", "admin")
ADMIN_MOTDEPASSE = os.environ.get("ADMIN_MOTDEPASSE", "genoped2026")

# Code d'accès partagé remis aux praticiens des établissements partenaires
CODE_ACCES = os.environ.get("CODE_ACCES_PRATICIEN", "94450")

# Liste de référence des CHU / CHR de France (établissements de santé publics majeurs)
ETABLISSEMENTS = [
    "AP-HP — Assistance Publique-Hôpitaux de Paris",
    "AP-HM — Assistance Publique-Hôpitaux de Marseille",
    "Hospices Civils de Lyon",
    "CHU d'Amiens-Picardie", "CHU d'Angers", "CHU de Besançon", "CHU de Bordeaux",
    "CHU de Brest", "CHU de Caen", "CHU de Clermont-Ferrand", "CHU de Dijon",
    "CHU de Grenoble Alpes", "CHU de Guadeloupe", "CHU de La Réunion", "CHU de Lille",
    "CHU de Limoges", "CHU de Martinique", "CHU de Montpellier", "CHU de Nancy",
    "CHU de Nantes", "CHU de Nice", "CHU de Nîmes", "CHU d'Orléans", "CHU de Poitiers",
    "CHU de Reims", "CHU de Rennes", "CHU de Rouen", "CHU de Saint-Étienne",
    "CHU de Strasbourg", "CHU de Toulouse", "CHU de Tours",
    "Autre établissement",
]

database.initialiser()


def connexion_requise(vue):
    """Réserve l'accès à l'outil aux praticiens identifiés."""
    @functools.wraps(vue)
    def enveloppe(*args, **kwargs):
        if "praticien" not in session:
            return redirect(url_for("connexion"))
        return vue(*args, **kwargs)
    return enveloppe


def authentification_requise(vue):
    """Protège le back-office par une authentification HTTP simple."""
    @functools.wraps(vue)
    def enveloppe(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != ADMIN_UTILISATEUR or auth.password != ADMIN_MOTDEPASSE:
            return Response(
                "Accès réservé à l'administrateur GénoPed.", 401,
                {"WWW-Authenticate": 'Basic realm="Back-office GenoPed"'})
        return vue(*args, **kwargs)
    return enveloppe

# --- Organisation du formulaire en groupes logiques ---
# Les symptômes et les facteurs génétiques sont placés en premier : ce sont, de loin,
# les variables les plus déterminantes (analyse exploratoire, V de Cramér 0,21 à 0,67).
GROUPES = [
    ("Symptômes cliniques observés", "Symptômes",
     "Ce sont les informations les plus déterminantes pour l'orientation.", True,
     SYMPTOMES),
    ("Facteurs génétiques", "Génétique",
     "Présence d'un facteur génétique connu du côté de chaque parent.", True,
     ["Gène maternel", "Gène paternel"]),
    ("Informations sur l'enfant", "Enfant", None, False,
     ["Âge du patient (années)", "Sexe"]),
    ("Grossesse et naissance", "Grossesse", None, False,
     ["Âge de la mère", "Âge du père", "Nombre d'avortements antérieurs",
      "Asphyxie à la naissance", "Lieu de naissance", "Conception assistée (FIV/PMA)",
      "Prise d'acide folique périconceptionnelle",
      "Antécédents d'anomalies lors de grossesses précédentes"]),
    ("Antécédents parentaux", "Antécédents", None, False,
     ["Antécédent de maladie maternelle grave",
      "Antécédent d'exposition aux radiations (rayons X)", "Antécédent de toxicomanie"]),
    ("Examens et mesures", "Examens", None, False,
     ["Numération des globules rouges (mcL)", "Numération des globules blancs (milliers/µL)",
      "Fréquence respiratoire", "Fréquence cardiaque", "Résultat du bilan sanguin",
      "Malformations congénitales"]),
]


def defaut_categoriel(c):
    return "Inconnu" if "Inconnu" in VALEURS_CAT[c] else VALEURS_CAT[c][0]


def decrire_champ(nom):
    """Décrit un champ (type + options) pour l'affichage."""
    if nom in SYMPTOMES:
        return {"type": "checkbox", "nom": nom}
    if nom in NUMERIQUES:
        b = BORNES_NUM[nom]
        return {"type": "number", "nom": nom, "min": round(b["min"], 2),
                "max": round(b["max"], 2), "defaut": round(b["mediane"], 2)}
    return {"type": "select", "nom": nom, "options": VALEURS_CAT[nom],
            "defaut": defaut_categoriel(nom)}


def construire_groupes():
    groupes = []
    deja_vus = set()
    for titre, court, aide, accent, noms in GROUPES:
        champs = [decrire_champ(n) for n in noms if n in ORDRE]
        deja_vus.update(n for n in noms if n in ORDRE)
        groupes.append({"titre": titre, "court": court, "aide": aide,
                        "accent": accent, "champs": champs})
    # Filet de sécurité : si une variable n'a pas été classée, on l'ajoute en fin de formulaire
    oublies = [n for n in ORDRE if n not in deja_vus]
    if oublies:
        groupes.append({"titre": "Autres informations", "court": "Autres", "aide": None,
                        "accent": False, "champs": [decrire_champ(n) for n in oublies]})
    return groupes


def patient_exemple():
    """Profil réaliste pré-rempli, pratique pour une démonstration."""
    ex = {
        "Âge du patient (années)": 3, "Âge de la mère": 32, "Âge du père": 35,
        "Numération des globules rouges (mcL)": 4.7,
        "Numération des globules blancs (milliers/µL)": 8.0,
        "Nombre d'avortements antérieurs": 0,
        "Hypotonie musculaire": "on", "Convulsions": "on", "Régression neurologique": "on",
        "Gène maternel": "Oui", "Gène paternel": "Non",
        "Sexe": "Masculin", "Fréquence cardiaque": "Normale",
        "Fréquence respiratoire": "Normale (30-60)", "Résultat du bilan sanguin": "Anormal",
    }
    # On complète les catégorielles manquantes par leur valeur par défaut,
    # et on vérifie que chaque valeur existe bien dans le modèle.
    for c in CATEGORIELLES:
        if c not in ex or ex[c] not in VALEURS_CAT[c]:
            ex[c] = defaut_categoriel(c)
    return ex


def expliquer(maladie, symptomes_presents):
    """Explique pourquoi une maladie ressort, en comparant les symptômes de l'enfant
    à la signature clinique réelle de cette maladie (calculée sur les données)."""
    ctx = CONTEXTE.get(maladie, {})
    signature = ctx.get("signature", {})
    en_faveur, en_defaveur = [], []
    for symptome, pct in sorted(signature.items(), key=lambda x: -x[1]):
        if symptome in symptomes_presents and pct >= SEUIL_FREQUENT:
            en_faveur.append({"nom": symptome, "pct": int(pct)})
        elif symptome not in symptomes_presents and pct >= 60:
            en_defaveur.append({"nom": symptome, "pct": int(pct)})
    return {
        "description": ctx.get("description", ""),
        "famille": ctx.get("famille", "autre"),
        "rare": ctx.get("effectif", 9999) < SEUIL_RARE,
        "effectif": ctx.get("effectif"),
        "en_faveur": en_faveur[:3],
        "en_defaveur": en_defaveur[:2],
        "examens": ctx.get("examens", []),
    }


def comparer_top3(maladies):
    """Explique pourquoi ces 3 maladies sortent ensemble : même famille clinique ou non."""
    familles = [CONTEXTE.get(m, {}).get("famille", "autre") for m in maladies]
    rares = [m for m in maladies if CONTEXTE.get(m, {}).get("effectif", 9999) < SEUIL_RARE]

    if len(set(familles)) == 1:
        texte = ("Ces trois maladies appartiennent à la même famille : les maladies "
                 f"{familles[0]}s. Elles partagent des mécanismes et des symptômes très proches, "
                 "ce qui explique que le modèle hésite entre elles. Seul un test génétique permet "
                 "de trancher.")
    elif len(set(familles)) == 2:
        commune = max(set(familles), key=familles.count)
        concernees = [m for m, f in zip(maladies, familles) if f == commune]
        texte = (f"{' et '.join(concernees)} appartiennent à la même famille "
                 f"(maladies {commune}s) et se ressemblent beaucoup. La troisième piste est d'une "
                 "nature différente : le modèle la propose parce qu'elle partage certains signes "
                 "présents chez cet enfant.")
    else:
        texte = ("Ces trois maladies sont de natures différentes. Le modèle les rapproche non pas "
                 "parce qu'elles se ressemblent, mais parce que les signes de cet enfant se "
                 "retrouvent partiellement dans chacune, sans qu'aucune ne se détache nettement. "
                 "Le diagnostic reste donc très ouvert.")

    if rares:
        texte += (" ⚠️ " + " et ".join(rares) + (" est une maladie rare" if len(rares) == 1
                  else " sont des maladies rares") + " dans les données : le modèle a tendance à "
                  "la proposer trop facilement, cette piste est à considérer avec prudence.")
    return texte


def lire_formulaire(form):
    """Transforme les données du formulaire en une ligne exploitable par le modèle."""
    donnees = {}
    for c in NUMERIQUES:
        val = str(form.get(c, "")).strip()
        try:
            donnees[c] = float(val) if val != "" else BORNES_NUM[c]["mediane"]
        except ValueError:
            donnees[c] = BORNES_NUM[c]["mediane"]
    for c in SYMPTOMES:
        donnees[c] = 1 if form.get(c) == "on" else 0
    for c in CATEGORIELLES:
        val = form.get(c, defaut_categoriel(c))
        donnees[c] = val if val in VALEURS_CAT[c] else defaut_categoriel(c)
    return pd.DataFrame([donnees], columns=ORDRE)


@app.route("/")
def accueil():
    """Page d'accueil : présentation de GénoPed et de l'outil."""
    return render_template("accueil.html", meta=META, nb_classes=len(CLASSES))


@app.route("/connexion", methods=["GET", "POST"])
def connexion():
    """Identification du praticien avant l'accès à l'outil."""
    erreur = None
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        prenom = request.form.get("prenom", "").strip()
        etablissement = request.form.get("etablissement", "").strip()
        code = request.form.get("code", "").strip()
        if not nom or not prenom:
            erreur = "Veuillez renseigner votre nom et votre prénom."
        elif code != CODE_ACCES:
            erreur = "Code d'accès incorrect."
        else:
            session["praticien"] = {"nom": nom, "prenom": prenom,
                                    "etablissement": etablissement or "Non précisé"}
            return redirect(url_for("analyse"))
    return render_template("connexion.html", erreur=erreur, etablissements=ETABLISSEMENTS)


@app.route("/deconnexion")
def deconnexion():
    session.pop("praticien", None)
    return redirect(url_for("accueil"))


@app.route("/analyse", methods=["GET", "POST"])
@connexion_requise
def analyse():
    resultats = None
    autres = None
    comparaison = None
    valeurs = {}

    if request.method == "POST":
        valeurs = request.form.to_dict()
        ligne = lire_formulaire(request.form)
        proba = PIPELINE.predict_proba(ligne)[0]
        top3_idx = proba.argsort()[::-1][:3]

        symptomes_presents = {s for s in SYMPTOMES if int(ligne.iloc[0][s]) == 1}
        resultats = []
        for i in top3_idx:
            maladie = CLASSES[i]
            resultats.append({"maladie": maladie,
                              "probabilite": round(float(proba[i]) * 100, 1),
                              "explication": expliquer(maladie, symptomes_presents)})
        # part restante, pour que le total affiché fasse bien 100 %
        autres = round(100.0 - sum(r["probabilite"] for r in resultats), 1)
        comparaison = comparer_top3([r["maladie"] for r in resultats])

        # Traçabilité : on enregistre la consultation (données patient pseudonymisées ;
        # seul le praticien à l'origine de l'analyse est identifié, pour l'audit)
        try:
            database.enregistrer(ligne.iloc[0].to_dict(), resultats, session.get("praticien"))
        except Exception as erreur:                      # l'app doit rester utilisable
            app.logger.warning("Consultation non enregistrée : %s", erreur)

        # Version compacte du rapport, conservée en session pour l'export PDF
        session["dernier_rapport"] = {
            "date": datetime.now().strftime("%d/%m/%Y à %H:%M"),
            "praticien": session.get("praticien"),
            "symptomes_presents": sorted(symptomes_presents),
            "autres": autres,
            "comparaison": comparaison,
            "resultats": [{
                "maladie": r["maladie"], "probabilite": r["probabilite"],
                "description": r["explication"]["description"],
                "examens": r["explication"]["examens"],
            } for r in resultats],
        }
    elif request.args.get("exemple") == "1":
        valeurs = patient_exemple()

    return render_template("index.html", groupes=construire_groupes(), resultats=resultats,
                           autres=autres, nb_autres=len(CLASSES) - 3, comparaison=comparaison,
                           valeurs=valeurs, meta=META, praticien=session.get("praticien"))


@app.route("/telecharger-pdf")
@connexion_requise
def telecharger_pdf():
    """Génère et renvoie le compte-rendu PDF de la dernière analyse."""
    rapport = session.get("dernier_rapport")
    if not rapport:
        return redirect(url_for("analyse"))
    pdf = pdf_rapport.generer_pdf(rapport)
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{pdf_rapport.nom_fichier(rapport)}"'})


@app.route("/admin")
@authentification_requise
def admin():
    """Back-office : historique des consultations et statistiques d'usage."""
    return render_template("admin.html",
                           stats=database.statistiques(),
                           consultations=database.dernieres(50),
                           base=database.DATABASE_URL.split("://")[0])


@app.route("/sante")
def sante():
    return {"statut": "ok", "modele": META["algorithme"], "classes": len(CLASSES)}


if __name__ == "__main__":
    # En local : debug activé. En production (serveur), gunicorn lance l'app
    # et ces valeurs sont surchargées par les variables d'environnement.
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
