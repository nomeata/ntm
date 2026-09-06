"""Versand der Login-Mails über das lokale ``sendmail``.

Auf dem Zielsystem steckt dahinter nullmailer; jede sendmail-kompatible
Implementierung tut es aber genauso.  Die Empfängerin wird als Argument
übergeben (nicht per ``-t``), das verstehen alle.  Gesendet wird ohnehin nur
an Adressen aus der konfigurierten Nutzerliste.
"""

from __future__ import annotations

import logging
import subprocess
from email.message import EmailMessage

log = logging.getLogger(__name__)

SUBJECT = "Anmeldung – Therapiematerialien"

BODY = """\
Hallo,

dieser Link meldet dich bei den Therapiematerialien an:

    {link}

Er wurde über das Anmeldeformular angefordert.  Falls nicht von dir:
einfach ignorieren, ohne den Link passiert nichts.
"""


def login_mail(mail_from: str, to: str, link: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = mail_from
    message["To"] = to
    message["Subject"] = SUBJECT
    message["Auto-Submitted"] = "auto-generated"
    message.set_content(BODY.format(link=link))
    return message


def send(sendmail: str, message: EmailMessage) -> None:
    """Blockiert kurz – aus dem Endpoint heraus in einem Thread aufrufen."""
    recipient = str(message["To"])
    subprocess.run(
        [sendmail, recipient],
        input=message.as_bytes(),
        check=True,
        timeout=30,
        capture_output=True,
    )
    log.info("Login-Mail an %s übergeben", recipient)
