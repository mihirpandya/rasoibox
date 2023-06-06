from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP
from typing import Dict

from jinja2 import Environment


class RasoiBoxEmail():
    template: str
    template_args: Dict
    to_email: str
    subject: str
    from_email: str

    def __init__(
            self,
            template: str,
            template_args: Dict,
            to_email: str,
            subject: str,
            from_email: str
    ):
        self.template = template
        self.template_args = template_args
        self.to_email = to_email
        self.subject = subject
        self.from_email = from_email


class VerifySignUpEmail(RasoiBoxEmail):
    _subject: str = "Hello from Rasoi Box! Please verify your email."

    def __init__(self, url_base: str, verification_code: str, to_email: str,
                 from_email: str):
        template_args = {
            "verification_link": self.verification_link(url_base, verification_code)
        }
        super().__init__("verify_email.html", template_args, to_email, self._subject, from_email)

    def verification_link(self, url_base: str, verification_code: str) -> str:
        return "{}/menu?id={}".format(url_base, verification_code)


class ResetPasswordEmail(RasoiBoxEmail):
    _subject: str = "Your Rasoi Box Account: Password Reset"

    def __init__(self, url_base: str, reset_code: str, to_email: str, from_email: str):
        template_args = {
            "reset_link": self.reset_link(url_base, reset_code)
        }
        super().__init__("reset_password_email.html", template_args, to_email, self._subject, from_email)

    def reset_link(self, url_base: str, reset_code: str) -> str:
        return "{}/reset?id={}".format(url_base, reset_code)


def send_email(jinjaEnv: Environment, email: RasoiBoxEmail, email_server: SMTP, email_address: str,
               email_password: str):
    message: MIMEMultipart = MIMEMultipart("related")
    message['From'] = email.from_email
    message['To'] = email.to_email
    message['Subject'] = email.subject
    msg_html = MIMEText(jinjaEnv.get_template(email.template).render(**email.template_args), "html")
    message.attach(msg_html)

    f = open("templates/assets/logo.png", "rb")
    logo_img = MIMEImage(f.read())
    f.close()
    logo_img.add_header('Content-ID', '<logo.png>')
    logo_img.add_header('Content-Disposition', 'inline', filename="templates/assets/logo.png")
    message.attach(logo_img)

    email_server.connect('smtp.gmail.com', 587)
    email_server.starttls()
    email_server.login(email_address, email_password)
    email_server.send_message(message)
    email_server.quit()
