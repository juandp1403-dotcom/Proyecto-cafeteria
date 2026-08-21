import os
import smtplib
import logging
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def enviar_correo(destinatario, asunto, cuerpo):
    """HU-25: envia un correo via SMTP configurado por variables de
    entorno (SMTP_HOST/PORT/USER/PASS/FROM). Si SMTP_HOST no esta
    configurado (entorno local sin credenciales reales), el correo se
    imprime en el log en vez de fallar -- para no bloquear el flujo de
    desarrollo local. Nunca lanza una excepcion hacia el llamador."""
    host = os.environ.get('SMTP_HOST')
    if not host:
        logger.warning(
            "SMTP_HOST no configurado -- correo NO enviado, se imprime "
            "para desarrollo local:\nPara: %s\nAsunto: %s\n%s",
            destinatario, asunto, cuerpo,
        )
        return False

    remitente = os.environ.get('SMTP_FROM', host)
    try:
        msg = MIMEText(cuerpo)
        msg['Subject'] = asunto
        msg['From'] = remitente
        msg['To'] = destinatario

        puerto = int(os.environ.get('SMTP_PORT', '587'))
        usuario = os.environ.get('SMTP_USER')
        clave = os.environ.get('SMTP_PASS')

        with smtplib.SMTP(host, puerto, timeout=10) as server:
            server.starttls()
            if usuario and clave:
                server.login(usuario, clave)
            server.sendmail(remitente, [destinatario], msg.as_string())
        return True
    except Exception:
        logger.exception("Fallo al enviar correo a %s", destinatario)
        return False
