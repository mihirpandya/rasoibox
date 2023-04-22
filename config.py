import logging
import os.path

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

    class Config:
        env_file = ".env"

    @validator('from_email')
    def validate_email(cls, email_address: str) -> str:
        if email_address.endswith("@rasoibox.com"):
            return email_address
        raise ValidationError("Malformed email address.")

    @validator('db_path')
    def validate_db_path(cls, db_path: str) -> str:
        if db_path.endswith("/"):
            raise ValidationError("db_path must be a path to a file")
        if not os.path.exists(db_path):
            if "/" not in db_path:
                logger.warn("Creating db in local directory: %s", os.getcwd())
            else:
                raise ValidationError("db_path does not exist")
        return db_path
