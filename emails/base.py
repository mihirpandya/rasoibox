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
