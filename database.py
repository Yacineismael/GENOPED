# -*- coding: utf-8 -*-
"""
Accès à la base de données GénoPed.

Chaque analyse réalisée dans l'application est enregistrée dans la table `consultations`,
à des fins de traçabilité médicale et de statistiques d'usage.

Aucune donnée identifiante n'est stockée (ni nom, ni identifiant patient) :
la pseudonymisation est assurée par conception.

La base est choisie par la variable d'environnement DATABASE_URL :
  - par défaut          : sqlite:///sql/genoped.db
  - PostgreSQL (GénoPed): postgresql+psycopg2://utilisateur:motdepasse@serveur:5432/genoped
Le reste du code est identique dans les deux cas.
"""
import json
import os
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, Float, Integer, MetaData, String,
                        Table, Text, create_engine, desc, func, select)

CHEMIN_DEFAUT = "sqlite:///" + os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            "sql", "genoped.db")
DATABASE_URL = os.environ.get("DATABASE_URL", CHEMIN_DEFAUT)

engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

consultations = Table(
    "consultations", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("horodatage", DateTime, nullable=False),
    # Praticien à l'origine de l'analyse (traçabilité / audit)
    Column("praticien_nom", String(80)),
    Column("praticien_prenom", String(80)),
    Column("praticien_etablissement", String(120)),
    # Signes cliniques principaux (permettent des statistiques directes en SQL)
    Column("age_patient", Float),
    Column("sexe", String(40)),
    Column("gene_maternel", String(40)),
    Column("gene_paternel", String(40)),
    Column("hypotonie_musculaire", Integer),
    Column("retard_croissance", Integer),
    Column("convulsions", Integer),
    Column("detresse_respiratoire", Integer),
    Column("regression_neurologique", Integer),
    # Résultat proposé par le modèle
    Column("maladie_1", String(80)), Column("probabilite_1", Float),
    Column("maladie_2", String(80)), Column("probabilite_2", Float),
    Column("maladie_3", String(80)), Column("probabilite_3", Float),
    # Saisie complète, conservée pour l'audit
    Column("donnees_saisies", Text),
)


def initialiser():
    """Crée la table si besoin, et ajoute les colonnes manquantes (migration simple)."""
    metadata.create_all(engine)
    from sqlalchemy import inspect, text
    inspecteur = inspect(engine)
    existantes = {c["name"] for c in inspecteur.get_columns("consultations")}
    nouvelles = {"praticien_nom": "VARCHAR(80)", "praticien_prenom": "VARCHAR(80)",
                 "praticien_etablissement": "VARCHAR(120)"}
    with engine.begin() as connexion:
        for nom, typ in nouvelles.items():
            if nom not in existantes:
                connexion.execute(text(f"ALTER TABLE consultations ADD COLUMN {nom} {typ}"))


def enregistrer(donnees, resultats, praticien=None):
    """Enregistre une consultation. `donnees` = ligne saisie, `resultats` = top 3,
    `praticien` = dict {nom, prenom, etablissement} de l'utilisateur connecté."""
    praticien = praticien or {}
    ligne = {
        "horodatage": datetime.now(timezone.utc),
        "praticien_nom": praticien.get("nom"),
        "praticien_prenom": praticien.get("prenom"),
        "praticien_etablissement": praticien.get("etablissement"),
        "age_patient": _flottant(donnees.get("Âge du patient (années)")),
        "sexe": donnees.get("Sexe"),
        "gene_maternel": donnees.get("Gène maternel"),
        "gene_paternel": donnees.get("Gène paternel"),
        "hypotonie_musculaire": _entier(donnees.get("Hypotonie musculaire")),
        "retard_croissance": _entier(donnees.get("Retard de croissance")),
        "convulsions": _entier(donnees.get("Convulsions")),
        "detresse_respiratoire": _entier(donnees.get("Détresse respiratoire")),
        "regression_neurologique": _entier(donnees.get("Régression neurologique")),
        "donnees_saisies": json.dumps(donnees, ensure_ascii=False),
    }
    for rang, resultat in enumerate(resultats[:3], start=1):
        ligne[f"maladie_{rang}"] = resultat["maladie"]
        ligne[f"probabilite_{rang}"] = resultat["probabilite"]

    with engine.begin() as connexion:
        connexion.execute(consultations.insert().values(**ligne))


def dernieres(limite=50):
    """Les consultations les plus récentes, pour le back-office."""
    with engine.connect() as connexion:
        lignes = connexion.execute(
            select(consultations).order_by(desc(consultations.c.horodatage)).limit(limite)
        ).mappings().all()
    return [dict(l) for l in lignes]


def statistiques():
    """Quelques indicateurs d'usage pour le back-office."""
    with engine.connect() as connexion:
        total = connexion.execute(
            select(func.count()).select_from(consultations)).scalar() or 0
        repartition = connexion.execute(
            select(consultations.c.maladie_1, func.count().label("n"))
            .group_by(consultations.c.maladie_1)
            .order_by(desc("n"))
        ).all()
        confiance = connexion.execute(
            select(func.avg(consultations.c.probabilite_1))).scalar()
    return {
        "total": total,
        "repartition": [(m or "—", n) for m, n in repartition],
        "confiance_moyenne": round(confiance, 1) if confiance else None,
    }


def _entier(valeur):
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _flottant(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None
