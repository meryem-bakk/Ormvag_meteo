import os
import re
import glob
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DOSSIER_SAUVEGARDES_DEFAUT = "Sauvegardes"
RETENTION_SAUVEGARDES = 14  # nombre de sauvegardes automatiques conservées ; les plus anciennes sont supprimées


def trouver_pg_dump():
    """Localise pg_dump.exe : d'abord via PG_DUMP_PATH dans .env, sinon dans les
    emplacements standards d'installation PostgreSQL sous Windows."""
    chemin_env = os.getenv("PG_DUMP_PATH")
    if chemin_env and os.path.exists(chemin_env):
        return chemin_env

    base = r"C:\Program Files\PostgreSQL"
    if os.path.isdir(base):
        for version in sorted(os.listdir(base), reverse=True):
            chemin_possible = os.path.join(base, version, "bin", "pg_dump.exe")
            if os.path.exists(chemin_possible):
                return chemin_possible

    return None


def _parser_database_url():
    database_url = os.getenv("DATABASE_URL", "")
    correspondance = re.match(
        r"postgresql\+?\w*://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)",
        database_url
    )
    if not correspondance:
        return None

    utilisateur_db, mot_de_passe_db, hote, port, nom_base = correspondance.groups()
    return utilisateur_db, mot_de_passe_db, hote, port or "5432", nom_base


def executer_pg_dump(chemin_sortie, timeout=180):
    """Exécute pg_dump vers chemin_sortie. Retourne (succes: bool, message: str) —
    message est le chemin en cas de succès, ou une description de l'erreur sinon."""
    pg_dump = trouver_pg_dump()
    if not pg_dump:
        return False, ("pg_dump.exe introuvable. Ajoute PG_DUMP_PATH=chemin\\vers\\pg_dump.exe "
                        "dans le fichier .env (dossier bin de ton installation PostgreSQL).")

    infos = _parser_database_url()
    if not infos:
        return False, "Impossible de lire les informations de connexion depuis DATABASE_URL (.env)."
    utilisateur_db, mot_de_passe_db, hote, port, nom_base = infos

    environnement = os.environ.copy()
    environnement["PGPASSWORD"] = mot_de_passe_db

    try:
        resultat = subprocess.run(
            [pg_dump, "-h", hote, "-p", port, "-U", utilisateur_db, "-F", "p", "-f", chemin_sortie, nom_base],
            env=environnement, capture_output=True, text=True, timeout=timeout
        )
    except Exception as e:
        return False, str(e)

    if resultat.returncode != 0:
        return False, resultat.stderr

    return True, chemin_sortie


def appliquer_retention(dossier, garder=RETENTION_SAUVEGARDES, log=print):
    """Ne conserve que les `garder` sauvegardes automatiques les plus récentes."""
    fichiers = sorted(glob.glob(os.path.join(dossier, "sauvegarde_ormvag_*.sql")))
    if len(fichiers) <= garder:
        return

    for chemin in fichiers[:-garder]:
        try:
            os.remove(chemin)
            log(f"[Sauvegarde] Ancienne sauvegarde supprimée : {chemin}")
        except OSError as e:
            log(f"[Sauvegarde] Impossible de supprimer {chemin} : {e}")


def creer_sauvegarde_auto(dossier_sortie=DOSSIER_SAUVEGARDES_DEFAUT, log=print):
    """Crée une sauvegarde automatique horodatée dans `dossier_sortie` et applique
    la politique de rétention. Retourne le chemin créé, ou None en cas d'échec."""
    os.makedirs(dossier_sortie, exist_ok=True)
    nom_fichier = f"sauvegarde_ormvag_{datetime.now().strftime('%Y%m%d_%H%M')}.sql"
    chemin = os.path.join(dossier_sortie, nom_fichier)

    succes, message = executer_pg_dump(chemin)
    if not succes:
        log(f"[Sauvegarde] Échec : {message}")
        return None

    log(f"[Sauvegarde] Fichier créé : {chemin}")
    appliquer_retention(dossier_sortie, log=log)
    return chemin
