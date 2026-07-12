from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.services.calcul_indicateurs import calculer_indicateurs
from app.services.generateur_rapport import generer_rapport_journalier_pdf
from app.services.email_service import envoyer_rapport_par_email
from app.services.sauvegarde import creer_sauvegarde_auto
from app.utils.event_bus import event_bus


def tache_quotidienne_6h():
    """
    Exécutée chaque jour à 6h00 — heure de référence agrométéorologique
    (journée pluviométrique standard : 6h à 6h, convention OMM).
    """
    print("[Scheduler 6h] Démarrage de la tâche quotidienne...")

    try:
        from import_automatique import lancer_import_complet
        total_importe, erreurs = lancer_import_complet(jours_a_recuperer=2, log=print)
        print(f"[Scheduler 6h] Import terminé : {total_importe} mesure(s), {len(erreurs)} erreur(s).")
    except Exception as e:
        print(f"[Scheduler 6h] Erreur lors de l'import automatique : {e}")

    try:
        total_indicateurs = calculer_indicateurs(log=print)
        print(f"[Scheduler 6h] Indicateurs recalculés : {total_indicateurs}.")
    except Exception as e:
        print(f"[Scheduler 6h] Erreur lors du calcul des indicateurs : {e}")

    try:
        chemin_rapport, df_rapport = generer_rapport_journalier_pdf()
        print(f"[Scheduler 6h] Rapport journalier généré : {chemin_rapport}")

        cumul_reseau = df_rapport["Cumul pluie 24h (mm)"].sum() if not df_rapport.empty else 0
        envoyer_rapport_par_email(
            chemin_rapport,
            sujet=f"ORMVAG — Rapport météo journalier du {datetime.now().strftime('%d/%m/%Y')}",
            corps=(
                "Bonjour,\n\n"
                "Veuillez trouver ci-joint le rapport météorologique des dernières 24 heures "
                "(cumuls de précipitations par station).\n"
                f"Cumul de précipitations réseau : {cumul_reseau:.1f} mm.\n\n"
                "Cordialement,\nORMVAG — Système météo automatisé"
            ),
        )
        print("[Scheduler 6h] Rapport journalier envoyé par email.")
    except Exception as e:
        print(f"[Scheduler 6h] Erreur lors de la génération/envoi du rapport journalier : {e}")

    try:
        chemin_sauvegarde = creer_sauvegarde_auto(log=print)
        if chemin_sauvegarde:
            print(f"[Scheduler 6h] Sauvegarde automatique créée : {chemin_sauvegarde}")
    except Exception as e:
        print(f"[Scheduler 6h] Erreur lors de la sauvegarde automatique : {e}")

    event_bus.donnees_mises_a_jour.emit()
    print("[Scheduler 6h] Tâche quotidienne terminée, pages notifiées.")


def demarrer_scheduler():
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        tache_quotidienne_6h,
        trigger="cron",
        hour=6,
        minute=0,
        id="tache_quotidienne_6h"
    )

    scheduler.start()
    calculer_indicateurs()

    return scheduler