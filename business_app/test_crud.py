import os
import psycopg2
import psycopg2.extras
import sys

# Set environment variables for the database connection
os.environ['DB_NAME'] = 'business_app_db'
os.environ['DB_USER'] = 'business_app_user'
os.environ['DB_PASSWORD'] = 'mysecretpassword'

def get_test_db_connection():
    """Establishes a new database connection for the test."""
    print("Attempting to connect to the database...")
    conn = psycopg2.connect(
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        host=os.environ.get("DB_HOST", "localhost")
    )
    print("Database connection successful.")
    return conn

def cleanup_test_data(conn, email):
    """Deletes a contact by email to clean up before and after tests."""
    print(f"Cleaning up any existing test contact with email: {email}...")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM contacts WHERE email = %s", (email,))
    conn.commit()
    print("Cleanup complete.")

def test_create_contact(conn):
    """Tests the creation of a new contact."""
    print("\n--- Running test: Create Contact ---")
    test_contact = {
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'test.crud@example.com',
    }

    print("Executing INSERT...")
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO contacts (first_name, last_name, email) VALUES (%(first_name)s, %(last_name)s, %(email)s)",
            test_contact
        )
    conn.commit()
    print("INSERT executed and committed.")

    print("Verifying creation...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM contacts WHERE email = %s", (test_contact['email'],))
        created_contact = cur.fetchone()

    assert created_contact is not None, "Creation failed: Contact not found after insert."
    assert created_contact['first_name'] == 'Test', f"Creation failed: Expected first_name 'Test', got '{created_contact['first_name']}'."
    print("Create Contact Test PASSED.")
    return created_contact['id']

def test_update_contact(conn, contact_id):
    """Tests updating an existing contact."""
    print("\n--- Running test: Update Contact ---")
    updated_data = {
        'id': contact_id,
        'first_name': 'Updated',
        'company': 'NewCorp'
    }

    print("Executing UPDATE...")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE contacts SET first_name = %(first_name)s, company = %(company)s, updated_at = NOW() WHERE id = %(id)s",
            updated_data
        )
    conn.commit()
    print("UPDATE executed and committed.")

    print("Verifying update...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM contacts WHERE id = %s", (contact_id,))
        updated_contact = cur.fetchone()

    assert updated_contact['first_name'] == 'Updated', f"Update failed: Expected first_name 'Updated', got '{updated_contact['first_name']}'."
    assert updated_contact['company'] == 'NewCorp', f"Update failed: Expected company 'NewCorp', got '{updated_contact['company']}'."
    print("Update Contact Test PASSED.")

def test_delete_contact(conn, contact_id):
    """Tests deleting a contact."""
    print("\n--- Running test: Delete Contact ---")
    print("Executing DELETE...")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM contacts WHERE id = %s", (contact_id,))
    conn.commit()
    print("DELETE executed and committed.")

    print("Verifying deletion...")
    with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM contacts WHERE id = %s", (contact_id,))
        deleted_contact = cur.fetchone()

    assert deleted_contact is None, "Deletion failed: Contact still found after delete."
    print("Delete Contact Test PASSED.")


if __name__ == '__main__':
    conn = None
    test_email = 'test.crud@example.com'
    contact_id_to_test = None

    try:
        conn = get_test_db_connection()

        cleanup_test_data(conn, test_email)

        contact_id_to_test = test_create_contact(conn)
        test_update_contact(conn, contact_id_to_test)
        test_delete_contact(conn, contact_id_to_test)

        print("\n✅ All CRUD tests passed successfully!")

    except Exception as e:
        print(f"\n❌ An error occurred during testing: {e}", file=sys.stderr)
        # If an error occurs, try to clean up the created contact
        if conn and contact_id_to_test:
            print("Attempting to clean up created test data...")
            cleanup_test_data(conn, test_email)
        sys.exit(1) # Exit with an error code
    finally:
        if conn:
            conn.close()
            print("\nDatabase connection closed.")
