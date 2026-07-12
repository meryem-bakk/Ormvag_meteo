"""Entraîne un LSTM multi-stations sur les données préparées par preparer_donnees_lstm.py.

Architecture : la séquence de 30 jours passe dans deux couches LSTM, le résultat est
concaténé avec un embedding de la station (pour que le modèle apprenne les nuances
propres à chaque station tout en partageant la dynamique météo régionale commune),
puis deux couches denses produisent la prédiction (pluie, température) du jour suivant.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

CHEMIN_DONNEES = os.path.join(os.path.dirname(__file__), "donnees_lstm.npz")
CHEMIN_MODELE = os.path.join(os.path.dirname(__file__), "modele_lstm.keras")


def construire_modele(nb_stations, nb_features, taille_fenetre, dim_embedding=8, unites_lstm=64):
    entree_sequence = keras.Input(shape=(taille_fenetre, nb_features), name="sequence")
    entree_station = keras.Input(shape=(1,), name="station")

    embedding_station = layers.Embedding(nb_stations, dim_embedding, name="embedding_station")(entree_station)
    embedding_station = layers.Flatten()(embedding_station)

    x = layers.LSTM(unites_lstm, return_sequences=True)(entree_sequence)
    x = layers.LSTM(unites_lstm // 2)(x)

    x = layers.Concatenate()([x, embedding_station])
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(0.2)(x)
    sortie = layers.Dense(2, name="pluie_temperature")(x)

    modele = keras.Model(inputs=[entree_sequence, entree_station], outputs=sortie)
    modele.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return modele


def entrainer(epochs=30, batch_size=64, log=print):
    donnees = np.load(CHEMIN_DONNEES, allow_pickle=True)

    X_train, y_train = donnees["X_train"], donnees["y_train"]
    X_val, y_val = donnees["X_val"], donnees["y_val"]
    X_test, y_test = donnees["X_test"], donnees["y_test"]
    st_train = donnees["station_train"].astype("int32").reshape(-1, 1)
    st_val = donnees["station_val"].astype("int32").reshape(-1, 1)
    st_test = donnees["station_test"].astype("int32").reshape(-1, 1)

    nb_stations = len(donnees["noms_stations"])
    nb_features = X_train.shape[-1]
    taille_fenetre = X_train.shape[1]
    colonnes_cibles = donnees["colonnes_cibles"]

    log(f"Train: {X_train.shape} | Val: {X_val.shape} | Test: {X_test.shape}")
    log(f"Stations: {nb_stations} | Features: {nb_features} | Fenêtre: {taille_fenetre} jours\n")

    modele = construire_modele(nb_stations, nb_features, taille_fenetre)
    modele.summary(print_fn=log)

    arret_anticipe = keras.callbacks.EarlyStopping(
        monitor="val_loss", patience=5, restore_best_weights=True
    )

    modele.fit(
        {"sequence": X_train, "station": st_train}, y_train,
        validation_data=({"sequence": X_val, "station": st_val}, y_val),
        epochs=epochs, batch_size=batch_size,
        callbacks=[arret_anticipe],
        verbose=2,
    )

    predictions = modele.predict({"sequence": X_test, "station": st_test}, verbose=0)

    log("\n=== Résultats sur le jeu de test ===")
    for i, nom_cible in enumerate(colonnes_cibles):
        mae = float(np.mean(np.abs(predictions[:, i] - y_test[:, i])))
        rmse = float(np.sqrt(np.mean((predictions[:, i] - y_test[:, i]) ** 2)))
        log(f"  {nom_cible:<15} MAE: {mae:.3f}   RMSE: {rmse:.3f}")

    modele.save(CHEMIN_MODELE)
    log(f"\nModèle sauvegardé : {CHEMIN_MODELE}")

    return modele


if __name__ == "__main__":
    entrainer()
