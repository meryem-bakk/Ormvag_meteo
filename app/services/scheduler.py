import os
from datetime import datetime, date, time, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.calcul_indicateurs import calculer_indicateurs
from app.services.generateur_rapport import generer_rapport_journalier_excel
from app.services.email_service import envoyer_rapport_par_email
from app.services.sauvegarde import creer_sauvegarde_auto
from app.utils.event_bus import event_bus

# APScheduler ne déclenche la tâche de 6h que si l'application est ouverte à cet
# instant précis — si elle est fermée, la tâche est simplement sautée, sans
# rattrapage natif. Ce marqueur permet de détecter, à chaque démarrage de l'app,
# si la tâche du jour a déjà tourné, et sinon de la rattraper immédiatement.
CHEMIN_MARQUEUR_DERNIER_RUN = ".dernier_run_quotidien"

# Si l'app reste fermée plus longtemps que ça, on ne rattrape que les derniers
# cycles plutôt que tout l'historique (évite un rattrapage interminable après
# une très longue absence, ex. plusieurs semaines de congé).
MAX_JOURS_RATTRAPAGE = 14


def _tache_deja_executee_aujourdhui():
    if not os.path.exists(CHEMIN_MARQUEUR_DERNIER_RUN):
        return False
    with open(CHEMIN_MARQUEUR_DERNIER_RUN) as f:
        return f.read().strip() == date.today().isoformat()


def _marquer_tache_executee():
    with open(CHEMIN_MARQUEUR_DERNIER_RUN, "w") as f:
        f.write(date.today().isoformat())


def _date_reference_6h(instant=None):
    """Date du cycle agrométéorologique 6h-6h en cours à `instant` (par défaut
    maintenant). Convention OMM : la "journée" pluviométrique va de 6h à 6h."""
    instant = instant or datetime.now()
    reference = instant.replace(hour=6, minute=0, second=0, microsecond=0)
    return reference.date() if instant >= reference else reference.date() - timedelta(days=1)


def _jours_manques():
    """Liste des dates de cycles 6h-6h non couverts depuis le dernier run réussi
    (marqueur exclu) jusqu'au cycle courant (inclus). Plafonnée à
    MAX_JOURS_RATTRAPAGE pour éviter un rattrapage trop long après une absence
    prolongée. Retourne [aujourd'hui] si aucun marqueur n'existe encore."""
    aujourdhui = _date_reference_6h()

    if not os.path.exists(CHEMIN_MARQUEUR_DERNIER_RUN):
        return [aujourdhui]

    try:
        with open(CHEMIN_MARQUEUR_DERNIER_RUN) as f:
            dernier_run = date.fromisoformat(f.read().strip())
    except ValueError:
        return [aujourdhui]

    if dernier_run >= aujourdhui:
        return []

    nb_jours = (aujourdhui - dernier_run).days
    if nb_jours > MAX_JOURS_RATTRAPAGE:
        print(f"[Scheduler] Absence de {nb_jours} jour(s) détectée : rattrapage "
              f"limité aux {MAX_JOURS_RATTRAPAGE} derniers cycles.")
        dernier_run = aujourdhui - timedelta(days=MAX_JOURS_RATTRAPAGE)

    jours = []
    curseur = dernier_run + timedelta(days=1)
    while curseur <= aujourdhui:
        jours.append(curseur)
        curseur += timedelta(days=1)
    return jours


def _envoyer_rapport_pour_jour(jour):
    """Génère et envoie le rapport journalier du cycle 6h-6h se terminant le
    matin du `jour` donné (ex. jour=13/07 -> cycle 12/07 06h -> 13/07 06h)."""
    date_fin_cycle = datetime.combine(jour, time(6, 0))
    chemin_rapport, df_rapport, infos_rapport = generer_rapport_journalier_excel(date_fin=date_fin_cycle)
    print(f"[Scheduler 6h] Rapport journalier généré ({jour.strftime('%d/%m/%Y')}) : {chemin_rapport}")

    pluie_moyenne_reseau = df_rapport["Pluie 24h (mm)"].mean() if not df_rapport.empty else 0
    envoyer_rapport_par_email(
        chemin_rapport,
        sujet=f"ORMVAG — Relevé des précipitations du {jour.strftime('%d/%m/%Y')} "
              f"(campagne {infos_rapport['libelle_campagne']})",
        corps=(
            "Bonjour,\n\n"
            "Veuillez trouver ci-joint le relevé des précipitations du réseau ORMVAG "
            "(pluie 24h, 15 derniers jours, cumuls de campagne par station et par province).\n"
            f"Pluie moyenne réseau (dernières 24h) : {pluie_moyenne_reseau:.1f} mm.\n\n"
            "Cordialement,\nORMVAG — Système météo automatisé"
        ),
    )
    print(f"[Scheduler 6h] Rapport journalier envoyé par email ({jour.strftime('%d/%m/%Y')}).")


def tache_quotidienne_6h():
    """
    Exécutée chaque jour à 8h00 — 2h après la fin du cycle agrométéorologique
    6h-6h (convention OMM) qu'elle traite. Ce décalage laisse le temps aux relevés
    bruts du site source de remonter (délai de transmission observé d'environ 2h) :
    lancer la tâche pile à 6h00 laisserait le calcul de "Pluie 24h" amputé des
    deux dernières heures du cycle (voir generateur_rapport._pluie_24h). Le nom de
    la fonction et les libellés ("6h") font référence au cycle traité, pas à
    l'heure d'exécution réelle.

    Si l'application est restée fermée plusieurs jours, rattrape automatiquement
    tous les cycles manqués : import élargi à la taille réelle de l'absence,
    un rapport généré et envoyé par jour manqué (et non plus seulement pour le
    cycle le plus récent), un seul recalcul d'indicateurs et une seule
    sauvegarde (pas besoin d'une sauvegarde par jour manqué).
    """
    print("[Scheduler 6h] Démarrage de la tâche quotidienne...")

    jours_manques = _jours_manques() or [_date_reference_6h()]
    jours_a_couvrir = len(jours_manques)

    # Fenetre minimale de 15 jours (et non jours_a_couvrir + 2) : le site source
    # renvoie parfois la journee en cours en "Prevision" avant de la confirmer en
    # "Mesure" quelques jours plus tard. Une fenetre trop courte ne laisse jamais
    # a l'import quotidien la chance de revenir corriger ces lignes, qui restent
    # alors bloquees en "Prevision" indefiniment (voir calcul_indicateurs.py).
    JOURS_MIN_REIMPORT = 15

    import_reussi = False
    try:
        from import_automatique import lancer_import_complet
        total_importe, erreurs = lancer_import_complet(
            jours_a_recuperer=max(jours_a_couvrir + 2, JOURS_MIN_REIMPORT), log=print)
        print(f"[Scheduler 6h] Import terminé : {total_importe} mesure(s), {len(erreurs)} erreur(s).")
        import_reussi = True
    except Exception as e:
        print(f"[Scheduler 6h] Erreur lors de l'import automatique : {e}")

    try:
        total_indicateurs = calculer_indicateurs(log=print)
        print(f"[Scheduler 6h] Indicateurs recalculés : {total_indicateurs}.")
    except Exception as e:
        print(f"[Scheduler 6h] Erreur lors du calcul des indicateurs : {e}")

    if jours_a_couvrir > 1:
        print(f"[Scheduler 6h] Rattrapage : {jours_a_couvrir} cycle(s) manqué(s), "
              f"un rapport sera envoyé pour chacun.")

    for jour in jours_manques:
        try:
            _envoyer_rapport_pour_jour(jour)
        except Exception as e:
            print(f"[Scheduler 6h] Erreur lors de la génération/envoi du rapport "
                  f"journalier du {jour.strftime('%d/%m/%Y')} : {e}")

    try:
        chemin_sauvegarde = creer_sauvegarde_auto(log=print)
        if chemin_sauvegarde:
            print(f"[Scheduler 6h] Sauvegarde automatique créée : {chemin_sauvegarde}")
    except Exception as e:
        print(f"[Scheduler 6h] Erreur lors de la sauvegarde automatique : {e}")

    # Le marqueur n'avance que si l'import a reussi : une panne reseau transitoire
    # (voir erreur ci-dessus) ne doit pas faire passer la journee pour "traitee" -
    # sans quoi l'import ne serait retente qu'au prochain cycle de 6h, potentiellement
    # le lendemain, alors que la connexion peut deja etre revenue quelques minutes
    # plus tard. Les autres etapes (indicateurs, rapport, sauvegarde) s'executent
    # quand meme sur les donnees deja disponibles, marqueur ou non.
    if import_reussi:
        _marquer_tache_executee()
    else:
        print("[Scheduler 6h] Import echoue : la tache sera retentee au prochain "
              "demarrage plutot que consideree comme terminee pour aujourd'hui.")
    event_bus.donnees_mises_a_jour.emit()
    print("[Scheduler 6h] Tâche quotidienne terminée, pages notifiées.")


def demarrer_scheduler():
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        tache_quotidienne_6h,
        trigger="cron",
        hour=8,
        minute=0,
        id="tache_quotidienne_6h"
    )

    scheduler.start()
    calculer_indicateurs()

    if not _tache_deja_executee_aujourdhui():
        print("[Scheduler] Tâche quotidienne pas encore exécutée aujourd'hui "
              "(app probablement fermée à 8h00) — rattrapage en arrière-plan.")
        scheduler.add_job(tache_quotidienne_6h, id="rattrapage_quotidien")

    return scheduler
