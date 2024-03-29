import logging

from pydantic import BaseSettings, validator, ValidationError

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    from_email: str
    email: str
    email_app_password: str
    backend_url_base: str
    frontend_url_base: str
    db_path: str
    admin_user: str
    admin_password: str
    jwt_secret_key: str
    stripe_secret_key: str
    stripe_referral_coupon_id: str
    stripe_welcome_promo_code_id: str
    stripe_payment_success_webhook_secret: str

    class Config:
        env_file = ".env"

    @validator('from_email')
    def validate_email(cls, email_address: str) -> str:
        if email_address.endswith("@rasoibox.com"):
            return email_address
        raise ValidationError("Malformed email address.")
