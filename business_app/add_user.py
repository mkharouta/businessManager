import os
import psycopg2
import argparse
from werkzeug.security import generate_password_hash

def add_user(username, password):
    """Adds a new user to the database."""
    password_hash = generate_password_hash(password)

    DB_NAME = os.environ.get("DB_NAME", "postgres")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD")
    DB_HOST = os.environ.get("DB_HOST", "localhost")

    conn = None
    try:
        # Re-using connection logic similar to init_db.py for consistency
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                host=DB_HOST
            )
        except psycopg2.OperationalError as e:
            if "password authentication failed" in str(e) and not DB_PASSWORD:
                 conn = psycopg2.connect(
                    dbname=DB_NAME,
                    user=DB_USER,
                    host=DB_HOST
                )
            else:
                # Re-raise if it's not a password issue we can handle
                raise e

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, status) VALUES (%s, %s, %s)",
                (username, password_hash, 'active')
            )

        conn.commit()
        print(f"User '{username}' added successfully.")

    except psycopg2.IntegrityError:
        print(f"Error: User '{username}' already exists.")
        if conn:
            conn.rollback()
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Add a new user to the database.")
    parser.add_argument("username", help="The username for the new user.")
    parser.add_argument("password", help="The password for the new user.")
    args = parser.parse_args()

    if not args.password:
        print("Error: Password cannot be empty.")
    else:
        add_user(args.username, args.password)
