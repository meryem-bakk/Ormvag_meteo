# ORMVAG Météo Manager

Application de bureau (PySide6) pour la collecte, le suivi et l'analyse des données météorologiques et des indicateurs agroclimatiques des stations de l'ORMVAG (Office Régional de Mise en Valeur Agricole du Gharb).

## Fonctionnalités

- **Tableau de bord** : vue d'ensemble en temps réel (stations actives, mesures du jour, température moyenne, tendances) avec alertes (gel, stress thermique, déficit hydrique) et carte interactive des stations.
- **Import de données** : import manuel ou automatique de mesures météo (fichiers Excel/CSV), traitement en arrière-plan.
- **Gestion des stations** : création, modification, suivi de l'état des stations de mesure.
- **Indicateurs agroclimatiques** : calcul automatique d'indicateurs journaliers (gel, stress thermique, bilan hydrique) à partir des mesures brutes.
- **Graphiques** : visualisation des tendances par variable (température, humidité, pluie, vent) sur différentes périodes.
- **Rapports** : génération de rapports (PDF/Excel/CSV) à partir des données collectées, avec envoi manuel par email depuis l'interface.
- **Rapport journalier automatique** : chaque jour à 6h00, un rapport PDF axé sur les cumuls de précipitations des dernières 24h est généré et envoyé par email (voir section dédiée ci-dessous).
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
| `SMTP_HOST`, `SMTP_PORT` | Serveur et port SMTP utilisés pour l'envoi des rapports par email (ex. `smtp.gmail.com`, `587`). |
| `SMTP_USER`, `SMTP_PASSWORD` | Compte d'envoi et mot de passe. Pour Gmail, utiliser un [mot de passe d'application](https://myaccount.google.com/apppasswords) (2FA requise), jamais le mot de passe du compte. |
| `SMTP_DESTINATAIRES` | Adresse(s) recevant les rapports, séparées par des virgules. Modifiable aussi depuis l'interface (page Paramètres). |

## Rapport journalier automatique

Une tâche planifiée (`APScheduler`) s'exécute chaque jour à **6h00** :

1. Import automatique des dernières mesures des stations.
2. Recalcul des indicateurs agroclimatiques journaliers.
3. Génération d'un rapport PDF sur les **24 dernières heures**, trié par cumul de précipitations décroissant par station, avec le cumul réseau mis en avant.
4. Envoi de ce PDF par email aux adresses définies dans `SMTP_DESTINATAIRES`.

Le rapport est aussi sauvegardé dans le dossier `Rapports/`. Un envoi manuel (avec choix de la période, des stations et du format PDF/Excel/CSV) est disponible depuis la page **Rapports** de l'application.

Sans configuration SMTP valide dans `.env`, l'import et le calcul des indicateurs continuent de fonctionner normalement — seul l'envoi de l'email échoue silencieusement (erreur journalisée dans la console).

## Sécurité

- Ne jamais committer le fichier `.env` (déjà exclu via `.gitignore`) — `.env.example` ne doit contenir que des valeurs d'exemple, jamais de vrais identifiants ou mots de passe.
- Changer le mot de passe administrateur par défaut après la première connexion.
- Les fichiers de données réelles (`.sql`, `.xlsx`, `.csv`) ne sont pas versionnés — voir `.gitignore`.

## Licence

Projet interne — usage réservé à l'ORMVAG.
