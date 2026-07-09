from apscheduler.schedulers.background import BackgroundScheduler
from app.services.calcul_indicateurs import calculer_indicateurs


def demarrer_scheduler():
    scheduler = BackgroundScheduler()

    # Recalcul automatique tous les jours à 02h00
    scheduler.add_job(
        calculer_indicateurs,
        trigger="cron",
        hour=2,
        minute=0,
        id="calcul_indicateurs_quotidien"
    )

    scheduler.start()

    # Premier calcul immédiat au démarrage de l'app, pour ne pas attendre 02h00
    calculer_indicateurs()

    return scheduler