import pandas as pd
from datetime import date, timedelta
from app.database import SessionLocal
from app.models.station import Station
from app.models.mesure import Mesure
from app.models.indicateur_journalier import IndicateurJournalier

TEMP_BASE_GDD = 10  # température de base pour le calcul des degrés-jours (courant pour céréales)

# Un indicateur déjà calculé pour un jour antérieur à cette fenêtre est considéré
# stable (les mesures "Mesuré" de cette période ne changent plus) : inutile de le
# recalculer/réécrire à chaque démarrage. Fenêtre volontairement large (au-delà des
# rolling 7j/30j) pour couvrir les mesures encore en "Prévision" qui se confirment
# après coup, ou des corrections tardives.
FENETRE_RECALCUL_JOURS = 45

# Inutile de recharger 10 ans de mesures en mémoire à chaque démarrage : les rolling
# 7j/30j et le cumul saison n'ont besoin que de la saison agricole en cours (≤ 365
# jours) + une marge pour la continuité des jours sans pluie. Large marge de sécurité.
FENETRE_CHARGEMENT_JOURS = 400


def _debut_saison_agricole(annee_reference):
    """Saison agricole marocaine typique : débute le 1er septembre."""
    if pd.Timestamp.now().month >= 9:
        return date(pd.Timestamp.now().year, 9, 1)
    return date(pd.Timestamp.now().year - 1, 9, 1)


def calculer_indicateurs(log=print):
    session = SessionLocal()
    stations = session.query(Station).filter_by(actif=True).all()

    debut_saison = _debut_saison_agricole(pd.Timestamp.now().year)
    total_calcule = 0

    date_limite_chargement = date.today() - timedelta(days=FENETRE_CHARGEMENT_JOURS)

    for station in stations:
        # Seules les mesures confirmées ("Mesuré") alimentent les indicateurs : une
        # "Prévision" pas encore remplacée par la vraie mesure ne doit pas fausser les
        # cumuls de pluie, le bilan hydrique ou les jours sans pluie.
        mesures = session.query(Mesure).filter(
            Mesure.station_id == station.id,
            Mesure.date_heure >= date_limite_chargement,
            Mesure.type_donnee == "Mesuré",
        ).order_by(Mesure.date_heure).all()

        if not mesures:
            continue

        df = pd.DataFrame([{
            "date": m.date_heure.date(),
            "pluie": m.pluie or 0,
            "eto": m.eto or 0,
            "temp_min": m.temperature_min,
            "temp_max": m.temperature_max,
            "temp_moy": m.temperature,
        } for m in mesures])

        df = df.groupby("date", as_index=False).agg({
            "pluie": "sum", "eto": "sum",
            "temp_min": "min", "temp_max": "max", "temp_moy": "mean"
        }).sort_values("date").reset_index(drop=True)

        df["cumul_pluie_7j"] = df["pluie"].rolling(window=7, min_periods=1).sum()
        df["cumul_pluie_30j"] = df["pluie"].rolling(window=30, min_periods=1).sum()
        df["cumul_eto_7j"] = df["eto"].rolling(window=7, min_periods=1).sum()
        df["bilan_hydrique_7j"] = df["cumul_pluie_7j"] - df["cumul_eto_7j"]

        # Cumul pluie depuis le début de la saison agricole
        df_saison = df[df["date"] >= debut_saison].copy()
        df_saison["cumul_pluie_saison"] = df_saison["pluie"].cumsum()
        df = df.merge(df_saison[["date", "cumul_pluie_saison"]], on="date", how="left")

        # Jours consécutifs sans pluie
        jours_sans_pluie = []
        compteur = 0
        for pluie in df["pluie"]:
            compteur = compteur + 1 if pluie == 0 else 0
            jours_sans_pluie.append(compteur)
        df["jours_sans_pluie"] = jours_sans_pluie

        # Gel et stress thermique
        df["gel_detecte"] = df["temp_min"] < 0
        df["stress_thermique"] = df["temp_max"] > 38

        # Degrés-jours de croissance (GDD), cumulés depuis le début de saison
        df["gdd_jour"] = (df["temp_moy"] - TEMP_BASE_GDD).clip(lower=0)
        df_saison_gdd = df[df["date"] >= debut_saison].copy()
        df_saison_gdd["gdd_cumule_saison"] = df_saison_gdd["gdd_jour"].cumsum()
        df = df.merge(df_saison_gdd[["date", "gdd_cumule_saison"]], on="date", how="left")

        dates_existantes = {
            d for (d,) in session.query(IndicateurJournalier.date)
            .filter(IndicateurJournalier.station_id == station.id).all()
        }
        date_limite_recalcul = date.today() - timedelta(days=FENETRE_RECALCUL_JOURS)

        nb_ignores = 0
        for _, ligne in df.iterrows():
            if ligne["date"] in dates_existantes and ligne["date"] < date_limite_recalcul:
                nb_ignores += 1
                continue

            session.query(IndicateurJournalier).filter(
                IndicateurJournalier.station_id == station.id,
                IndicateurJournalier.date == ligne["date"]
            ).delete()

            session.add(IndicateurJournalier(
                station_id=station.id,
                date=ligne["date"],
                cumul_pluie_7j=ligne["cumul_pluie_7j"],
                cumul_pluie_30j=ligne["cumul_pluie_30j"],
                cumul_pluie_saison=ligne["cumul_pluie_saison"] if pd.notna(ligne["cumul_pluie_saison"]) else None,
                cumul_eto_7j=ligne["cumul_eto_7j"],
                bilan_hydrique_7j=ligne["bilan_hydrique_7j"],
                jours_sans_pluie=int(ligne["jours_sans_pluie"]),
                gel_detecte=bool(ligne["gel_detecte"]) if pd.notna(ligne["gel_detecte"]) else False,
                stress_thermique=bool(ligne["stress_thermique"]) if pd.notna(ligne["stress_thermique"]) else False,
                gdd_jour=ligne["gdd_jour"] if pd.notna(ligne["gdd_jour"]) else None,
                gdd_cumule_saison=ligne["gdd_cumule_saison"] if pd.notna(ligne["gdd_cumule_saison"]) else None,
            ))
            total_calcule += 1

        session.commit()
        log(f"{station.nom} : {len(df) - nb_ignores} jour(s) (re)calculé(s), {nb_ignores} déjà stable(s) ignoré(s).")

    session.close()
    log(f"Calcul terminé : {total_calcule} indicateur(s) journalier(s) mis à jour.")
    return total_calcule