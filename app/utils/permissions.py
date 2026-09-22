"""Vérifications de rôle centralisées - le rôle n'était jusqu'ici qu'une étiquette
affichée sur la page Utilisateurs, sans effet sur les actions disponibles ailleurs
dans l'application (n'importe quel compte connecté, y compris Consultation,
pouvait importer, modifier des stations, générer des rapports, gérer les comptes...).
"""

ROLE_CONSULTATION = "Consultation"
ROLE_ADMINISTRATEUR = "Administrateur"


def peut_ecrire_donnees(utilisateur):
    """Consultation est en lecture seule (cahier des charges §2.2) : import,
    gestion des stations, recalcul des indicateurs et génération de rapports
    sont réservés à Technicien et Administrateur."""
    return utilisateur.role.nom != ROLE_CONSULTATION


def est_administrateur(utilisateur):
    """Gestion des comptes/rôles et paramètres système : réservée à l'Administrateur."""
    return utilisateur.role.nom == ROLE_ADMINISTRATEUR
