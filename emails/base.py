from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from smtplib import SMTP
from typing import Dict, List, Any

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


class ResetPasswordCompleteEmail(RasoiBoxEmail):
    _subject: str = "Your Rasoi Box password has been reset"

    def __init__(self, first_name: str, to_email: str, from_email: str):
        template_args = {
            "first_name": first_name
        }
        super().__init__("reset_password_complete_email.html", template_args, to_email, self._subject, from_email)


class ReceiptEmail(RasoiBoxEmail):
    _subject: str = "Rasoi Box Order Confirmation"

    def __init__(self, url_base: str, first_name: str, line_items: List[Dict[str, Any]], promo_code: Dict[str, Any],
                 total: float, sub_total: float, shipping_address: Dict[str, Any], order_id: str, to_email: str,
                 from_email: str):
        subject = self._subject + ": " + order_id
        template_args = {
            "order_link": self.order_link(url_base, order_id),
            "first_name": first_name,
            "subtotal": "{:.2f}".format(sub_total),
            "total": "{:.2f}".format(total),
            "line_items": line_items,
            "shipping_address": shipping_address,
            "order_id": order_id
        }

        if len(promo_code) > 0:
            discount_str = ""
            if promo_code["amount_off"] is not None and promo_code["amount_off"] > 0:
                discount_str = "-$" + "{:.2f}".format(promo_code["amount_off"])
            elif promo_code["percent_off"] is not None and promo_code["percent_off"] > 0:
                discount_str = "-" + str(int(promo_code["percent_off"])) + "%"
            template_args["promo_code"] = {
                "name": promo_code["name"],
                "discount_str": discount_str
            }

        super().__init__("receipt.html", template_args, to_email, subject, from_email)

    def order_link(self, url_base: str, order_id: str) -> str:
        return "{}/order?orderId={}".format(url_base, order_id)


class InvitationEmail(RasoiBoxEmail):
    _prefix: str = "You're Invited: "
    _suffix: str = " off your first Rasoi Box!"

    def __init__(self, url_base: str, promo_code: str, promo_amount: str, to_email: str, from_email: str):
        subject = self._prefix + promo_amount + self._suffix
        template_args = {
            "promo_code": promo_code,
            "promo_amount": promo_amount
        }
        super().__init__("invitation.html", template_args, to_email, subject, from_email)


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
