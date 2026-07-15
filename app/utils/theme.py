"""Palette et helpers de mise en page partagés par toutes les pages.

Style plat, sans cartes-boîtes ni ombres portées ni badges d'icônes emoji :
sections structurées par la typographie (titre + règle de couleur) et des
séparateurs fins, plutôt que par des rectangles blancs superposés.
"""
from PySide6.QtWidgets import QVBoxLayout, QLabel, QFrame

COULEURS = {
    "primaire": "#1a5276",
    "succes": "#27ae60",
    "attention": "#e67e22",
    "danger": "#c0392b",
    "info": "#3498db",
    "violet": "#8e44ad",
    "neutre": "#7f8c8d",
    "fond": "#f4f6f8",
    "texte": "#2c3e50",
}


def titre_section(texte, couleur=None):
    """Titre de section flanqué d'une règle inférieure — remplace la carte-boîte
    blanche avec ombre par une structure typographique. Retourne (QVBoxLayout, QLabel)."""
    couleur = couleur or COULEURS["primaire"]
    bloc = QVBoxLayout()
    bloc.setSpacing(8)
    label = QLabel(texte)
    label.setStyleSheet(f"font-weight: 700; color: {COULEURS['texte']}; font-size: 13.5px; border: none;")
    bloc.addWidget(label)
    regle = QFrame()
    regle.setFixedHeight(2)
    regle.setStyleSheet(f"background-color: {couleur}; border: none;")
    bloc.addWidget(regle)
    return bloc, label


def diviseur_vertical():
    diviseur = QFrame()
    diviseur.setFixedWidth(1)
    diviseur.setStyleSheet("background-color: #e3e7eb; border: none;")
    return diviseur


def diviseur_horizontal():
    diviseur = QFrame()
    diviseur.setFixedHeight(1)
    diviseur.setStyleSheet("background-color: #e3e7eb; border: none;")
    return diviseur
