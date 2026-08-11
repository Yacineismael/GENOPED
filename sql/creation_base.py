# -*- coding: utf-8 -*-
"""
GénoPed — Création de la base de données des dossiers patients.

Ce script :
  1. charge le jeu de données nettoyé (CSV) ;
  2. crée la base SQLite `genoped.db` et la table `patients` ;
  3. mesure le temps d'exécution de requêtes AVANT indexation ;
  4. crée les index (version optimisée) et remesure ;
  5. exporte un dump SQL compatible PostgreSQL (`genoped_dump.sql`).

Lancement :  python sql/creation_base.py
"""
import os
import sqlite3
import time

import pandas as pd

DOSSIER = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(DOSSIER, "..", "disorders_nettoye_v2.csv")
BASE = os.path.join(DOSSIER, "genoped.db")
DUMP = os.path.join(DOSSIER, "genoped_dump.sql")

# Correspondance : libellé métier (CSV) -> nom de colonne SQL
COLONNES = {
    "Âge du patient (années)": "age_patient",
    "Gène maternel": "gene_maternel",
    "Gène paternel": "gene_paternel",
    "Numération des globules rouges (mcL)": "globules_rouges",
    "Âge de la mère": "age_mere",
    "Âge du père": "age_pere",
    "Fréquence respiratoire": "frequence_respiratoire",
    "Fréquence cardiaque": "frequence_cardiaque",
    "Sexe": "sexe",
    "Asphyxie à la naissance": "asphyxie_naissance",
    "Lieu de naissance": "lieu_naissance",
    "Prise d'acide folique périconceptionnelle": "acide_folique",
    "Antécédent de maladie maternelle grave": "antecedent_maladie_maternelle",
    "Antécédent d'exposition aux radiations (rayons X)": "antecedent_radiations",
    "Antécédent de toxicomanie": "antecedent_toxicomanie",
    "Conception assistée (FIV/PMA)": "conception_assistee",
    "Antécédents d'anomalies lors de grossesses précédentes": "antecedents_grossesses",
    "Nombre d'avortements antérieurs": "nb_avortements",
    "Malformations congénitales": "malformations_congenitales",
    "Numération des globules blancs (milliers/µL)": "globules_blancs",
    "Résultat du bilan sanguin": "bilan_sanguin",
    "Statut du panel génétique": "statut_panel_genetique",
    "Nom du gène maternel": "nom_gene_maternel",
    "Nom du gène paternel": "nom_gene_paternel",
    "Hypotonie musculaire": "hypotonie_musculaire",
    "Retard de croissance": "retard_croissance",
    "Convulsions": "convulsions",
    "Détresse respiratoire": "detresse_respiratoire",
    "Régression neurologique": "regression_neurologique",
    "Sous-classe diagnostique": "sous_classe_diagnostique",
}

NUMERIQUES = ["age_patient", "globules_rouges", "age_mere", "age_pere",
              "globules_blancs", "nb_avortements"]
SYMPTOMES = ["hypotonie_musculaire", "retard_croissance", "convulsions",
             "detresse_respiratoire", "regression_neurologique"]

# Requêtes servant au comparatif de performance
REQUETES = [
    ("Filtre sur la maladie",
     "SELECT COUNT(*) FROM patients WHERE sous_classe_diagnostique = 'Syndrome de Leigh'"),
    ("Filtre maladie + symptôme",
     "SELECT COUNT(*) FROM patients WHERE sous_classe_diagnostique = 'Mucoviscidose' "
     "AND detresse_respiratoire = 1"),
    ("Agrégat par maladie",
     "SELECT sous_classe_diagnostique, AVG(age_patient) FROM patients "
     "GROUP BY sous_classe_diagnostique"),
]


def type_sql(col):
    if col in NUMERIQUES:
        return "NUMERIC"
    if col in SYMPTOMES:
        return "INTEGER"
    return "VARCHAR(80)"


def charger():
    df = pd.read_csv(CSV)
    manquantes = [c for c in COLONNES if c not in df.columns]
    if manquantes:
        raise SystemExit(f"Colonnes absentes du CSV : {manquantes}")
    return df[list(COLONNES)].rename(columns=COLONNES)


def creer_base(df):
    if os.path.exists(BASE):
        os.remove(BASE)
    con = sqlite3.connect(BASE)
    colonnes_sql = ",\n  ".join(f"{c} {type_sql(c)}" for c in df.columns)
    con.execute(f"CREATE TABLE patients (\n  id INTEGER PRIMARY KEY AUTOINCREMENT,\n  {colonnes_sql}\n)")
    df.to_sql("patients", con, if_exists="append", index=False)
    con.commit()
    return con


def mesurer(con, repetitions=40):
    """Temps moyen d'exécution de chaque requête, en millisecondes."""
    resultats = {}
    for libelle, sql in REQUETES:
        con.execute("SELECT 1")  # réchauffe la connexion
        debut = time.perf_counter()
        for _ in range(repetitions):
            con.execute(sql).fetchall()
        resultats[libelle] = (time.perf_counter() - debut) / repetitions * 1000
    return resultats


def exporter_dump(df):
    """Dump SQL compatible PostgreSQL (schéma + données + index)."""
    lignes = [
        "-- GénoPed — dump de la base des dossiers patients",
        "-- Compatible PostgreSQL. Import : psql -U <user> -d <base> -f genoped_dump.sql",
        "",
        "DROP TABLE IF EXISTS patients;",
        "",
        "CREATE TABLE patients (",
        "  id SERIAL PRIMARY KEY,",
    ]
    lignes += [f"  {c} {type_sql(c)}," for c in df.columns[:-1]]
    lignes.append(f"  {df.columns[-1]} {type_sql(df.columns[-1])}")
    lignes += [");", ""]

    cols = ", ".join(df.columns)
    valeurs = []
    for ligne in df.itertuples(index=False, name=None):
        morceaux = []
        for col, val in zip(df.columns, ligne):
            if col in NUMERIQUES or col in SYMPTOMES:
                morceaux.append(str(val))
            else:
                morceaux.append("'" + str(val).replace("'", "''") + "'")
        valeurs.append("(" + ", ".join(morceaux) + ")")

    for i in range(0, len(valeurs), 500):   # insertions par lots de 500
        paquet = ",\n".join(valeurs[i:i + 500])
        lignes.append(f"INSERT INTO patients ({cols}) VALUES\n{paquet};\n")

    lignes += [
        "-- Index (version optimisée)",
        "CREATE INDEX idx_patients_maladie ON patients(sous_classe_diagnostique);",
        "CREATE INDEX idx_patients_detresse ON patients(detresse_respiratoire);",
        "CREATE INDEX idx_patients_maladie_detresse ON patients(sous_classe_diagnostique, detresse_respiratoire);",
        "-- Index couvrant : accelere les agregats par maladie sans relire la table",
        "CREATE INDEX idx_patients_maladie_age ON patients(sous_classe_diagnostique, age_patient);",
        "",
    ]
    with open(DUMP, "w", encoding="utf-8") as f:
        f.write("\n".join(lignes))
    return os.path.getsize(DUMP)


def main():
    df = charger()
    print(f"Donnees chargees : {len(df)} lignes, {len(df.columns)} colonnes")

    con = creer_base(df)
    total = con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    print(f"Base creee : {BASE}  ({total} lignes inserees)\n")

    avant = mesurer(con)
    con.execute("CREATE INDEX idx_patients_maladie ON patients(sous_classe_diagnostique)")
    con.execute("CREATE INDEX idx_patients_detresse ON patients(detresse_respiratoire)")
    con.execute("CREATE INDEX idx_patients_maladie_detresse "
                "ON patients(sous_classe_diagnostique, detresse_respiratoire)")
    # Index « couvrant » : contient à la fois la clé de regroupement et la colonne agrégée,
    # ce qui évite d'aller relire chaque ligne de la table pour le GROUP BY.
    con.execute("CREATE INDEX idx_patients_maladie_age "
                "ON patients(sous_classe_diagnostique, age_patient)")
    con.commit()
    apres = mesurer(con)

    print("Comparaison des temps d'execution (moyenne sur 40 executions)")
    print(f"{'Requete':30} {'Non optimise':>14} {'Optimise':>12} {'Gain':>10}")
    for libelle, _ in REQUETES:
        a, b = avant[libelle], apres[libelle]
        gain = (a - b) / a * 100 if a else 0
        print(f"{libelle:30} {a:11.3f} ms {b:9.3f} ms {gain:9.1f} %")

    con.close()
    taille = exporter_dump(df)
    print(f"\nDump SQL exporte : {DUMP}  ({taille/1e6:.1f} Mo)")


if __name__ == "__main__":
    main()
