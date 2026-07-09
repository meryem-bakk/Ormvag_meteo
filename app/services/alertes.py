from dataclasses import dataclass
from typing import List, Optional

SEUIL_CANICULE = 40.0      # °C
SEUIL_VENT_FORT = 40.0     # km/h
SEUIL_HUMIDITE = 95.0      # %

# Détection d'anomalies capteur
PLAGE_TEMP_MIN = -20.0
PLAGE_TEMP_MAX = 55.0
ECART_MAX_VS_VOISINS = 15.0  # °C d'écart jugé suspect vs moyenne récente


@dataclass
class Alerte:
    type: str
    icone: str
    message: str
    niveau: str   # "danger" ou "warning"
    couleur: str


def detecter_alertes(temp_max: Optional[float], vent_vitesse: Optional[float], humidite: Optional[float]) -> List[Alerte]:
    """Retourne la liste des alertes actives à partir des dernières valeurs mesurées."""
    alertes = []

    if temp_max is not None and temp_max > SEUIL_CANICULE:
        alertes.append(Alerte(
            type="canicule", icone="🔥",
            message=f"Alerte canicule — Tmax = {temp_max:.1f}°C",
            niveau="danger", couleur="#c0392b"
        ))

    if vent_vitesse is not None and vent_vitesse > SEUIL_VENT_FORT:
        alertes.append(Alerte(
            type="vent_fort", icone="💨",
            message=f"Alerte vent fort — {vent_vitesse:.1f} km/h",
            niveau="warning", couleur="#e67e22"
        ))

    if humidite is not None and humidite > SEUIL_HUMIDITE:
        alertes.append(Alerte(
            type="risque_maladie", icone="🦠",
            message=f"Risque de maladies fongiques — HR = {humidite:.1f}%",
            niveau="warning", couleur="#8e44ad"
        ))

    return alertes


@dataclass
class Anomalie:
    index: int
    valeur: float
    raison: str


def detecter_anomalies_temperature(valeurs: List[Optional[float]]) -> List[Anomalie]:
    """
    Détecte des valeurs de température suspectes (erreur capteur) dans une série
    ordonnée chronologiquement.
    Deux règles :
      1. Hors plage physiquement plausible.
      2. Écart brutal par rapport à la moyenne des 3 valeurs précédentes.
    """
    anomalies = []
    for i, v in enumerate(valeurs):
        if v is None:
            continue

        if v < PLAGE_TEMP_MIN or v > PLAGE_TEMP_MAX:
            anomalies.append(Anomalie(i, v, "hors plage physique plausible"))
            continue

        fenetre = [x for x in valeurs[max(0, i - 3):i] if x is not None]
        if fenetre:
            moyenne = sum(fenetre) / len(fenetre)
            if abs(v - moyenne) > ECART_MAX_VS_VOISINS:
                anomalies.append(Anomalie(
                    i, v, f"écart anormal ({v:.1f}°C vs moyenne récente {moyenne:.1f}°C)"
                ))

    return anomalies