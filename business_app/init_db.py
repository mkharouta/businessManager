import psycopg2
import os

# This script will initialize the database by creating the necessary tables.

# For now, we'll connect to the default 'postgres' database as the 'postgres' user.
# In a production environment, you would use a dedicated database and user with a secure password.
DB_NAME = os.environ.get("DB_NAME", "postgres")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD") # Should be set in the environment
DB_HOST = os.environ.get("DB_HOST", "localhost")

try:
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST
    )
except psycopg2.OperationalError as e:
    # This can happen if the password is required for the postgres user.
    # We will handle user creation and permissions in the next step.
    # For now, we'll try connecting without a password.
    if "password authentication failed" in str(e):
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME,
                user=DB_USER,
                host=DB_HOST
            )
        except psycopg2.OperationalError as e2:
            print(f"Could not connect to the database: {e2}")
            exit(1)
    else:
        print(f"Could not connect to the database: {e}")
        exit(1)


with conn.cursor() as cur:
    # Using "CREATE TABLE IF NOT EXISTS" makes the script idempotent.
    cur.execute("""
    CREATE TABLE IF NOT EXISTS contacts (
        id SERIAL PRIMARY KEY,
        first_name VARCHAR(100),
        last_name VARCHAR(100),
        email VARCHAR(255) UNIQUE NOT NULL,
        phone_number VARCHAR(50),
        address TEXT,
        company VARCHAR(255),
        job_title VARCHAR(255),
        relationship TEXT,
        date_of_birth DATE,
        gender VARCHAR(50),
        occupation VARCHAR(255),
        current_trait TEXT,
        profile_notes TEXT,
        personality_openness SMALLINT,
        personality_conscientiousness SMALLINT,
        personality_extraversion SMALLINT,
        personality_agreeableness SMALLINT,
        personality_neuroticism SMALLINT,
        history TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS records (
        id SERIAL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        record_type VARCHAR(100),
        record_date DATE,
        contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS attachments (
        id SERIAL PRIMARY KEY,
        record_id INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
        filename VARCHAR(255) NOT NULL,
        filepath VARCHAR(1024) NOT NULL,
        mimetype VARCHAR(255),
        filesize BIGINT,
        uploaded_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'active', -- e.g., 'active', 'inactive'
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        payment_method VARCHAR(50) NOT NULL,
        amount_charged DECIMAL(20, 8) NOT NULL,
        currency_charged VARCHAR(10) NOT NULL,
        amount_paid_fiat DECIMAL(10, 2),
        transaction_fee DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
        status VARCHAR(50) NOT NULL DEFAULT 'pending', -- e.g., pending, succeeded, failed
        payment_processor_ref VARCHAR(255) UNIQUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    """)

    # We can also add a trigger to automatically update the updated_at timestamp.
    # For now, the application logic will handle this.

    print("Tables 'contacts', 'records', and 'attachments' successfully created or already exist.")

conn.commit()
conn.close()
