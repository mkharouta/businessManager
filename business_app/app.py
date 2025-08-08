import os
import psycopg2
import psycopg2.extras
from flask import Flask, g, jsonify, render_template

app = Flask(__name__, template_folder='templates')

# --- Database Connection ---
def get_db():
    if 'db' not in g:
        try:
            # Try connecting with a password if it's provided
            g.db = psycopg2.connect(
                dbname=os.environ.get("DB_NAME", "postgres"),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD"),
                host=os.environ.get("DB_HOST", "localhost")
            )
        except psycopg2.OperationalError as e:
            # If password fails, try without it (for local dev with peer auth)
            if "password authentication failed" in str(e) and not os.environ.get("DB_PASSWORD"):
                g.db = psycopg2.connect(
                    dbname=os.environ.get("DB_NAME", "postgres"),
                    user=os.environ.get("DB_USER", "postgres"),
                    host=os.environ.get("DB_HOST", "localhost")
                )
            else:
                # Re-raise the exception if it's not a password issue or if a password was provided
                raise e
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- UI Routes ---
@app.route('/')
def index():
    """
    Renders the main admin dashboard page.
    """
    return render_template('index.html')

@app.route('/contacts-ui')
def contacts_ui():
    """
    Fetches all contacts from the database and renders the contacts UI page.
    """
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM contacts ORDER BY id ASC;")
        contacts = [dict(row) for row in cur.fetchall()]
    return render_template('contacts.html', contacts=contacts)

# --- API Routes ---
@app.route('/api/contacts')
def get_contacts_api():
    """
    Fetches all contacts from the database and returns them as JSON.
    """
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM contacts ORDER BY id ASC;")
        contacts_list = [dict(row) for row in cur.fetchall()]
    return jsonify(contacts_list)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
