from pydantic import BaseSettings, validator, ValidationError


class Settings(BaseSettings):
    from_email: str
    email: str
    email_app_password: str
    url_base: str

    class Config:
        env_file = ".env"

    @validator('from_email')
    def validate_email(cls, email_address: str) -> str:
        if email_address.endswith("@rasoibox.com"):
            return email_address
        raise ValidationError("Malformed email address.")
