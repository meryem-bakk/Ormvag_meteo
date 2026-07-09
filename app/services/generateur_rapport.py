import pandas as pd
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure


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
    return pd.DataFrame(lignes)


def generer_pdf(chemin_sortie, titre, date_debut, date_fin, df):
    doc = SimpleDocTemplate(chemin_sortie, pagesize=A4,
                             topMargin=1.5*cm, bottomMargin=1.5*cm,
                             leftMargin=1.5*cm, rightMargin=1.5*cm)
    elements = []
    styles = getSampleStyleSheet()

    style_titre = ParagraphStyle("TitreORMVAG", parent=styles["Title"], textColor=colors.HexColor("#1a5276"))
    elements.append(Paragraph("ORMVAG — Rapport météorologique", style_titre))
    elements.append(Paragraph(titre, styles["Heading2"]))
    elements.append(Paragraph(
        f"Période : {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
        styles["Normal"]
    ))
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.8*cm))

    if df.empty:
        elements.append(Paragraph("Aucune donnée disponible pour cette sélection.", styles["Normal"]))
    else:
        donnees_tableau = [df.columns.tolist()] + df.round(1).astype(str).values.tolist()
        tableau = Table(donnees_tableau, repeatRows=1)
        tableau.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f8")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(tableau)

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
    stations = requete_stations.all()

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
        "station": m.station.code,
        "temperature": m.temperature,
        "pluie": m.pluie or 0,
    } for m in mesures])

    session.close()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 4.5), sharex=True)

    for code_station, groupe in df.groupby("station"):
        ax1.plot(groupe["date"], groupe["temperature"], label=code_station, linewidth=1.2)
    ax1.set_ylabel("Température (°C)", fontsize=8)
    ax1.legend(fontsize=6, loc="upper right", ncol=3)
    ax1.tick_params(labelsize=7)
    ax1.grid(alpha=0.2)

    cumul_par_jour = df.groupby("date")["pluie"].sum()
    ax2.bar(cumul_par_jour.index, cumul_par_jour.values, color="#1a5276", width=0.8)
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

    style_titre = ParagraphStyle("TitreORMVAG", parent=styles["Title"], textColor=colors.HexColor("#1a5276"))
    elements.append(Paragraph("ORMVAG — Rapport de synthèse agroclimatique", style_titre))
    elements.append(Paragraph(
        f"Période : {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}",
        styles["Normal"]
    ))
    elements.append(Paragraph(f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.6*cm))

    if df_synthese.empty:
        elements.append(Paragraph("Aucune donnée disponible pour cette sélection.", styles["Normal"]))
    else:
        donnees_tableau = [df_synthese.columns.tolist()] + df_synthese.astype(str).values.tolist()
        tableau = Table(donnees_tableau, repeatRows=1)
        tableau.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f8")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(tableau)
        elements.append(Spacer(1, 0.8*cm))

        if graphique_buffer:
            elements.append(Paragraph("Évolution sur la période", styles["Heading3"]))
            elements.append(Image(graphique_buffer, width=16*cm, height=10*cm))

    doc.build(elements)