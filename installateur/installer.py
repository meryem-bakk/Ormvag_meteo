"""Installateur autonome ORMVAG Meteo Manager : installe PostgreSQL 18 si
absent, cree la base et le schema, et seed les donnees de base (roles, admin,
stations reelles). A lancer une seule fois, avant le premier lancement de
ORMVAG-Meteo.exe, depuis le meme dossier (assets/, ML/, bin/).

bin/postgresql-18.4-2-windows-x64.exe n'est pas versionne (voir .gitignore,
~370 Mo) : a retelecharger depuis
https://get.enterprisedb.com/postgresql/postgresql-18.4-2-windows-x64.exe
avant de reconstruire (pyinstaller Installateur.spec).
"""
import os
import sys
import socket
import secrets
import subprocess
import time

NOM_SERVICE = "postgresql-x64-18"
PORT = 5432
NOM_BASE = "ormvag_meteo"

if getattr(sys, "frozen", False):
    RACINE = os.path.dirname(sys.executable)
else:
    RACINE = os.path.dirname(os.path.abspath(__file__))

CHEMIN_ENV = os.path.join(RACINE, ".env")
CHEMIN_PG_INSTALLER = os.path.join(RACINE, "bin", "postgresql-18.4-2-windows-x64.exe")

# Le code applicatif (app/) est un dossier frere de installateur/ dans le depot ;
# une fois construit en exe, PyInstaller l'embarque directement (voir Installateur.spec).
sys.path.insert(0, os.path.dirname(RACINE))


def pg_port_ouvert():
    """Detecte une instance PostgreSQL deja active sur le port local standard."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        return s.connect_ex(("localhost", PORT)) == 0


def attendre_pg(timeout=90):
    debut = time.time()
    while time.time() - debut < timeout:
        if pg_port_ouvert():
            return True
        time.sleep(2)
    return False


def installer_postgresql(mot_de_passe_postgres):
    if not os.path.exists(CHEMIN_PG_INSTALLER):
        raise RuntimeError(f"Installeur PostgreSQL introuvable : {CHEMIN_PG_INSTALLER}")

    print("Installation de PostgreSQL 18 (mode silencieux, ~2-5 min, ne pas fermer)...")
    resultat = subprocess.run([
        CHEMIN_PG_INSTALLER,
        "--mode", "unattended",
        "--unattendedmodeui", "minimal",
        "--superpassword", mot_de_passe_postgres,
        "--servicename", NOM_SERVICE,
        "--serverport", str(PORT),
        "--disable-components", "stackbuilder",
    ], capture_output=True, text=True)

    if resultat.returncode != 0:
        raise RuntimeError(
            f"Echec de l'installation PostgreSQL (code {resultat.returncode}) :\n{resultat.stderr}"
        )
    print("PostgreSQL installe.")

    if not attendre_pg():
        raise RuntimeError("PostgreSQL installe mais ne repond pas sur le port 5432 apres 90s.")


def creer_base(mot_de_passe_postgres):
    import psycopg
    conn = psycopg.connect(
        f"host=localhost port={PORT} dbname=postgres user=postgres password={mot_de_passe_postgres}",
        autocommit=True,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (NOM_BASE,))
            if cur.fetchone():
                print(f"Base '{NOM_BASE}' deja presente.")
            else:
                cur.execute(f'CREATE DATABASE "{NOM_BASE}"')
                print(f"Base '{NOM_BASE}' creee.")
    finally:
        conn.close()


def ecrire_env(mot_de_passe_postgres):
    if os.path.exists(CHEMIN_ENV):
        print(".env deja present : conserve tel quel (identifiants existants non modifies).")
        return

    contenu = (
        f"DATABASE_URL=postgresql://postgres:{mot_de_passe_postgres}@localhost:{PORT}/{NOM_BASE}\n"
        "ADMIN_SEED_PASSWORD=\n"
        "SMTP_HOST=smtp.gmail.com\n"
        "SMTP_PORT=587\n"
        "SMTP_USER=\n"
        "SMTP_PASSWORD=\n"
        "SMTP_DESTINATAIRES=\n"
        "ORMVAG_TELEPHONE=\n"
        "ORMVAG_MOTDEPASSE=\n"
    )
    with open(CHEMIN_ENV, "w", encoding="utf-8") as f:
        f.write(contenu)
    print(".env cree.")
    print(
        "IMPORTANT : completez ORMVAG_TELEPHONE / ORMVAG_MOTDEPASSE (identifiants du site "
        "avertissement.yobeen.com) dans le fichier .env avant d'utiliser l'import automatique."
    )


def initialiser_schema_et_donnees():
    from dotenv import load_dotenv
    load_dotenv(CHEMIN_ENV, override=True)

    from app.database import engine, Base
    import app.models  # noqa: F401 - necessaire pour enregistrer les tables aupres de Base
    Base.metadata.create_all(engine)
    print("Schema de base de donnees cree.")

    from app.services.premier_demarrage import initialiser_donnees_de_base
    return initialiser_donnees_de_base(log=print)


def main():
    print("=== Installateur ORMVAG Meteo Manager ===\n")

    if pg_port_ouvert():
        print("PostgreSQL semble deja actif sur ce PC (port 5432 ouvert).")
        mot_de_passe_postgres = input(
            "Mot de passe du compte 'postgres' existant (pour creer la base ormvag_meteo) : "
        ).strip()
    else:
        mot_de_passe_postgres = secrets.token_urlsafe(16)
        installer_postgresql(mot_de_passe_postgres)

    creer_base(mot_de_passe_postgres)
    ecrire_env(mot_de_passe_postgres)
    mot_de_passe_admin = initialiser_schema_et_donnees()

    print("\n=== Installation terminee ===")
    print("Vous pouvez maintenant lancer ORMVAG-Meteo.exe depuis ce meme dossier.")
    if mot_de_passe_admin:
        print(f"Identifiant : admin | Mot de passe : {mot_de_passe_admin}")
        print("(a changer des le premier login, dans Parametres > Utilisateurs)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERREUR] {e}")
    input("\nAppuyez sur Entree pour fermer...")
