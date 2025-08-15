import os
import psycopg2
import psycopg2.extras
from flask import Flask, g, jsonify, render_template, request, redirect, url_for, flash

app = Flask(__name__, template_folder='templates')
app.secret_key = os.urandom(24)

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


@app.route('/contacts/new', methods=['GET', 'POST'])
def new_contact():
    """
    Renders the form to create a new contact and handles form submission.
    """
    if request.method == 'POST':
        # Get form data, converting empty strings to None
        form_data = {key: value if value else None for key, value in request.form.items()}

        # The 'date_of_birth' field needs to be handled carefully if it's empty
        if not form_data.get('date_of_birth'):
            form_data['date_of_birth'] = None

        # Integer fields need to be converted to int, or None if empty
        for key in ['personality_openness', 'personality_conscientiousness', 'personality_extraversion', 'personality_agreeableness', 'personality_neuroticism']:
            if form_data.get(key) is not None:
                try:
                    form_data[key] = int(form_data[key])
                except (ValueError, TypeError):
                    form_data[key] = None

        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contacts (
                    first_name, last_name, email, phone_number, address, company, job_title,
                    relationship, date_of_birth, gender, occupation, current_trait,
                    profile_notes, personality_openness, personality_conscientiousness,
                    personality_extraversion, personality_agreeableness, personality_neuroticism,
                    history
                ) VALUES (
                    %(first_name)s, %(last_name)s, %(email)s, %(phone_number)s, %(address)s,
                    %(company)s, %(job_title)s, %(relationship)s, %(date_of_birth)s,
                    %(gender)s, %(occupation)s, %(current_trait)s, %(profile_notes)s,
                    %(personality_openness)s, %(personality_conscientiousness)s,
                    %(personality_extraversion)s, %(personality_agreeableness)s,
                    %(personality_neuroticism)s, %(history)s
                )
                """,
                form_data
            )
        db.commit()
        flash('Contact created successfully!', 'success')
        return redirect(url_for('contacts_ui'))

    # For GET request, just render the form
    return render_template('contact_form.html')


@app.route('/contacts/<int:id>/edit', methods=['GET', 'POST'])
def edit_contact(id):
    """
    Renders the form to edit a contact and handles form submission for updates.
    """
    db = get_db()

    # Fetch the contact to edit for both GET and POST
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM contacts WHERE id = %s", (id,))
        contact = cur.fetchone()

    if contact is None:
        flash('Contact not found.', 'danger')
        return redirect(url_for('contacts_ui'))

    if request.method == 'POST':
        # Get form data
        form_data = {key: value if value else None for key, value in request.form.items()}
        form_data['id'] = id  # Add id for the WHERE clause in the UPDATE statement

        # Handle date and integer fields
        if not form_data.get('date_of_birth'):
            form_data['date_of_birth'] = None
        for key in ['personality_openness', 'personality_conscientiousness', 'personality_extraversion', 'personality_agreeableness', 'personality_neuroticism']:
            if form_data.get(key) is not None:
                try:
                    form_data[key] = int(form_data[key])
                except (ValueError, TypeError):
                    form_data[key] = None

        with db.cursor() as cur:
            cur.execute(
                """
                UPDATE contacts SET
                    first_name = %(first_name)s,
                    last_name = %(last_name)s,
                    email = %(email)s,
                    phone_number = %(phone_number)s,
                    address = %(address)s,
                    company = %(company)s,
                    job_title = %(job_title)s,
                    relationship = %(relationship)s,
                    date_of_birth = %(date_of_birth)s,
                    gender = %(gender)s,
                    occupation = %(occupation)s,
                    current_trait = %(current_trait)s,
                    profile_notes = %(profile_notes)s,
                    personality_openness = %(personality_openness)s,
                    personality_conscientiousness = %(personality_conscientiousness)s,
                    personality_extraversion = %(personality_extraversion)s,
                    personality_agreeableness = %(personality_agreeableness)s,
                    personality_neuroticism = %(personality_neuroticism)s,
                    history = %(history)s,
                    updated_at = NOW()
                WHERE id = %(id)s
                """,
                form_data
            )
        db.commit()
        flash('Contact updated successfully!', 'success')
        return redirect(url_for('contacts_ui'))

    # For GET request, render the form with the contact's data
    return render_template('contact_form.html', contact=contact)


@app.route('/contacts/<int:id>/delete', methods=['POST'])
def delete_contact(id):
    """
    Deletes a contact from the database.
    """
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        # Check if contact exists before deleting to provide a better error message
        cur.execute("SELECT id FROM contacts WHERE id = %s", (id,))
        contact = cur.fetchone()
        if contact is None:
            flash('Contact not found.', 'danger')
        else:
            cur.execute("DELETE FROM contacts WHERE id = %s", (id,))
            db.commit()
            flash('Contact deleted successfully!', 'success')

    return redirect(url_for('contacts_ui'))

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
