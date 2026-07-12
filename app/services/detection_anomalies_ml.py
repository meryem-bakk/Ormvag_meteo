"""Détection d'anomalies par apprentissage automatique (Isolation Forest),
en complément des règles de plausibilité physique déjà présentes dans alertes.py.

Le modèle est entraîné hors-ligne par ML/entrainer_detecteur_anomalies.py et
sauvegardé dans ML/detecteur_anomalies.joblib (fichier non versionné, régénérable).
Si ce fichier est absent (ex. après un clone frais du dépôt sans avoir relancé
l'entraînement), la détection ML est simplement désactivée sans erreur.
"""
import os
import joblib
import pandas as pd

CHEMIN_MODELE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "ML", "detecteur_anomalies.joblib"
)

_cache_modele = None
_modele_absent_signale = False


def _charger_modele(log=print):
    global _cache_modele, _modele_absent_signale
    if _cache_modele is not None:
        return _cache_modele

    if not os.path.exists(CHEMIN_MODELE):
        if not _modele_absent_signale:
            log(f"[detection_anomalies_ml] Modèle introuvable ({CHEMIN_MODELE}) — "
                f"détection IA désactivée. Lancer ML/entrainer_detecteur_anomalies.py pour l'activer.")
            _modele_absent_signale = True
        return None

    _cache_modele = joblib.load(CHEMIN_MODELE)
    return _cache_modele


def detecter_anomalies_mesures(mesures, station_id):
    """Score une liste de Mesure (toutes de la même station) avec le détecteur ML.
    Retourne une liste de (mesure, score) pour celles jugées anormales, triée
    des plus suspectes aux moins suspectes."""
    donnees = _charger_modele()
    if donnees is None or not mesures:
        return []

    modele = donnees["modele"]
    colonnes_features = donnees["colonnes_features"]
    ids_stations = donnees["ids_stations"]
    medianes = donnees["medianes"]

    lignes = []
    for m in mesures:
        ligne = {c: (getattr(m, c) if getattr(m, c) is not None else medianes.get(c)) for c in colonnes_features}
        for sid in ids_stations:
            ligne[f"station_{sid}"] = 1 if sid == station_id else 0
        lignes.append(ligne)

    colonnes_attendues = list(colonnes_features) + [f"station_{sid}" for sid in ids_stations]
    X = pd.DataFrame(lignes)[colonnes_attendues]

    predictions = modele.predict(X)
    scores = modele.decision_function(X)

    resultats = [(m, score) for m, pred, score in zip(mesures, predictions, scores) if pred == -1]
    resultats.sort(key=lambda t: t[1])
    return resultats
