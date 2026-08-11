# -*- coding: utf-8 -*-
"""Génère le compte-rendu PDF d'une analyse GP AI (téléchargeable depuis l'application)."""
import os
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

_TTF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
BLEU = (42, 93, 143)
BLEU_FONCE = (30, 68, 104)
VERT = (46, 125, 91)
GRIS = (85, 99, 111)

# raccourcis pour passer proprement à la ligne suivante (API fpdf2 >= 2.8)
_SAUT = dict(new_x=XPos.LMARGIN, new_y=YPos.NEXT)


class RapportPDF(FPDF):
    def header(self):
        self.set_fill_color(*BLEU_FONCE)
        self.rect(0, 0, self.w, 22, "F")
        self.set_xy(15, 6)
        self.set_font("DejaVu", "B", 16)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, "GP AI  ·  GénoPed", **_SAUT)
        self.set_x(15)
        self.set_font("DejaVu", "", 9)
        self.cell(0, 5, "Compte-rendu d'orientation diagnostique", **_SAUT)
        self.ln(6)
        self.set_text_color(30, 30, 30)

    def footer(self):
        self.set_y(-15)
        self.set_x(15)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(*GRIS)
        self.multi_cell(0, 4,
            "Document d'aide à l'orientation — ne constitue pas un diagnostic. "
            f"Modèle : Forêt aléatoire (Top-3 accuracy 87 %).   Page {self.page_no()}",
            align="C")


def _ligne(pdf, texte, taille=10, gras=False, couleur=(30, 30, 30)):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("DejaVu", "B" if gras else "", taille)
    pdf.set_text_color(*couleur)
    pdf.multi_cell(0, 5, texte, **_SAUT)


def _titre_section(pdf, texte):
    pdf.ln(2)
    _ligne(pdf, texte, taille=12, gras=True, couleur=BLEU_FONCE)
    pdf.set_text_color(30, 30, 30)


def generer_pdf(rapport):
    """`rapport` = dict {date, praticien, symptomes_presents, resultats, autres, comparaison}."""
    pdf = RapportPDF(format="A4")
    pdf.add_font("DejaVu", "", os.path.join(_TTF, "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", os.path.join(_TTF, "DejaVuSans-Bold.ttf"))
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    prat = rapport.get("praticien") or {}
    nom = ("Dr. " + prat.get("prenom", "") + " " + prat.get("nom", "")).strip()
    _ligne(pdf, "Praticien : " + (nom or "—") + "     Établissement : "
           + prat.get("etablissement", "—"), couleur=GRIS)
    _ligne(pdf, "Date de l'analyse : " + rapport.get("date", ""), couleur=GRIS)
    pdf.ln(1)

    pdf.set_x(pdf.l_margin)
    pdf.set_fill_color(255, 246, 229)
    pdf.set_font("DejaVu", "", 9)
    pdf.multi_cell(0, 5,
        "Avertissement : cet outil est une aide à l'orientation. Il propose des pistes à confirmer "
        "par un professionnel de santé et un test génétique. Il ne pose pas de diagnostic.",
        fill=True, **_SAUT)

    _titre_section(pdf, "Signes cliniques renseignés")
    symptomes = rapport.get("symptomes_presents") or []
    _ligne(pdf, "Symptômes observés : " +
           (", ".join(symptomes) if symptomes else "aucun symptôme coché."))

    _titre_section(pdf, "Diagnostics les plus probables")
    for i, r in enumerate(rapport.get("resultats", []), start=1):
        _ligne(pdf, f"{i}. {r['maladie']}  —  {r['probabilite']} %",
               taille=11, gras=True, couleur=(VERT if i == 1 else BLEU))
        if r.get("description"):
            _ligne(pdf, r["description"], taille=9)
        if r.get("examens"):
            _ligne(pdf, "Examens de confirmation à envisager :", taille=9, gras=True)
            for e in r["examens"]:
                _ligne(pdf, "  •  " + e, taille=9)
        pdf.ln(1)

    if rapport.get("autres") is not None:
        _ligne(pdf, f"Les autres maladies cumulent {rapport['autres']} %  (total = 100 %).",
               taille=9, couleur=GRIS)

    if rapport.get("comparaison"):
        _titre_section(pdf, "Pourquoi ces trois maladies ensemble ?")
        _ligne(pdf, rapport["comparaison"], taille=9)

    return bytes(pdf.output())


def nom_fichier(rapport):
    return "compte_rendu_GP_AI_" + datetime.now().strftime("%Y%m%d_%H%M") + ".pdf"
