"""Initialisation des données de base d'une installation neuve : rôles,
compte administrateur, et les 14 stations réelles du réseau ORMVAG. Utilisé
par seed_admin.py/seed_roles.py/seed_stations_reelles.py (usage manuel) et par
l'installateur automatique (installateur/installer.py)."""
import os
import secrets
import bcrypt
from app.database import SessionLocal
from app.models.role import Role
from app.models.user import User
from app.models.station import Station

ROLES_DE_BASE = [
    ("Administrateur", "Accès complet à toutes les fonctionnalités"),
    ("Technicien", "Gestion des stations, import et consultation des données"),
    ("Consultation", "Lecture seule des données et rapports"),
]

# (identifiant_externe exact du site, nom affiché, longitude, latitude, province)
STATIONS_REELLES = [
    ("Pce_Kenitra_S.Larbaa", "Souk Larbaa (Kénitra)", -6.00067, 34.67090, "Kénitra"),
    ("Pce_S.Sliman_S.sliman", "Sidi Slimane", -5.93738, 34.25191, "Sidi Slimane"),
    ("Pce_Kenitra_S.Allal-Tazi", "Sidi Allal Tazi (Kénitra)", -6.33066, 34.51860, "Kénitra"),
    ("PCE_KENITRA_NORD3", "Kénitra Nord 3", -6.06312, 34.66965, "Kénitra"),
    ("Pce_S.Kacem_Zeggoutta", "Zeggoutta (Sidi Kacem)", -5.53122, 34.16882, "Sidi Kacem"),
    ("PCE_KENITRA_OUED ETTINE", "Oued Ettine (Kénitra)", -5.71564, 34.69691, "Kénitra"),
    ("METEO KHENICHET", "Khénichet", -5.68279, 34.42399, "Sidi Kacem"),
    ("Pce_Kenitra_Souk-Tlat", "Souk Tlat (Kénitra)", -6.15635, 34.62290, "Kénitra"),
    ("Pce_S.Kacem_BELKSIRI", "Mechraa Bel Ksiri (Sidi Kacem)", -5.95139, 34.57700, "Sidi Kacem"),
    ("Pce_Kenitra_Lamnassra", "Lamnassra (Kénitra)", -6.48486, 34.45630, "Kénitra"),
    ("KENITRA-BANLIEUE", "Kénitra Banlieue", -6.44178, 34.33617, "Kénitra"),
    ("Pce_S.Kacem_S.Kacem", "Sidi Kacem", -5.79713, 34.25410, "Sidi Kacem"),
    ("AMEUR CHAMALIA-DAR GUEDDARI", "Ameur Chamalia - Dar Gueddari", -6.12745, 34.42843, "Sidi Slimane"),
    ("SIDIYAHYA_ELGHARB", "Sidi Yahya El Gharb", -6.16150, 34.23947, "Sidi Slimane"),
]


def _creer_roles(session, log):
    nb_ajoutes = 0
    for nom, description in ROLES_DE_BASE:
        if not session.query(Role).filter_by(nom=nom).first():
            session.add(Role(nom=nom, description=description))
            nb_ajoutes += 1
    session.commit()
    log(f"{nb_ajoutes} rôle(s) ajouté(s).")


def _creer_admin(session, log):
    """Crée le compte admin s'il n'existe pas. Utilise ADMIN_SEED_PASSWORD si
    défini dans l'environnement, sinon génère un mot de passe aléatoire affiché
    une seule fois (voir .env.example). Retourne le mot de passe utilisé, ou
    None si le compte existait déjà."""
    role_admin = session.query(Role).filter_by(nom="Administrateur").first()

    utilisateur_existant = session.query(User).filter_by(username="admin").first()
    if utilisateur_existant:
        log("L'utilisateur admin existe déjà.")
        return None

    mot_de_passe = os.getenv("ADMIN_SEED_PASSWORD") or secrets.token_urlsafe(9)
    session.add(User(
        username="admin",
        password_hash=bcrypt.hashpw(mot_de_passe.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        nom_complet="Administrateur",
        role_id=role_admin.id,
        actif=True,
    ))
    session.commit()
    log(f"Utilisateur admin créé (identifiant : admin / mot de passe : {mot_de_passe})")
    return mot_de_passe


def _creer_stations(session, log):
    nb_crees = 0
    nb_mis_a_jour = 0
    for i, (identifiant, nom, longitude, latitude, province) in enumerate(STATIONS_REELLES, start=1):
        station = session.query(Station).filter_by(identifiant_externe=identifiant).first()
        if station:
            station.nom = nom
            station.latitude = latitude
            station.longitude = longitude
            station.province = province
            nb_mis_a_jour += 1
        else:
            code = f"REAL-{i:02d}"
            while session.query(Station).filter_by(code=code).first():
                i += 1
                code = f"REAL-{i:02d}"
            session.add(Station(
                nom=nom, code=code, latitude=latitude, longitude=longitude,
                altitude=0, actif=True, identifiant_externe=identifiant, province=province,
            ))
            nb_crees += 1
    session.commit()
    log(f"{nb_crees} station(s) créée(s), {nb_mis_a_jour} mise(s) à jour.")


def initialiser_donnees_de_base(log=print):
    """Rôles + compte admin + stations réelles, dans cet ordre (l'admin a besoin
    du rôle). Idempotent : peut être relancé sans dupliquer quoi que ce soit.
    Retourne le mot de passe admin généré, ou None si le compte existait déjà."""
    session = SessionLocal()
    try:
        _creer_roles(session, log)
        mot_de_passe_admin = _creer_admin(session, log)
        _creer_stations(session, log)
        return mot_de_passe_admin
    finally:
        session.close()
