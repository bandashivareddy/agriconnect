import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError


BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE)

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def main():
    required = {
        "DB_HOST": DB_HOST,
        "DB_PORT": DB_PORT,
        "DB_NAME": DB_NAME,
        "DB_USER": DB_USER,
        "DB_PASSWORD": DB_PASSWORD,
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        print("ERROR: Missing database configuration:")
        print(", ".join(missing))
        return 1

    # SQLAlchemy URL.create safely handles special characters
    # in the username/password without exposing the password.
    database_url = URL.create(
        drivername="postgresql+psycopg",
        username=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=int(DB_PORT),
        database=DB_NAME,
    )

    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 5,
            },
        )

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        print(f"Database connection successful: {DB_NAME}")
        return 0

    except SQLAlchemyError as exc:
        print("ERROR: Could not connect to the AgriConnect database.")
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())