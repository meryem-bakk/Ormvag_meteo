"""Vérifie si le modèle détecte vraiment les épisodes pluvieux, plutôt que de
prédire systématiquement une valeur proche de 0 (ce qui donnerait un MAE global
trompeusement bas puisque la plupart des jours sont secs)."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from tensorflow import keras

DOSSIER = os.path.dirname(__file__)
SEUIL_PLUIE = 0.5  # mm : au-dessus, on considère qu'il "a plu" ce jour-là

donnees = np.load(os.path.join(DOSSIER, "donnees_lstm.npz"), allow_pickle=True)
modele = keras.models.load_model(os.path.join(DOSSIER, "modele_lstm.keras"))

X_test = donnees["X_test"]
y_test = donnees["y_test"]
st_test = donnees["station_test"].astype("int32").reshape(-1, 1)
colonnes_cibles = list(donnees["colonnes_cibles"])
idx_pluie = colonnes_cibles.index("pluie")

predictions = modele.predict({"sequence": X_test, "station": st_test}, verbose=0)

pluie_reelle = y_test[:, idx_pluie]
pluie_predite = predictions[:, idx_pluie]

jours_pluvieux = pluie_reelle > SEUIL_PLUIE
jours_secs = ~jours_pluvieux

print(f"Jours de test : {len(pluie_reelle)}")
print(f"  dont pluvieux (>{SEUIL_PLUIE}mm) : {jours_pluvieux.sum()} ({100*jours_pluvieux.mean():.1f}%)")
print(f"  dont secs                       : {jours_secs.sum()} ({100*jours_secs.mean():.1f}%)")

print("\n=== MAE par catégorie de jour ===")
print(f"  Global      : {np.mean(np.abs(pluie_predite - pluie_reelle)):.3f} mm")
print(f"  Jours secs  : {np.mean(np.abs(pluie_predite[jours_secs] - pluie_reelle[jours_secs])):.3f} mm")
print(f"  Jours pluie : {np.mean(np.abs(pluie_predite[jours_pluvieux] - pluie_reelle[jours_pluvieux])):.3f} mm")

print(f"\n=== Prédiction moyenne du modèle ===")
print(f"  Sur les jours réellement secs   : {pluie_predite[jours_secs].mean():.3f} mm (réel : 0)")
print(f"  Sur les jours réellement pluvieux : {pluie_predite[jours_pluvieux].mean():.3f} mm (réel moyen : {pluie_reelle[jours_pluvieux].mean():.3f} mm)")

# Détection binaire "a-t-il plu ?" en seuillant la prédiction au même seuil
predit_pluie = pluie_predite > SEUIL_PLUIE
vrais_positifs = (predit_pluie & jours_pluvieux).sum()
faux_negatifs = (~predit_pluie & jours_pluvieux).sum()
faux_positifs = (predit_pluie & jours_secs).sum()
vrais_negatifs = (~predit_pluie & jours_secs).sum()

rappel = vrais_positifs / jours_pluvieux.sum() if jours_pluvieux.sum() else float("nan")
precision = vrais_positifs / predit_pluie.sum() if predit_pluie.sum() else float("nan")

print(f"\n=== Détection binaire \"a-t-il plu ?\" (seuil {SEUIL_PLUIE}mm) ===")
print(f"  Vrais positifs  (pluie prédite, pluie réelle)  : {vrais_positifs}")
print(f"  Faux négatifs   (pluie manquée)                : {faux_negatifs}")
print(f"  Faux positifs   (fausse alerte)                : {faux_positifs}")
print(f"  Vrais négatifs  (sec prédit, sec réel)          : {vrais_negatifs}")
print(f"  Rappel (% de pluies détectées)  : {100*rappel:.1f}%")
print(f"  Précision (% d'alertes justes)  : {100*precision:.1f}%")

correlation = np.corrcoef(pluie_predite, pluie_reelle)[0, 1]
print(f"\nCorrélation prédiction/réel (toutes valeurs) : {correlation:.3f}")
