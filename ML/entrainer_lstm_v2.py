"""Version 2 : modèle "hurdle" (en deux étapes) pour mieux gérer la pluie, très
majoritairement à 0 mm (excès de zéros classique en météo).

1. Un modèle "occurrence" prédit la probabilité qu'il pleuve (classification) ET
   la température (régression) — entraîné sur toutes les données.
2. Un modèle "quantité" estime le volume de pluie, entraîné UNIQUEMENT sur les
   fenêtres où il a réellement plu (> SEUIL_PLUIE) — il n'est donc plus tiré vers
   zéro par la majorité des jours secs.

À la prédiction : si le modèle d'occurrence dit "il va pleuvoir", on utilise le
modèle de quantité pour estimer combien ; sinon on prédit 0 mm.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

DOSSIER = os.path.dirname(__file__)
CHEMIN_DONNEES = os.path.join(DOSSIER, "donnees_lstm.npz")
CHEMIN_MODELE_OCCURRENCE = os.path.join(DOSSIER, "modele_occurrence.keras")
CHEMIN_MODELE_QUANTITE = os.path.join(DOSSIER, "modele_quantite.keras")

SEUIL_PLUIE = 0.5  # mm : au-dessus, on considère qu'il "a plu" ce jour-là


def construire_tronc_commun(nb_stations, nb_features, taille_fenetre, dim_embedding=8, unites_lstm=64):
    """Partie partagée : LSTM sur la séquence + embedding de la station."""
    entree_sequence = keras.Input(shape=(taille_fenetre, nb_features), name="sequence")
    entree_station = keras.Input(shape=(1,), name="station")

    embedding_station = layers.Embedding(nb_stations, dim_embedding, name="embedding_station")(entree_station)
    embedding_station = layers.Flatten()(embedding_station)

    x = layers.LSTM(unites_lstm, return_sequences=True)(entree_sequence)
    x = layers.LSTM(unites_lstm // 2)(x)
    x = layers.Concatenate()([x, embedding_station])

    return entree_sequence, entree_station, x


def construire_perte_pluie_ponderee(poids_positif, poids_negatif=1.0):
    """Binary cross-entropy pondérée : les erreurs sur les jours de pluie (classe
    minoritaire) pèsent `poids_positif` fois plus que les erreurs sur les jours secs,
    pour empêcher le modèle de se contenter de prédire "jamais de pluie"."""
    def perte(y_true, y_pred):
        y_true = tf.cast(y_true, y_pred.dtype)
        bce = keras.losses.binary_crossentropy(y_true, y_pred)
        y_true_plat = tf.squeeze(y_true, axis=-1)
        poids = y_true_plat * poids_positif + (1.0 - y_true_plat) * poids_negatif
        return bce * poids
    return perte


def construire_modele_occurrence(nb_stations, nb_features, taille_fenetre, poids_positif=1.0, poids_negatif=1.0):
    entree_sequence, entree_station, tronc = construire_tronc_commun(nb_stations, nb_features, taille_fenetre)

    x = layers.Dense(32, activation="relu")(tronc)
    x = layers.Dropout(0.2)(x)
    sortie_temperature = layers.Dense(1, name="temperature")(x)
    sortie_pluie_proba = layers.Dense(1, activation="sigmoid", name="pluie_proba")(x)

    modele = keras.Model(
        inputs=[entree_sequence, entree_station],
        outputs=[sortie_temperature, sortie_pluie_proba],
    )
    modele.compile(
        optimizer="adam",
        loss={
            "temperature": "mse",
            "pluie_proba": construire_perte_pluie_ponderee(poids_positif, poids_negatif),
        },
        metrics={"temperature": "mae", "pluie_proba": "accuracy"},
    )
    return modele


def calculer_poids_classes(y_binaire):
    """Poids de classe pour rééquilibrer une classification déséquilibrée (ici ~85%
    de jours secs contre ~15% de jours pluvieux) : sans ça, le modèle peut se
    contenter de toujours prédire la classe majoritaire. Retourne (poids_positif, poids_negatif)."""
    n = len(y_binaire)
    n_pos = y_binaire.sum()
    n_neg = n - n_pos
    poids_pos = n / (2 * n_pos) if n_pos > 0 else 1.0
    poids_neg = n / (2 * n_neg) if n_neg > 0 else 1.0
    return float(poids_pos), float(poids_neg)


def construire_modele_quantite(nb_stations, nb_features, taille_fenetre):
    entree_sequence, entree_station, tronc = construire_tronc_commun(nb_stations, nb_features, taille_fenetre)

    x = layers.Dense(32, activation="relu")(tronc)
    x = layers.Dropout(0.2)(x)
    # softplus : garantit une quantité de pluie prédite toujours positive
    sortie = layers.Dense(1, activation="softplus", name="quantite_pluie")(x)

    modele = keras.Model(inputs=[entree_sequence, entree_station], outputs=sortie)
    modele.compile(optimizer="adam", loss="mae", metrics=["mae"])
    return modele


def entrainer(epochs=30, batch_size=64, log=print):
    donnees = np.load(CHEMIN_DONNEES, allow_pickle=True)

    X_train, y_train = donnees["X_train"], donnees["y_train"]
    X_val, y_val = donnees["X_val"], donnees["y_val"]
    X_test, y_test = donnees["X_test"], donnees["y_test"]
    st_train = donnees["station_train"].astype("int32").reshape(-1, 1)
    st_val = donnees["station_val"].astype("int32").reshape(-1, 1)
    st_test = donnees["station_test"].astype("int32").reshape(-1, 1)

    colonnes_cibles = list(donnees["colonnes_cibles"])
    idx_pluie = colonnes_cibles.index("pluie")
    idx_temp = colonnes_cibles.index("temperature")

    nb_stations = len(donnees["noms_stations"])
    nb_features = X_train.shape[-1]
    taille_fenetre = X_train.shape[1]

    pluie_train_bin = (y_train[:, idx_pluie] > SEUIL_PLUIE).astype("float32")
    pluie_val_bin = (y_val[:, idx_pluie] > SEUIL_PLUIE).astype("float32")

    poids_positif, poids_negatif = calculer_poids_classes(pluie_train_bin)
    log(f"Poids classe pluie — négatif: {poids_negatif:.3f}, positif: {poids_positif:.3f}\n")

    # --- Modèle 1 : occurrence de pluie + température, sur TOUT le jeu d'entraînement ---
    log("=== Entraînement du modèle d'occurrence (pluie oui/non + température) ===")
    modele_occurrence = construire_modele_occurrence(
        nb_stations, nb_features, taille_fenetre,
        poids_positif=poids_positif, poids_negatif=poids_negatif,
    )
    modele_occurrence.fit(
        {"sequence": X_train, "station": st_train},
        {"temperature": y_train[:, idx_temp], "pluie_proba": pluie_train_bin},
        validation_data=(
            {"sequence": X_val, "station": st_val},
            {"temperature": y_val[:, idx_temp], "pluie_proba": pluie_val_bin},
        ),
        epochs=epochs, batch_size=batch_size,
        callbacks=[keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)],
        verbose=2,
    )
    modele_occurrence.save(CHEMIN_MODELE_OCCURRENCE)

    # --- Modèle 2 : quantité de pluie, uniquement sur les fenêtres où il a réellement plu ---
    masque_train = y_train[:, idx_pluie] > SEUIL_PLUIE
    masque_val = y_val[:, idx_pluie] > SEUIL_PLUIE

    log(f"\n=== Entraînement du modèle de quantité (uniquement sur les jours pluvieux) ===")
    log(f"Fenêtres pluvieuses — train: {masque_train.sum()}, val: {masque_val.sum()}")

    modele_quantite = construire_modele_quantite(nb_stations, nb_features, taille_fenetre)
    modele_quantite.fit(
        {"sequence": X_train[masque_train], "station": st_train[masque_train]},
        y_train[masque_train, idx_pluie],
        validation_data=(
            {"sequence": X_val[masque_val], "station": st_val[masque_val]},
            y_val[masque_val, idx_pluie],
        ),
        epochs=epochs, batch_size=32,
        callbacks=[keras.callbacks.EarlyStopping(monitor="val_loss", patience=5, restore_best_weights=True)],
        verbose=2,
    )
    modele_quantite.save(CHEMIN_MODELE_QUANTITE)

    # --- Évaluation combinée sur le jeu de test ---
    temperature_pred, pluie_proba_pred = modele_occurrence.predict(
        {"sequence": X_test, "station": st_test}, verbose=0
    )
    quantite_pred = modele_quantite.predict({"sequence": X_test, "station": st_test}, verbose=0)

    predit_pluie_bin = (pluie_proba_pred[:, 0] > 0.5)
    pluie_finale_pred = np.where(predit_pluie_bin, quantite_pred[:, 0], 0.0)

    pluie_reelle = y_test[:, idx_pluie]
    temperature_reelle = y_test[:, idx_temp]
    jours_pluvieux = pluie_reelle > SEUIL_PLUIE
    jours_secs = ~jours_pluvieux

    log("\n=== Résultats combinés (modèle hurdle) sur le jeu de test ===")
    log(f"Température — MAE: {np.mean(np.abs(temperature_pred[:, 0] - temperature_reelle)):.3f}")
    log(f"Pluie — MAE global: {np.mean(np.abs(pluie_finale_pred - pluie_reelle)):.3f}")
    log(f"Pluie — MAE jours secs: {np.mean(np.abs(pluie_finale_pred[jours_secs] - pluie_reelle[jours_secs])):.3f}")
    log(f"Pluie — MAE jours pluvieux: {np.mean(np.abs(pluie_finale_pred[jours_pluvieux] - pluie_reelle[jours_pluvieux])):.3f}")
    log(f"Pluie — moyenne prédite jours pluvieux: {quantite_pred[jours_pluvieux, 0].mean():.3f} (réel: {pluie_reelle[jours_pluvieux].mean():.3f})")

    vrais_positifs = (predit_pluie_bin & jours_pluvieux).sum()
    faux_positifs = (predit_pluie_bin & jours_secs).sum()
    rappel = vrais_positifs / jours_pluvieux.sum()
    precision = vrais_positifs / predit_pluie_bin.sum() if predit_pluie_bin.sum() else float("nan")
    log(f"Rappel: {100*rappel:.1f}%  |  Précision: {100*precision:.1f}%")

    correlation = np.corrcoef(pluie_finale_pred, pluie_reelle)[0, 1]
    log(f"Corrélation prédiction/réel : {correlation:.3f}")

    return modele_occurrence, modele_quantite


if __name__ == "__main__":
    entrainer()
