"""Users pick themselves by name and country; there is no auth."""
import psycopg2.errors

from core.countries import validate_country
from core.database import db_cursor


class UserExists(Exception):
    pass


def list_users():
    with db_cursor() as cur:
        cur.execute("SELECT id, name, country FROM users ORDER BY name")
        return [{"id": id, "name": name, "country": country} for id, name, country in cur.fetchall()]


def create_user(name: str, country: str):
    """The new user; ValueError on a blank name or unknown country, UserExists if the name is taken."""
    name = (name or "").strip()
    if not name:
        raise ValueError("Enter a name.")
    country = validate_country(country)
    try:
        with db_cursor() as cur:
            cur.execute("INSERT INTO users (name, country) VALUES (%s, %s) RETURNING id", (name, country))
            return {"id": cur.fetchone()[0], "name": name, "country": country}
    except psycopg2.errors.UniqueViolation:
        raise UserExists(f"{name} already exists; pick it from the list.")
