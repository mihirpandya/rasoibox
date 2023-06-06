from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import Settings

settings: Settings = Settings()
engine = create_engine(
    settings.db_path,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


def get_engine():
    return engine
