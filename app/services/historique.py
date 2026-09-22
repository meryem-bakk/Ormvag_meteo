from app.models.historique_modification import HistoriqueModification


def enregistrer(session_db, acteur, action, cible_type, cible_id, description):
    """Ajoute une entrée à l'historique des modifications. N'effectue pas le commit :
    à appeler dans la même transaction que la modification elle-même."""
    session_db.add(HistoriqueModification(
        acteur_id=acteur.id if acteur else None,
        action=action,
        cible_type=cible_type,
        cible_id=cible_id,
        description=description,
    ))
