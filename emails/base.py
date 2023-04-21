import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from imaplib import IMAP4_SSL, Time2Internaldate
from typing import Dict

from jinja2 import Template, Environment


class RasoiBoxEmail():
    email_template: Template
    template_args: Dict
    to_email: str
    subject: str
    from_email: str

    def __init__(
            self,
            email_template: Template,
            template_args: Dict,
            to_email: str,
            subject: str,
            from_email: str
    ):
        self.email_template = email_template
        self.template_args = template_args
        self.to_email = to_email
        self.subject = subject
        self.from_email = from_email

    def render_template(self) -> str:
        return self.email_template.render(self.template_args)


class VerifyUserEmail(RasoiBoxEmail):
    _subject: str = "Hello from Rasoi Box! Please verify your email."

    def __init__(self, email_template: Template, url_base: str, verification_code: str, to_email: str, from_email: str):
        super().__init__(email_template, {"verification_link": self.verification_link(url_base, verification_code)},
                         to_email, self._subject, from_email)

    def verification_link(self, url_base: str, verification_code: str) -> str:
        return "{}/verify/email?id={}".format(url_base, verification_code)


def send_email(email: RasoiBoxEmail, email_server: IMAP4_SSL):
    GMAIL_DRAFTS = "[Gmail]/Drafts"
    message: MIMEMultipart = MIMEMultipart('alternative')
    message['From'] = email.from_email
    message['To'] = email.to_email
    message['Subject'] = email.subject

    email_html: str = email.render_template()
    html_payload: MIMEText = MIMEText(email_html, 'html')
    message.attach(html_payload)
    email_server.append(GMAIL_DRAFTS,
                        '',
                        Time2Internaldate(time.time()),
                        bytes(message))
