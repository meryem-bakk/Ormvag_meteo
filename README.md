# ORMVAG Météo Manager

Application de bureau (PySide6) pour la collecte, le suivi et l'analyse des données météorologiques et des indicateurs agroclimatiques des stations de l'ORMVAG (Office Régional de Mise en Valeur Agricole du Gharb).

## Fonctionnalités

- **Tableau de bord** : vue d'ensemble en temps réel (stations actives, mesures du jour, température moyenne, tendances) avec alertes (gel, stress thermique, déficit hydrique) et carte interactive des stations.
- **Import de données** : import manuel ou automatique de mesures météo (fichiers Excel/CSV), traitement en arrière-plan, plus un script d'import d'historique pluriannuel (voir [Module Machine Learning](#module-machine-learning-ml)).
- **Gestion des stations** : création, modification, suivi de l'état des stations de mesure.
- **Indicateurs agroclimatiques** : calcul automatique d'indicateurs journaliers (gel, stress thermique, bilan hydrique) à partir des mesures brutes.
- **Graphiques** : visualisation des tendances par variable (température, humidité, pluie, vent) sur différentes périodes.
- **Rapports** : génération de rapports (PDF/Excel/CSV) à partir des données collectées, groupés par province, avec envoi manuel par email depuis l'interface.
- **Détection d'anomalies (IA)** : en complément des règles de plausibilité physique, un modèle Isolation Forest signale les journées statistiquement atypiques (page **Indicateurs**).
- **Carte** : localisation des stations avec statut visuel (OK / déficit / alerte).
- **Gestion des utilisateurs et rôles** : authentification, contrôle d'accès, et historique des modifications (création/modification de compte, changement de rôle, réinitialisation de mot de passe).
- **Sauvegarde** : sauvegarde manuelle depuis l'interface, et sauvegarde automatique planifiée chaque jour à 8h00.
- **Tâche planifiée quotidienne (8h00)** : import des dernières mesures, recalcul des indicateurs, génération et envoi par email du rapport journalier, sauvegarde de la base (voir sections dédiées ci-dessous).

## Stack technique

- **Interface** : [PySide6](https://doc.qt.io/qtforpython/) (Qt pour Python)
- **Base de données** : PostgreSQL via [SQLAlchemy](https://www.sqlalchemy.org/)
- **Graphiques** : Matplotlib
- **Cartographie** : Leaflet.js (affiché via `QWebEngineView`)
- **Authentification** : bcrypt pour le hachage des mots de passe
- **Planification** : APScheduler (tâche quotidienne à 8h00)
- **Machine Learning** : scikit-learn (détection d'anomalies Isolation Forest, intégrée à l'app) ; TensorFlow/Keras (prévisions LSTM, étude ponctuelle — voir [Module Machine Learning](#module-machine-learning-ml))

## Structure du projet

```
app/
├── models/          # Modèles SQLAlchemy (Station, Mesure, IndicateurJournalier, Role, User, HistoriqueModification)
├── services/         # Logique métier (alertes, calcul d'indicateurs, rapports, email, sauvegarde, historique,
│                      #   planification, prévision_ml, detection_anomalies_ml)
├── utils/            # Utilitaires
├── views/             # Pages de l'interface (tableau de bord, import, stations, graphiques, etc.)
├── workers/          # Traitements en arrière-plan (import de données)
└── database.py        # Configuration de la connexion à la base de données
ML/                    # Pipeline Machine Learning (voir section dédiée ci-dessous)
seed_*.py              # Scripts d'initialisation de la base (rôles, admin, stations, mesures)
importer_historique_excel.py  # Import d'historique météo pluriannuel depuis des exports Excel
main.py                # Point d'entrée de l'application
```

## Installation

### Déploiement sur un poste utilisateur (sans Python)

Pour un poste ne disposant pas encore de PostgreSQL, un installateur autonome (`Installateur-ORMVAG.exe`, voir `installateur/`) détecte si PostgreSQL est déjà actif, sinon l'installe silencieusement depuis l'installeur officiel EnterpriseDB embarqué, puis crée la base, le schéma et les données de base (rôles, compte admin, stations réelles). Lancer cet exécutable une seule fois, puis `ORMVAG-Meteo.exe` — voir la section [Construire les exécutables](#construire-les-exécutables).

### Développement

#### Prérequis

- Python 3.10+
- PostgreSQL installé et accessible

#### Étapes

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

## Construire les exécutables

```bash
venv\Scripts\pyinstaller.exe ORMVAG-Meteo.spec --noconfirm
venv\Scripts\pyinstaller.exe Installateur.spec --noconfirm
```

Génère respectivement `dist/ORMVAG-Meteo/` et `dist/Installateur-ORMVAG/`. Les deux se distribuent sous forme de dossiers (l'exécutable accompagné de `assets/`, `ML/`, `.env`, etc., et de `bin/` pour l'installateur), à l'image d'une application portable — voir `installateur/installer.py` pour l'URL de téléchargement de l'installeur PostgreSQL embarqué (non versionné, ~370 Mo).

## Variables d'environnement

Voir `.env.example` pour la liste complète. Principales variables :

| Variable | Description |
|---|---|
| `DATABASE_URL` | Chaîne de connexion PostgreSQL, format `postgresql://utilisateur:mot_de_passe@hote:port/nom_base` |
| `ADMIN_SEED_PASSWORD` | (optionnel) Mot de passe à utiliser pour le compte admin créé par `seed_admin.py`. Si non défini, un mot de passe aléatoire est généré et affiché une seule fois. |
| `SMTP_HOST`, `SMTP_PORT` | Serveur et port SMTP utilisés pour l'envoi des rapports par email (ex. `smtp.gmail.com`, `587`). |
| `SMTP_USER`, `SMTP_PASSWORD` | Compte d'envoi et mot de passe. Pour Gmail, utiliser un [mot de passe d'application](https://myaccount.google.com/apppasswords) (2FA requise), jamais le mot de passe du compte. |
| `SMTP_DESTINATAIRES` | Adresse(s) recevant les rapports, séparées par des virgules. Modifiable aussi depuis l'interface (page Paramètres). |
| `PG_DUMP_PATH` | (optionnel) Chemin vers `pg_dump.exe`, utilisé pour la sauvegarde de la base. Si absent, recherché automatiquement dans `C:\Program Files\PostgreSQL\<version>\bin\` (Windows). |

## Tâche planifiée quotidienne (8h00, pour le cycle 6h-6h)

Une tâche planifiée (`APScheduler`, `app/services/scheduler.py`) s'exécute chaque jour à **8h00** et enchaîne, chacune indépendamment des autres (une erreur sur l'une n'empêche pas les suivantes) :

1. **Import automatique** des dernières mesures des stations.
2. **Recalcul des indicateurs** agroclimatiques journaliers (uniquement les ~45 derniers jours ; les indicateurs plus anciens sont stables et ne sont pas retraités).
3. **Relevé des précipitations** : génération d'un fichier Excel au format officiel SED "RELEVE DES PRECIPITATIONS POUR LA CAMPAGNE AGRICOLE", envoyé par email aux adresses définies dans `SMTP_DESTINATAIRES`. Le fichier est aussi conservé dans `Rapports/`. Un envoi manuel (période, stations et format PDF/Excel/CSV au choix) est disponible depuis la page **Rapports**. La pluie des dernières 24h est calée sur le cycle agrométéorologique 6h-6h (convention OMM) et calculée à partir des relevés bruts (pas de 15 min) du site source — la tâche s'exécute à 8h plutôt que pile à 6h pour laisser le temps à ces relevés de remonter (délai de transmission observé d'environ 2h).
4. **Sauvegarde automatique** de la base (voir section dédiée ci-dessous).

Si l'application reste fermée à 8h00 (absence prolongée), la tâche est rattrapée au prochain démarrage : la fenêtre d'import s'élargit à la taille réelle de l'absence (plafonnée à 14 jours) et **un relevé distinct est généré et envoyé pour chaque jour manqué**, plutôt qu'un seul rapport pour le jour le plus récent.

Sans configuration SMTP valide dans `.env`, les autres étapes continuent de fonctionner normalement — seul l'envoi de l'email échoue (erreur journalisée dans la console). Idem pour `pg_dump` absent : seule la sauvegarde échoue.

### Format du relevé des précipitations

Reproduit la mise en page et les variables du bulletin utilisé par le SED (Service des Études et Données) :

- **Par station**, groupées par province (Kénitra, Sidi Kacem, Sidi Slimane) avec une ligne de moyenne par province et une ligne totale "ORMVAG" : pluie des **24 dernières heures** (cycle 6h-6h, convention OMM), pluie cumulée sur les **15 derniers jours glissants**, pluie cumulée de la **campagne agricole en cours** (depuis le 1er septembre) et de la **campagne n-1** à la même date.
- Seules les mesures confirmées (`type_donnee == "Mesuré"`) alimentent ces cumuls et les indicateurs agroclimatiques : une donnée encore taguée "Prévision" par le site source (pas encore remplacée par la vraie mesure) n'est jamais comptée comme réelle.
- **Deux tableaux mensuels** (pluie mensuelle et pluie cumulative, de septembre au mois en cours) comparant l'année en cours, l'année n-1 et la **normale sur 30 ans**. La base ne remonte qu'à ~10 ans : les valeurs de normale sont reprises telles quelles du bulletin officiel SED (`NORMALE_30_ANS_MENSUELLE` dans `app/services/generateur_rapport.py`) plutôt que recalculées, et à mettre à jour manuellement si le SED communique une normale révisée.
- Un graphique Excel natif (barres groupées, branché directement sur les cellules du tableau "PLUIE MENSUELLE") compare visuellement l'année en cours, l'année n-1 et la normale 30 ans, avec des badges rappelant les cumuls totaux de campagne.

## Sauvegarde

- **Automatique** : un dump complet de la base (`pg_dump`) est généré chaque jour à 8h00 dans `Sauvegardes/`, au format `sauvegarde_ormvag_AAAAMMJJ_HHMM.sql`. Seules les **14 sauvegardes les plus récentes** sont conservées, les plus anciennes sont supprimées automatiquement (`app/services/sauvegarde.py`).
- **Manuelle** : un bouton "Créer une sauvegarde" dans la page **Paramètres** permet de générer un dump à l'emplacement de son choix, à tout moment.

## Module Machine Learning (`ML/`)

Deux modèles entraînés sur l'historique météo des 14 stations (jusqu'à 10 ans de données journalières selon la station) :

| Modèle | Fichier | Rôle |
|---|---|---|
| LSTM multi-stations | `ML/modele_lstm.keras` + `ML/parametres_lstm.npz` | Prévoit la pluie et la température du lendemain à partir des 30 derniers jours de mesures. MAE sur jeu de test : ~1,9 mm (pluie), ~1,2°C (température). |
| Isolation Forest | `ML/detecteur_anomalies.joblib` | Détecte les journées dont la combinaison de variables (température, humidité, pluie, vent...) est statistiquement atypique pour la station. |

Seul l'**Isolation Forest** est intégré à l'application (page **Indicateurs**) : léger à charger, et il évalue les mesures du jour même, donc reste pertinent sans réentraînement fréquent.

Le **LSTM** a été implémenté et branché à l'application (page dédiée **Prévisions**, `app/views/previsions_page.py` + `app/services/prevision_ml.py`) au cours du stage, puis retiré de l'interface : une prévision affichée en direct sans pipeline de réentraînement régulier donne une fausse impression de fraîcheur, et son chargement (TensorFlow) alourdissait nettement le démarrage de l'app (~15s). Le code reste dans le dépôt et le modèle entraîné (`ML/modele_lstm.keras`) est versionné ; l'étude (méthodologie, résultats, limites ci-dessous) est documentée dans le rapport de stage plutôt qu'en fonctionnalité live.

### Pipeline de données (scripts, à relancer manuellement si besoin)

1. `importer_historique_excel.py <dossier>` — importe un historique météo pluriannuel depuis des exports Excel (une feuille par station, reconnue par nom ou par identifiant externe). Idempotent : ignore les dates déjà confirmées ("Mesuré") et les lignes de panne capteur (valeurs à 0 partout).
2. `ML/diagnostic_qualite.py` — audite la qualité des données par station (trous, doublons, valeurs suspectes).
3. `ML/nettoyer_donnees.py [--appliquer]` — supprime les mesures de panne capteur (dry-run par défaut).
4. `ML/preparer_donnees_lstm.py` — construit les fenêtres d'entraînement du LSTM (segmentation aux trous > 7 jours, interpolation des petits trous, split train/val/test chronologique). Génère `donnees_lstm.npz` (~85 Mo, non versionné) et le petit fichier `parametres_lstm.npz` (versionné).
5. `ML/entrainer_lstm.py` — entraîne et sauvegarde le modèle de prévision.
6. `ML/entrainer_detecteur_anomalies.py` — entraîne et sauvegarde le détecteur d'anomalies.

Pour re-générer les modèles avec des données à jour, relancer les étapes 4 à 6 (les étapes 1 à 3 ne sont utiles que si de nouvelles données brutes doivent être importées/nettoyées).

**Limites connues**, à garder en tête pour toute interprétation des résultats :
- Le modèle de pluie détecte bien *qu'il va pleuvoir* (rappel ~78-85 %) mais sous-estime souvent la *quantité* lors des épisodes pluvieux, et génère un nombre notable de fausses alertes (précision ~33-35 %) — se fier à la tendance plutôt qu'au chiffre exact.
- Une architecture "hurdle" à deux modèles (occurrence + quantité) a été testée mais n'a pas surpassé le modèle de référence sur l'ensemble des métriques ; le modèle simple a été conservé.

## Historique des modifications

Toute création/modification de compte utilisateur, changement de rôle, activation/désactivation, réinitialisation ou changement de mot de passe est enregistrée (qui, quoi, quand) dans la table `historique_modifications` et consultable directement sur la page **Utilisateurs**.

## Sécurité

- Ne jamais committer le fichier `.env` (déjà exclu via `.gitignore`) — `.env.example` ne doit contenir que des valeurs d'exemple, jamais de vrais identifiants ou mots de passe.
- Changer le mot de passe administrateur par défaut après la première connexion.
- Les fichiers de données réelles (`.sql`, `.xlsx`, `.csv`) ne sont pas versionnés — voir `.gitignore`.
- Historique des modifications sur les comptes/rôles (voir section dédiée ci-dessus).
- En exécutable packagé (sans console), une exception non interceptée est journalisée dans `erreur.log` (à côté de l'exécutable) et affichée à l'utilisateur, plutôt que de provoquer un blocage silencieux (`main.py`).

## Licence

Projet interne — usage réservé à l'ORMVAG.
