import os
import mimetypes
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()


def envoyer_rapport_par_email(chemin_fichier, sujet, corps):
    """Envoie le fichier donné (PDF, Excel ou CSV) en pièce jointe aux destinataires configurés dans .env."""
    hote = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    utilisateur = os.getenv("SMTP_USER")
    mot_de_passe = os.getenv("SMTP_PASSWORD")
    destinataires = [d.strip() for d in os.getenv("SMTP_DESTINATAIRES", "").split(",") if d.strip()]

    if not (hote and utilisateur and mot_de_passe and destinataires):
        raise RuntimeError(
            "Configuration SMTP incomplète : renseignez SMTP_HOST, SMTP_USER, "
            "SMTP_PASSWORD et SMTP_DESTINATAIRES dans le fichier .env."
        )

    message = EmailMessage()
    message["Subject"] = sujet
    message["From"] = utilisateur
    message["To"] = ", ".join(destinataires)
    message.set_content(corps)

    type_mime, _ = mimetypes.guess_type(chemin_fichier)
    maintype, subtype = type_mime.split("/", 1) if type_mime else ("application", "octet-stream")

    with open(chemin_fichier, "rb") as f:
        message.add_attachment(
            f.read(), maintype=maintype, subtype=subtype,
            filename=os.path.basename(chemin_fichier)
        )

    with smtplib.SMTP(hote, port) as serveur:
        serveur.starttls()
        serveur.login(utilisateur, mot_de_passe)
        serveur.send_message(message)
