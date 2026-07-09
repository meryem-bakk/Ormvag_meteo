# ORMVAG Météo Manager

Application de bureau (PySide6) pour la collecte, le suivi et l'analyse des données météorologiques et des indicateurs agroclimatiques des stations de l'ORMVAG (Office Régional de Mise en Valeur Agricole du Gharb).

## Fonctionnalités

- **Tableau de bord** : vue d'ensemble en temps réel (stations actives, mesures du jour, température moyenne, tendances) avec alertes (gel, stress thermique, déficit hydrique) et carte interactive des stations.
- **Import de données** : import manuel ou automatique de mesures météo (fichiers Excel/CSV), traitement en arrière-plan.
- **Gestion des stations** : création, modification, suivi de l'état des stations de mesure.
- **Indicateurs agroclimatiques** : calcul automatique d'indicateurs journaliers (gel, stress thermique, bilan hydrique) à partir des mesures brutes.
- **Graphiques** : visualisation des tendances par variable (température, humidité, pluie, vent) sur différentes périodes.
- **Rapports** : génération de rapports à partir des données collectées.
- **Carte** : localisation des stations avec statut visuel (OK / déficit / alerte).
- **Gestion des utilisateurs et rôles** : authentification et contrôle d'accès.

## Stack technique

- **Interface** : [PySide6](https://doc.qt.io/qtforpython/) (Qt pour Python)
- **Base de données** : PostgreSQL via [SQLAlchemy](https://www.sqlalchemy.org/)
- **Graphiques** : Matplotlib
- **Cartographie** : Leaflet.js (affiché via `QWebEngineView`)
- **Authentification** : bcrypt pour le hachage des mots de passe

## Structure du projet

```
app/
├── models/          # Modèles SQLAlchemy (Station, Mesure, IndicateurJournalier, Role, User)
├── services/         # Logique métier (alertes, calcul d'indicateurs, rapports, planification)
├── utils/            # Utilitaires
├── views/             # Pages de l'interface (tableau de bord, import, stations, graphiques, etc.)
├── workers/          # Traitements en arrière-plan (import de données)
└── database.py        # Configuration de la connexion à la base de données
seed_*.py              # Scripts d'initialisation de la base (rôles, admin, stations, mesures)
main.py                # Point d'entrée de l'application
```

## Installation

### Prérequis

- Python 3.10+
- PostgreSQL installé et accessible

### Étapes

1. Cloner le dépôt :
   ```bash
   git clone https://github.com/meryem-bakk/Ormvag_meteo.git
   cd Ormvag_meteo
   ```

2. Créer et activer un environnement virtuel :
   ```bash
   python -m venv venv
   venv\Scripts\activate       # Windows
   source venv/bin/activate    # macOS / Linux
   ```

3. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

4. Configurer les variables d'environnement :
   ```bash
   cp .env.example .env
   ```
   Puis éditer `.env` avec vos propres identifiants de base de données (voir la section ci-dessous).

5. Créer les tables :
   ```bash
   python test_connexion.py
   ```

6. Initialiser les données de base (rôles + compte administrateur) :
   ```bash
   python seed_roles.py
   python seed_admin.py
   ```

7. Lancer l'application :
   ```bash
   python main.py
   ```

## Variables d'environnement

Voir `.env.example` pour la liste complète. Principales variables :

| Variable | Description |
|---|---|
| `DATABASE_URL` | Chaîne de connexion PostgreSQL, format `postgresql://utilisateur:mot_de_passe@hote:port/nom_base` |
| `ADMIN_SEED_PASSWORD` | (optionnel) Mot de passe à utiliser pour le compte admin créé par `seed_admin.py`. Si non défini, un mot de passe aléatoire est généré et affiché une seule fois. |

## Sécurité

- Ne jamais committer le fichier `.env` (déjà exclu via `.gitignore`).
- Changer le mot de passe administrateur par défaut après la première connexion.
- Les fichiers de données réelles (`.sql`, `.xlsx`, `.csv`) ne sont pas versionnés — voir `.gitignore`.

## Licence

Projet interne — usage réservé à l'ORMVAG.
