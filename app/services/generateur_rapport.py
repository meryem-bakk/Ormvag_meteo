import os
import pandas as pd
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure

# Palette sobre : le bleu ORMVAG n'est utilisé qu'en accent (titre, bordures, surbrillance),
# jamais en aplat large, pour éviter un rendu trop "chargé".
COULEUR_TITRE = colors.HexColor("#2c3e50")
COULEUR_SOUS_TITRE = colors.HexColor("#3d5a70")
COULEUR_TEXTE_SECONDAIRE = colors.HexColor("#8a97a0")
COULEUR_ENTETE_FOND = colors.HexColor("#e9edf1")
COULEUR_ENTETE_TEXTE = colors.HexColor("#2c3e50")
COULEUR_PROVINCE_FOND = colors.HexColor("#dde6ed")
COULEUR_RAYURE = colors.HexColor("#f7f8fa")
COULEUR_GRILLE = colors.HexColor("#e2e5e8")
COULEUR_ACCENT = colors.HexColor("#5d7a94")
COULEUR_SURBRILLANCE = colors.HexColor("#dee9f2")
COULEUR_SEPARATEUR_REGION = colors.HexColor("#aebac3")


def _style_meta(styles):
    """Style pour les lignes d'information secondaires (période, date de génération)."""
    return ParagraphStyle("MetaORMVAG", parent=styles["Normal"], fontSize=10,
                           textColor=colors.black, leading=13)


def _style_sous_titre(styles):
    """Style pour le sous-titre décrivant le contenu du rapport."""
    return ParagraphStyle("SousTitreORMVAG", parent=styles["Heading2"], fontSize=14,
                           textColor=COULEUR_SOUS_TITRE, spaceBefore=2, spaceAfter=6)


def recuperer_donnees(station_ids, date_debut, date_fin):
    session = SessionLocal()

    requete = session.query(Mesure).filter(
        Mesure.date_heure >= date_debut,
        Mesure.date_heure <= date_fin,
    )
    if station_ids:
        requete = requete.filter(Mesure.station_id.in_(station_ids))

    mesures = requete.order_by(Mesure.station_id, Mesure.date_heure).all()

    lignes = []
    for m in mesures:
        lignes.append({
            "Station": m.station.nom,
            "Province": m.station.province or "Non classée",
            "Date": m.date_heure.strftime("%d/%m/%Y"),
            "Type": m.type_donnee or "—",
            "ETo (mm)": m.eto,
            "Pluie (mm)": m.pluie,
            "Temp. min (°C)": m.temperature_min,
            "Temp. moy (°C)": m.temperature,
            "Temp. max (°C)": m.temperature_max,
            "Hum. moy (%)": m.humidite,
            "Vent (km/h)": m.vent,
        })

    session.close()

    df = pd.DataFrame(lignes)
    if not df.empty:
        df = df.sort_values("Province", kind="stable").reset_index(drop=True)
    return df


_POIDS_COLONNES = {
    "Station": 2.6, "Province": 1.4, "Date": 1.7, "Type": 1.2,
    "Stations par région": 2.8,
    "Temp. moyenne (°C)": 1.3, "Hum. moyenne (%)": 1.3, "Vent moyen (km/h)": 1.2,
}


def _element_tableau(df, largeur_disponible, taille_police=7.5, styles_supplementaires=None,
                      lignes_en_gras=None):
    """Construit un tableau PDF unique à partir du DataFrame (colonne Province incluse),
    avec des largeurs de colonnes adaptées et un retour à la ligne du texte long."""
    lignes_en_gras = set(lignes_en_gras or [])

    style_entete = ParagraphStyle(
        "EnteteTableau", fontName="Helvetica-Bold", fontSize=taille_police,
        leading=taille_police + 2, textColor=COULEUR_ENTETE_TEXTE, alignment=1,
    )
    style_cellule = ParagraphStyle(
        "CelluleTableau", fontName="Helvetica", fontSize=taille_police,
        leading=taille_police + 2, alignment=1,
    )
    style_cellule_gras = ParagraphStyle(
        "CelluleTableauGras", fontName="Helvetica-Bold", fontSize=taille_police,
        leading=taille_police + 2, alignment=1,
    )

    colonnes = df.columns.tolist()
    entete = [Paragraph(str(c), style_entete) for c in colonnes]
    corps = []
    for i, ligne in enumerate(df.astype(str).values.tolist()):
        style = style_cellule_gras if i in lignes_en_gras else style_cellule
        corps.append([Paragraph(v, style) for v in ligne])
    donnees_tableau = [entete] + corps

    poids = [_POIDS_COLONNES.get(c, 1.0) for c in colonnes]
    poids_total = sum(poids)
    largeurs_colonnes = [largeur_disponible * p / poids_total for p in poids]

    tableau = Table(donnees_tableau, colWidths=largeurs_colonnes, repeatRows=1)

    style_liste = [
        ("BACKGROUND", (0, 0), (-1, 0), COULEUR_ENTETE_FOND),
        ("LINEBELOW", (0, 0), (-1, 0), 1, COULEUR_ACCENT),
        ("FONTSIZE", (0, 0), (-1, -1), taille_police),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COULEUR_RAYURE]),
        ("GRID", (0, 0), (-1, -1), 0.4, COULEUR_GRILLE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if styles_supplementaires:
        style_liste.extend(styles_supplementaires)
    tableau.setStyle(TableStyle(style_liste))

    return [tableau]


# Pour la ligne de synthèse régionale : la moyenne n'est pertinente que pour les taux
# (températures moyennes, cumuls d'eau). Les extrêmes de température doivent remonter le
# record absolu de la région (pas une moyenne d'extrêmes), et les compteurs de jours
# (pluie, gel, stress) doivent remonter le pire cas plutôt qu'une moyenne peu rigoureuse.
_COLONNES_MAX_ABSOLU = {"Temp. max (°C)"}
_COLONNES_MIN_ABSOLU = {"Temp. min (°C)"}
_COLONNES_MAX_COMPTEUR = {"Jours de pluie", "Jours de gel", "Jours de stress thermique"}


def construire_tableau_groupe_par_province(df):
    """Transforme un DataFrame (une ligne par station, colonnes Station + Province +
    métriques) en un tableau unique groupé par province : une ligne d'en-tête de région,
    les stations, puis une ligne "Synthèse région" (moyenne pour les taux/cumuls, extrême
    absolu pour les températures min/max, maximum pour les compteurs de jours — une
    moyenne n'a pas de sens pour ceux-ci). Utilisé par le rapport de synthèse et le
    rapport journalier, pour une présentation cohérente entre les rapports.
    Retourne (df_groupe, indices_entete, indices_synthese) — les indices repèrent les
    lignes spéciales dans df_groupe pour une mise en forme particulière (PDF)."""
    if df.empty:
        return df, [], []

    colonnes_metriques = [c for c in df.columns if c not in ("Station", "Province")]
    lignes = []
    indices_entete = []
    indices_synthese = []

    for province, groupe in df.groupby("Province", sort=True):
        indices_entete.append(len(lignes))
        ligne_entete = {"Stations par région": province}
        for c in colonnes_metriques:
            ligne_entete[c] = ""
        lignes.append(ligne_entete)

        for _, station_ligne in groupe.iterrows():
            ligne = {"Stations par région": station_ligne["Station"]}
            for c in colonnes_metriques:
                ligne[c] = station_ligne[c]
            lignes.append(ligne)

        indices_synthese.append(len(lignes))
        ligne_synthese = {"Stations par région": "Synthèse région"}
        for c in colonnes_metriques:
            valeurs = groupe[c].dropna()
            if valeurs.empty:
                ligne_synthese[c] = None
            elif c in _COLONNES_MAX_ABSOLU or c in _COLONNES_MAX_COMPTEUR:
                ligne_synthese[c] = round(valeurs.max(), 1)
            elif c in _COLONNES_MIN_ABSOLU:
                ligne_synthese[c] = round(valeurs.min(), 1)
            else:
                ligne_synthese[c] = round(valeurs.mean(), 1)
        lignes.append(ligne_synthese)

    return pd.DataFrame(lignes), indices_entete, indices_synthese


def generer_excel_synthese(chemin_sortie, df_synthese):
    df_groupe, _, _ = construire_tableau_groupe_par_province(df_synthese)
    generer_excel(chemin_sortie, df_groupe)


def generer_csv_synthese(chemin_sortie, df_synthese):
    df_groupe, _, _ = construire_tableau_groupe_par_province(df_synthese)
    generer_csv(chemin_sortie, df_groupe)


def generer_pdf(chemin_sortie, titre, date_debut, date_fin, df):
    doc = SimpleDocTemplate(chemin_sortie, pagesize=A4,
                             topMargin=1.5*cm, bottomMargin=1.5*cm,
                             leftMargin=1.5*cm, rightMargin=1.5*cm)
    elements = []
    styles = getSampleStyleSheet()

    style_titre = ParagraphStyle("TitreORMVAG", parent=styles["Title"], textColor=COULEUR_TITRE)
    style_meta = _style_meta(styles)
    elements.append(Paragraph("ORMVAG — Rapport météorologique", style_titre))
    elements.append(Paragraph(titre, _style_sous_titre(styles)))
    elements.append(Paragraph(
        f"Période : {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
        style_meta
    ))
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", style_meta))
    elements.append(Spacer(1, 0.8*cm))

    if df.empty:
        elements.append(Paragraph("Aucune donnée disponible pour cette sélection.", styles["Normal"]))
    else:
        largeur_disponible = A4[0] - 3*cm
        elements.extend(_element_tableau(df.round(1), largeur_disponible, taille_police=7.5))

    doc.build(elements)


def generer_excel(chemin_sortie, df):
    df.to_excel(chemin_sortie, index=False, engine="openpyxl")


def generer_csv(chemin_sortie, df):
    df.to_csv(chemin_sortie, index=False, sep=";", encoding="utf-8-sig")

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reportlab.platypus import Image
from app.models.indicateur_journalier import IndicateurJournalier


def recuperer_synthese(station_ids, date_debut, date_fin):
    session = SessionLocal()

    requete_stations = session.query(Station).filter_by(actif=True)
    if station_ids:
        requete_stations = requete_stations.filter(Station.id.in_(station_ids))
    stations = requete_stations.order_by(Station.province, Station.nom).all()

    lignes = []
    for station in stations:
        mesures = session.query(Mesure).filter(
            Mesure.station_id == station.id,
            Mesure.date_heure >= date_debut,
            Mesure.date_heure <= date_fin,
        ).all()

        if not mesures:
            continue

        temperatures = [m.temperature for m in mesures if m.temperature is not None]
        temp_mins = [m.temperature_min for m in mesures if m.temperature_min is not None]
        temp_maxs = [m.temperature_max for m in mesures if m.temperature_max is not None]
        pluies = [m.pluie or 0 for m in mesures]
        etos = [m.eto or 0 for m in mesures]

        indicateurs = session.query(IndicateurJournalier).filter(
            IndicateurJournalier.station_id == station.id,
            IndicateurJournalier.date >= date_debut.date(),
            IndicateurJournalier.date <= date_fin.date(),
        ).all()

        nb_jours_gel = sum(1 for i in indicateurs if i.gel_detecte)
        nb_jours_stress = sum(1 for i in indicateurs if i.stress_thermique)
        gdd_cumule = sum(i.gdd_jour or 0 for i in indicateurs)

        cumul_pluie = sum(pluies)
        cumul_eto = sum(etos)

        lignes.append({
            "Station": station.nom,
            "Province": station.province or "Non classée",
            "Temp. moyenne (°C)": round(sum(temperatures) / len(temperatures), 1) if temperatures else None,
            "Temp. min (°C)": round(min(temp_mins), 1) if temp_mins else None,
            "Temp. max (°C)": round(max(temp_maxs), 1) if temp_maxs else None,
            "Cumul pluie (mm)": round(cumul_pluie, 1),
            "Jours de pluie": sum(1 for p in pluies if p > 0),
            "Cumul ETo (mm)": round(cumul_eto, 1),
            "Bilan hydrique (mm)": round(cumul_pluie - cumul_eto, 1),
            "Jours de gel": nb_jours_gel,
            "Jours de stress thermique": nb_jours_stress,
            "GDD cumulé": round(gdd_cumule, 0),
        })

    session.close()
    return pd.DataFrame(lignes)


def generer_graphique_temperature(station_ids, date_debut, date_fin):
    from sqlalchemy.orm import joinedload

    session = SessionLocal()

    requete = session.query(Mesure).options(joinedload(Mesure.station)).filter(
        Mesure.date_heure >= date_debut,
        Mesure.date_heure <= date_fin,
    )
    if station_ids:
        requete = requete.filter(Mesure.station_id.in_(station_ids))
    mesures = requete.order_by(Mesure.date_heure).all()

    if not mesures:
        session.close()
        return None

    df = pd.DataFrame([{
        "date": m.date_heure.date(),
        "station": m.station.nom,
        "temperature": m.temperature,
        "pluie": m.pluie or 0,
    } for m in mesures])

    session.close()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 5.2), sharex=True)

    # Palette à 20 couleurs distinctes : le cycle par défaut (10 couleurs) fait
    # sinon se confondre certaines stations dès qu'il y en a plus de 10.
    noms_stations = sorted(df["station"].unique())
    couleurs_stations = plt.get_cmap("tab20").colors
    for i, nom_station in enumerate(noms_stations):
        groupe = df[df["station"] == nom_station]
        ax1.plot(groupe["date"], groupe["temperature"], label=nom_station, linewidth=1.4,
                  color=couleurs_stations[i % len(couleurs_stations)])
    ax1.set_ylabel("Température (°C)", fontsize=8)
    ax1.legend(fontsize=5.5, loc="upper center", bbox_to_anchor=(0.5, 1.35), ncol=3)
    ax1.tick_params(labelsize=7)
    ax1.grid(alpha=0.2)

    cumul_par_jour = df.groupby("date")["pluie"].sum()
    ax2.bar(cumul_par_jour.index, cumul_par_jour.values, color="#5d7a94", width=0.8)
    ax2.set_ylabel("Pluie cumulée (mm)", fontsize=8)
    ax2.tick_params(labelsize=7, rotation=30)
    ax2.grid(alpha=0.2)

    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    buffer.seek(0)
    return buffer


def generer_pdf_synthese(chemin_sortie, date_debut, date_fin, df_synthese, graphique_buffer):
    from reportlab.lib.pagesizes import landscape

    doc = SimpleDocTemplate(chemin_sortie, pagesize=landscape(A4),
                             topMargin=1.2*cm, bottomMargin=1.2*cm,
                             leftMargin=1.2*cm, rightMargin=1.2*cm)
    elements = []
    styles = getSampleStyleSheet()

    style_titre = ParagraphStyle("TitreORMVAG", parent=styles["Title"], textColor=COULEUR_TITRE)
    style_meta = _style_meta(styles)
    elements.append(Paragraph("ORMVAG — Rapport de synthèse agroclimatique", style_titre))
    elements.append(Paragraph(
        f"Période : {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
        style_meta
    ))
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", style_meta))
    elements.append(Spacer(1, 0.6*cm))

    if df_synthese.empty:
        elements.append(Paragraph("Aucune donnée disponible pour cette sélection.", style_meta))
    else:
        df_groupe, indices_entete, indices_synthese = construire_tableau_groupe_par_province(df_synthese)

        styles_supplementaires = []
        for i in indices_entete:
            r = i + 1  # +1 car la ligne d'en-tête de colonnes occupe la ligne 0 du tableau
            styles_supplementaires.append(("BACKGROUND", (0, r), (-1, r), COULEUR_PROVINCE_FOND))
            styles_supplementaires.append(("LINEABOVE", (0, r), (-1, r), 1, COULEUR_SEPARATEUR_REGION))
        for i in indices_synthese:
            r = i + 1
            styles_supplementaires.append(("LINEABOVE", (0, r), (-1, r), 0.75, COULEUR_ACCENT))

        largeur_disponible = landscape(A4)[0] - 2.4*cm
        elements.extend(_element_tableau(
            df_groupe, largeur_disponible, taille_police=8,
            styles_supplementaires=styles_supplementaires,
            lignes_en_gras=indices_entete + indices_synthese,
        ))
        if graphique_buffer:
            elements.append(PageBreak())
            elements.append(Paragraph("Évolution sur la période", _style_sous_titre(styles)))
            elements.append(Image(graphique_buffer, width=16*cm, height=11*cm))

    doc.build(elements)


def recuperer_rapport_journalier(date_fin=None):
    """Synthèse des dernières 24h par station, triée par cumul de pluie décroissant."""
    if date_fin is None:
        date_fin = datetime.now()
    date_debut = date_fin - timedelta(hours=24)
    date_debut_30j = date_fin - timedelta(days=30)

    session = SessionLocal()
    stations = session.query(Station).filter_by(actif=True).order_by(Station.province, Station.nom).all()

    lignes = []
    for station in stations:
        mesures_30j = session.query(Mesure).filter(
            Mesure.station_id == station.id,
            Mesure.date_heure >= date_debut_30j,
            Mesure.date_heure <= date_fin,
        ).all()

        if not mesures_30j:
            continue

        mesures = [m for m in mesures_30j if m.date_heure >= date_debut]
        if not mesures:
            continue

        temperatures = [m.temperature for m in mesures if m.temperature is not None]
        temp_mins = [m.temperature_min for m in mesures if m.temperature_min is not None]
        temp_maxs = [m.temperature_max for m in mesures if m.temperature_max is not None]
        humidites = [m.humidite for m in mesures if m.humidite is not None]
        vents = [m.vent for m in mesures if m.vent is not None]
        pluies = [m.pluie or 0 for m in mesures]
        pluies_30j = [m.pluie or 0 for m in mesures_30j]

        lignes.append({
            "Station": station.nom,
            "Province": station.province or "Non classée",
            "Cumul pluie 24h (mm)": round(float(sum(pluies)), 1),
            "Cumul pluie 30j (mm)": round(sum(pluies_30j), 1),
            "Temp. min (°C)": round(min(temp_mins), 1) if temp_mins else None,
            "Temp. moyenne (°C)": round(sum(temperatures) / len(temperatures), 1) if temperatures else None,
            "Temp. max (°C)": round(max(temp_maxs), 1) if temp_maxs else None,
            "Hum. moyenne (%)": round(sum(humidites) / len(humidites), 1) if humidites else None,
            "Vent moyen (km/h)": round(sum(vents) / len(vents), 1) if vents else None,
        })

    session.close()

    df = pd.DataFrame(lignes)
    if not df.empty:
        df = df.sort_values(["Province", "Cumul pluie 24h (mm)"], ascending=[True, False]).reset_index(drop=True)
    return df, date_debut, date_fin


def generer_pdf_rapport_journalier(chemin_sortie, df, date_debut, date_fin):
    doc = SimpleDocTemplate(chemin_sortie, pagesize=A4,
                             topMargin=1.5*cm, bottomMargin=1.5*cm,
                             leftMargin=1.5*cm, rightMargin=1.5*cm)
    elements = []
    styles = getSampleStyleSheet()

    style_titre = ParagraphStyle("TitreORMVAG", parent=styles["Title"], textColor=COULEUR_TITRE)
    style_meta = _style_meta(styles)
    elements.append(Paragraph("ORMVAG — Rapport météorologique journalier", style_titre))
    elements.append(Paragraph(
        f"Période couverte : {date_debut.strftime('%d/%m/%Y %H:%M')} → {date_fin.strftime('%d/%m/%Y %H:%M')} (24 dernières heures)",
        style_meta
    ))
    elements.append(Paragraph(f"Généré automatiquement le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", style_meta))
    elements.append(Spacer(1, 0.6*cm))

    if df.empty:
        elements.append(Paragraph("Aucune mesure reçue sur les dernières 24 heures.", style_meta))
    else:
        cumul_reseau = df["Cumul pluie 24h (mm)"].sum()
        nb_stations_pluie = int((df["Cumul pluie 24h (mm)"] > 0).sum())
        elements.append(Paragraph(
            f"Cumul de précipitations réseau ({len(df)} stations) : <b>{cumul_reseau:.1f} mm</b>",
            _style_sous_titre(styles)
        ))
        elements.append(Paragraph(
            f"{nb_stations_pluie} station(s) sur {len(df)} ont enregistré de la pluie sur la période.",
            style_meta
        ))
        elements.append(Spacer(1, 0.4*cm))

        df_groupe, indices_entete, indices_synthese = construire_tableau_groupe_par_province(df)

        styles_supplementaires = [("BACKGROUND", (1, 1), (1, -1), COULEUR_SURBRILLANCE)]
        for i in indices_entete:
            r = i + 1
            styles_supplementaires.append(("BACKGROUND", (0, r), (-1, r), COULEUR_PROVINCE_FOND))
            styles_supplementaires.append(("LINEABOVE", (0, r), (-1, r), 1, COULEUR_SEPARATEUR_REGION))
        for i in indices_synthese:
            r = i + 1
            styles_supplementaires.append(("LINEABOVE", (0, r), (-1, r), 0.75, COULEUR_ACCENT))

        largeur_disponible = A4[0] - 3*cm
        elements.extend(_element_tableau(
            df_groupe, largeur_disponible, taille_police=8,
            styles_supplementaires=styles_supplementaires,
            lignes_en_gras=indices_entete + indices_synthese,
        ))

    doc.build(elements)


def generer_rapport_journalier_pdf(dossier_sortie="Rapports"):
    """Génère le PDF du rapport journalier (24h, axé pluie) et retourne (chemin, df)."""
    df, date_debut, date_fin = recuperer_rapport_journalier()
    os.makedirs(dossier_sortie, exist_ok=True)
    nom_fichier = f"rapport_journalier_{date_fin.strftime('%Y%m%d_%H%M')}.pdf"
    chemin = os.path.join(dossier_sortie, nom_fichier)
    generer_pdf_rapport_journalier(chemin, df, date_debut, date_fin)
    return chemin, df