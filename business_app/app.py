import os
import psycopg2
import psycopg2.extras
import stripe
from coinbase_commerce.client import Client
from coinbase_commerce.webhook import Webhook
from flask import Flask, g, jsonify, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, ValidationError

app = Flask(__name__, template_folder='templates')
# It's important to set a secret key for session management and WTForms CSRF protection
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a-very-secret-key')

# --- Stripe Configuration ---
app.config['STRIPE_PUBLISHABLE_KEY'] = os.environ.get('STRIPE_PUBLISHABLE_KEY')
app.config['STRIPE_SECRET_KEY'] = os.environ.get('STRIPE_SECRET_KEY')
app.config['STRIPE_WEBHOOK_SECRET'] = os.environ.get('STRIPE_WEBHOOK_SECRET')
stripe.api_key = app.config['STRIPE_SECRET_KEY']

# --- Coinbase Commerce Configuration ---
app.config['COINBASE_COMMERCE_API_KEY'] = os.environ.get('COINBASE_COMMERCE_API_KEY')
app.config['COINBASE_COMMERCE_WEBHOOK_SECRET'] = os.environ.get('COINBASE_COMMERCE_WEBHOOK_SECRET')

# Initialize the Coinbase client
if app.config['COINBASE_COMMERCE_API_KEY']:
    try:
        Client.init(app.config['COINBASE_COMMERCE_API_KEY'])
    except Exception as e:
        app.logger.warning(f"Could not initialize Coinbase Commerce client: {e}")
else:
    app.logger.warning("COINBASE_COMMERCE_API_KEY is not set. Coinbase payments will not be available.")


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # The name of the view to redirect to when login is required

# --- User Model and Authentication ---
class User(UserMixin):
    def __init__(self, id, username, password_hash, status='active'):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.status = status

    @property
    def is_active(self):
        """
        Flask-Login requires an is_active property.
        A user is active if their status is 'active'.
        """
        return self.status == 'active'

    def set_password(self, password):
        """Hashes and sets the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    """
    Callback function for Flask-Login to load a user from the database.
    """
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM users WHERE id = %s;", (user_id,))
        user_data = cur.fetchone()
        if user_data:
            return User(
                id=user_data['id'],
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                status=user_data['status']
            )
    return None

# --- Forms ---
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

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
@login_required
def index():
    """
    Renders the main payment page for authenticated users.
    """
    return render_template('payment.html')

@app.route('/contacts-ui')
@login_required
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
@login_required
def get_contacts_api():
    """
    Fetches all contacts from the database and returns them as JSON.
    """
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM contacts ORDER BY id ASC;")
        contacts_list = [dict(row) for row in cur.fetchall()]
    return jsonify(contacts_list)


# --- Stripe Payment Routes ---
@app.route('/create-payment-intent', methods=['POST'])
@login_required
def create_payment_intent():
    try:
        data = request.get_json()
        # Amount should be in the smallest currency unit (e.g., cents)
        amount = int(data['amount'])
        currency = data['currency']

        if currency.upper() not in ['USD', 'EUR']:
            return jsonify(error={'message': f'Currency {currency} not supported.'}), 400

        # Calculate 5% transaction fee
        fee = int(amount * 0.05)
        total_amount = amount + fee

        # Create a pending transaction record in the database
        db = get_db()
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # Using DECIMAL for amounts, so no need to divide by 100 here
            cur.execute(
                """
                INSERT INTO transactions (user_id, payment_method, amount_charged, currency_charged, transaction_fee, status)
                VALUES (%s, %s, %s, %s, %s, 'pending') RETURNING id;
                """,
                (current_user.id, 'stripe', total_amount / 100.0, currency.upper(), fee / 100.0)
            )
            transaction_id = cur.fetchone()['id']
            db.commit()

        # Create a PaymentIntent with the amount and currency
        intent = stripe.PaymentIntent.create(
            amount=total_amount,
            currency=currency,
            metadata={
                'user_id': current_user.id,
                'internal_transaction_id': transaction_id
            }
        )

        return jsonify({
            'clientSecret': intent.client_secret
        })
    except Exception as e:
        app.logger.error(f"Error creating payment intent: {e}")
        return jsonify(error={'message': str(e)}), 400


# --- Coinbase Payment Routes ---
@app.route('/create-coinbase-charge', methods=['POST'])
@login_required
def create_coinbase_charge():
    if not app.config.get('COINBASE_COMMERCE_API_KEY'):
        return jsonify({'error': {'message': 'Coinbase payments are not configured.'}}), 500

    try:
        from coinbase_commerce.model import Charge

        data = request.get_json()
        amount_cents = int(data['amount'])
        currency = data['currency'].upper()

        # Gross up the amount to pass the ~1% fee to the user
        total_amount = round((amount_cents / 100.0) / 0.99, 2)

        db = get_db()
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                INSERT INTO transactions (user_id, payment_method, amount_charged, currency_charged, transaction_fee, status)
                VALUES (%s, %s, %s, %s, %s, 'pending') RETURNING id;
                """,
                (current_user.id, 'coinbase', total_amount, currency, round(total_amount - (amount_cents / 100.0), 2), 'pending')
            )
            transaction_id = cur.fetchone()['id']
            db.commit()

        charge_data = {
            'name': 'Business App Payment',
            'description': f'Payment for Transaction ID: {transaction_id}',
            'local_price': {
                'amount': str(total_amount),
                'currency': currency,
            },
            'pricing_type': 'fixed_price',
            'metadata': {
                'user_id': current_user.id,
                'internal_transaction_id': transaction_id,
            },
            'redirect_url': url_for('index', _external=True, payment_status='success'),
            'cancel_url': url_for('index', _external=True, payment_status='canceled'),
        }

        charge = Charge.create(**charge_data)

        # Save the coinbase charge id to our transaction for reference
        with db.cursor() as cur:
            cur.execute(
                "UPDATE transactions SET payment_processor_ref = %s WHERE id = %s",
                (charge.id, transaction_id)
            )
            db.commit()

        return jsonify({'hosted_url': charge.hosted_url})

    except Exception as e:
        app.logger.error(f"Error creating Coinbase charge: {e}")
        return jsonify({'error': {'message': 'An error occurred while creating the Coinbase charge.'}}), 500


@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = app.config['STRIPE_WEBHOOK_SECRET']
    event = None

    if not endpoint_secret:
        app.logger.warning("STRIPE_WEBHOOK_SECRET is not set. Skipping signature verification.")
        return "Webhook secret not configured.", 500

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        # Invalid payload
        app.logger.error(f"Invalid payload in webhook: {e}")
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        app.logger.error(f"Invalid signature in webhook: {e}")
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_payment_succeeded(payment_intent)
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        handle_payment_failed(payment_intent)
    else:
        app.logger.info(f"Unhandled event type {event['type']}")

    return jsonify(success=True)

def handle_payment_succeeded(payment_intent):
    """
    Handles the 'payment_intent.succeeded' event.
    Updates transaction and user status in the database.
    """
    metadata = payment_intent.get('metadata', {})
    transaction_id = metadata.get('internal_transaction_id')
    user_id = metadata.get('user_id')

    if transaction_id and user_id:
        db = get_db()
        with db.cursor() as cur:
            # Update transaction status to 'succeeded'
            cur.execute(
                "UPDATE transactions SET status = 'succeeded', payment_processor_ref = %s, updated_at = NOW() WHERE id = %s",
                (payment_intent['id'], transaction_id)
            )

            # Deactivate the user
            cur.execute(
                "UPDATE users SET status = 'inactive' WHERE id = %s",
                (user_id,)
            )
            db.commit()
        app.logger.info(f"Payment succeeded for transaction {transaction_id}. User {user_id} deactivated.")
    else:
        app.logger.error("Error: Missing metadata in successful payment intent.")

def handle_payment_failed(payment_intent):
    """
    Handles the 'payment_intent.payment_failed' event.
    Updates transaction status in the database.
    """
    metadata = payment_intent.get('metadata', {})
    transaction_id = metadata.get('internal_transaction_id')
    if transaction_id:
        db = get_db()
        with db.cursor() as cur:
            # Update transaction status to 'failed'
            cur.execute(
                "UPDATE transactions SET status = 'failed', payment_processor_ref = %s, updated_at = NOW() WHERE id = %s",
                (payment_intent['id'], transaction_id)
            )
            db.commit()
        app.logger.info(f"Payment failed for transaction {transaction_id}.")
    else:
        app.logger.error("Error: Missing metadata in failed payment intent.")


@app.route('/coinbase-webhook', methods=['POST'])
def coinbase_webhook():
    webhook_secret = app.config.get('COINBASE_COMMERCE_WEBHOOK_SECRET')
    if not webhook_secret:
        app.logger.warning("COINBASE_COMMERCE_WEBHOOK_SECRET is not set. Cannot process webhook.")
        return "Webhook secret not configured.", 500

    request_data = request.data
    request_sig = request.headers.get('X-CC-Webhook-Signature', None)

    try:
        event = Webhook.construct_event(request_data.decode('utf-8'), request_sig, webhook_secret)
    except (Webhook.SignatureVerificationError, Webhook.InvalidPayloadError) as e:
        app.logger.error(f"Coinbase webhook error: {e}")
        return str(e), 400

    # Handle the event
    if event.type == 'charge:confirmed':
        handle_coinbase_charge_confirmed(event)
    elif event.type == 'charge:failed':
        handle_coinbase_charge_failed(event)
    else:
        app.logger.info(f"Unhandled Coinbase event type: {event.type}")

    return 'OK', 200

def handle_coinbase_charge_confirmed(event):
    """Handles a confirmed Coinbase charge."""
    charge = event.data
    metadata = charge.get('metadata', {})
    transaction_id = metadata.get('internal_transaction_id')
    user_id = metadata.get('user_id')

    if transaction_id and user_id:
        db = get_db()
        with db.cursor() as cur:
            # Update transaction status
            cur.execute(
                "UPDATE transactions SET status = 'succeeded', updated_at = NOW() WHERE id = %s",
                (transaction_id,)
            )
            # Deactivate user
            cur.execute(
                "UPDATE users SET status = 'inactive' WHERE id = %s",
                (user_id,)
            )
            db.commit()
        app.logger.info(f"Coinbase charge confirmed for transaction {transaction_id}. User {user_id} deactivated.")
    else:
        app.logger.error(f"Error: Missing metadata in confirmed Coinbase charge: {charge}")

def handle_coinbase_charge_failed(event):
    """Handles a failed Coinbase charge."""
    charge = event.data
    metadata = charge.get('metadata', {})
    transaction_id = metadata.get('internal_transaction_id')
    if transaction_id:
        db = get_db()
        with db.cursor() as cur:
            cur.execute(
                "UPDATE transactions SET status = 'failed', updated_at = NOW() WHERE id = %s",
                (transaction_id,)
            )
            db.commit()
        app.logger.info(f"Coinbase charge failed for transaction {transaction_id}.")
    else:
        app.logger.error(f"Error: Missing metadata in failed Coinbase charge: {charge}")


# --- Authentication Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        db = get_db()
        with db.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username = %s;", (form.username.data,))
            user_data = cur.fetchone()

        user = None
        if user_data:
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                status=user_data['status']
            )

        if user and user.check_password(form.password.data):
            if user.is_active:
                login_user(user)
                flash('Logged in successfully.', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('index'))
            else:
                flash('Your account is inactive. Please contact an administrator.', 'danger')
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html', title='Login', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
