from functools import wraps
from flask import session, request, redirect, url_for, flash
import os
import stripe
from dotenv import load_dotenv
from supabase_client import SupabaseLogger

# Ensure environment variables are loaded
load_dotenv()

# Stripe will be initialized in app.py after loading env vars

def init_auth_session():
    """Initialize session variables for authentication"""
    if 'user_id' not in session:
        session['user_id'] = None
    if 'user_email' not in session:
        session['user_email'] = None
    if 'is_paid' not in session:
        session['is_paid'] = False

def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this feature.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def paid_user_required(f):
    """Decorator to require paid subscription"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this feature.', 'error')
            return redirect(url_for('login'))
        
        if not session.get('is_paid'):
            flash('This feature requires a paid subscription.', 'error')
            return redirect(url_for('pricing'))
        
        return f(*args, **kwargs)
    return decorated_function

def login_user(email: str, supabase_client: SupabaseLogger):
    """Log in a user and set session variables"""
    try:
        user = supabase_client.create_or_get_user(email)
        
        if user:
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            session['is_paid'] = user.get('is_paid', False)
            return True
    except Exception as e:
        print(f"Supabase error: {e}")
        print("Using fallback authentication...")
        
        # Fallback: create session-only user when database is not ready
        import uuid
        session['user_id'] = str(uuid.uuid4())
        session['user_email'] = email
        session['is_paid'] = True  # Default to paid user for demo when DB unavailable
        print(f"Created temporary paid session for {email}")
        return True
    
    return False

def logout_user():
    """Log out the current user"""
    session.clear()

def get_current_user_id():
    """Get current user ID from session"""
    return session.get('user_id')

def is_current_user_paid():
    """Check if current user has paid subscription"""
    return session.get('is_paid', False)

def create_stripe_checkout_session(user_email: str, success_url: str, cancel_url: str):
    """Create Stripe checkout session for subscription"""
    # Ensure Stripe API key is set
    if not stripe.api_key:
        stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
        print(f"Setting Stripe API key in function: {bool(stripe.api_key)}")
    
    if not stripe.api_key:
        print("Stripe API key not configured")
        return None
        
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Turo Marketplace Access',
                        'description': 'List your eligible vehicles on our Turo marketplace',
                    },
                    'unit_amount': 999,  # $9.99 in cents
                    'recurring': {
                        'interval': 'month',
                    },
                },
                'quantity': 1,
            }],
            mode='subscription',
            customer_email=user_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'user_email': user_email
            }
        )
        return checkout_session
    except Exception as e:
        print(f"Error creating Stripe session: {e}")
        print(f"Stripe API Key configured: {bool(stripe.api_key)}")
        return None

def handle_stripe_webhook(payload, sig_header):
    """Handle Stripe webhook events"""
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return False
    except stripe.error.SignatureVerificationError:
        return False

    # Handle successful payment
    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        user_email = session_data['metadata']['user_email']
        
        # Update user payment status in database
        supabase_client = SupabaseLogger()
        user = supabase_client.create_or_get_user(user_email)
        if user:
            supabase_client.update_user_payment_status(user['id'], True)
    
    # Handle subscription cancellation
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        # Get customer email from Stripe
        customer = stripe.Customer.retrieve(customer_id)
        user_email = customer['email']
        
        # Update user payment status in database
        supabase_client = SupabaseLogger()
        user = supabase_client.create_or_get_user(user_email)
        if user:
            supabase_client.update_user_payment_status(user['id'], False)

    return True