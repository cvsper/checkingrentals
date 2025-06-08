from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
from werkzeug.utils import secure_filename
from vin_utils import VINDecoder
from eligibility_rules import TuroEligibilityChecker
from supabase_client import SupabaseLogger
from auth import (
    init_auth_session, login_required, paid_user_required, 
    login_user, logout_user, get_current_user_id, is_current_user_paid,
    create_stripe_checkout_session, handle_stripe_webhook
)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Initialize components
vin_decoder = VINDecoder()
eligibility_checker = TuroEligibilityChecker()
supabase_logger = SupabaseLogger()

@app.before_request
def before_request():
    """Initialize session for each request"""
    init_auth_session()

@app.route('/')
def index():
    """Homepage with VIN and mileage input form"""
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check_eligibility():
    """Process VIN and mileage, return eligibility results"""
    vin = request.form.get('vin', '').strip().upper()
    mileage_str = request.form.get('mileage', '').strip()
    
    # Validate inputs
    if not vin or not mileage_str:
        flash('Please provide both VIN and mileage', 'error')
        return redirect(url_for('index'))
    
    try:
        mileage = int(mileage_str.replace(',', ''))
        if mileage < 0:
            raise ValueError("Negative mileage")
    except ValueError:
        flash('Please enter a valid mileage number', 'error')
        return redirect(url_for('index'))
    
    # Validate VIN format
    if not vin_decoder.validate_vin(vin):
        flash('Please enter a valid 17-character VIN', 'error')
        return redirect(url_for('index'))
    
    # Decode VIN
    vehicle_info = vin_decoder.decode_vin(vin)
    if not vehicle_info:
        flash('Unable to decode VIN. Please check the VIN and try again.', 'error')
        return redirect(url_for('index'))
    
    # Check eligibility
    eligibility_result = eligibility_checker.check_full_eligibility(vehicle_info, mileage)
    
    # Log to Supabase (optional - will not fail if Supabase is not configured)
    supabase_logger.log_vin_check(vin, mileage, vehicle_info, eligibility_result)
    
    # Calculate earnings estimate if eligible
    earnings_estimate = None
    if eligibility_result.get('eligible', False):
        earnings_estimate = supabase_logger.get_earnings_estimate(
            vehicle_info.get('make', ''),
            vehicle_info.get('model', ''),
            vehicle_info.get('year', 0)
        )
    
    # Store vehicle data in session for potential listing creation
    session['last_check'] = {
        'vin': vin,
        'mileage': mileage,
        'vehicle_info': vehicle_info,
        'eligibility_result': eligibility_result,
        'earnings_estimate': earnings_estimate
    }
    
    return render_template('result.html', 
                         vin=vin,
                         mileage=mileage,
                         vehicle_info=vehicle_info,
                         eligibility_result=eligibility_result,
                         earnings_estimate=earnings_estimate)

@app.route('/admin')
def admin():
    """Admin page showing recent checks (optional)"""
    if not supabase_logger.is_connected():
        flash('Database not configured', 'error')
        return redirect(url_for('index'))
    
    recent_checks = supabase_logger.get_recent_checks(25)
    return render_template('admin.html', recent_checks=recent_checks)

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple email-based login"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        if not email:
            flash('Please enter your email address', 'error')
            return render_template('login.html')
        
        if login_user(email, supabase_logger):
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login failed. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Log out current user"""
    logout_user()
    flash('Successfully logged out!', 'success')
    return redirect(url_for('index'))

@app.route('/pricing')
def pricing():
    """Pricing page for marketplace access"""
    return render_template('pricing.html')

@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    """Create Stripe checkout session"""
    user_email = session.get('user_email')
    
    if not user_email:
        flash('Please log in first', 'error')
        return redirect(url_for('login'))
    
    checkout_session = create_stripe_checkout_session(
        user_email,
        url_for('payment_success', _external=True),
        url_for('pricing', _external=True)
    )
    
    if checkout_session:
        return redirect(checkout_session.url, code=303)
    else:
        flash('Payment session could not be created', 'error')
        return redirect(url_for('pricing'))

@app.route('/payment-success')
@login_required
def payment_success():
    """Payment success page"""
    # Update session payment status
    session['is_paid'] = True
    flash('Payment successful! You now have access to the marketplace.', 'success')
    return redirect(url_for('marketplace'))

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    if handle_stripe_webhook(payload, sig_header):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'error': 'Invalid signature'}), 400

# Marketplace routes
@app.route('/marketplace')
def marketplace():
    """Public marketplace page"""
    listings = supabase_logger.get_active_listings()
    return render_template('marketplace.html', listings=listings)

@app.route('/list-vehicle')
@paid_user_required
def list_vehicle():
    """Create vehicle listing form"""
    # Check if user has a recent eligible vehicle check
    last_check = session.get('last_check')
    
    if not last_check or not last_check.get('eligibility_result', {}).get('eligible', False):
        flash('Please complete a successful eligibility check first', 'error')
        return redirect(url_for('index'))
    
    return render_template('list_vehicle.html', last_check=last_check)

@app.route('/create-listing', methods=['POST'])
@paid_user_required
def create_listing():
    """Create a new marketplace listing"""
    user_id = get_current_user_id()
    last_check = session.get('last_check')
    
    if not last_check or not last_check.get('eligibility_result', {}).get('eligible', False):
        flash('Please complete a successful eligibility check first', 'error')
        return redirect(url_for('index'))
    
    # Get form data
    location = request.form.get('location', '').strip()
    description = request.form.get('description', '').strip()
    availability = request.form.get('availability', 'available_now')
    
    if not location:
        flash('Please enter a location', 'error')
        return render_template('list_vehicle.html', last_check=last_check)
    
    # Create listing data
    vehicle_info = last_check['vehicle_info']
    listing_data = {
        'user_id': user_id,
        'vin': last_check['vin'],
        'mileage': last_check['mileage'],
        'year': vehicle_info.get('year'),
        'make': vehicle_info.get('make'),
        'model': vehicle_info.get('model'),
        'location': location,
        'description': description,
        'availability': availability,
        'estimated_earnings': last_check.get('earnings_estimate', 0),
        'images': []  # Will be populated by image uploads
    }
    
    # Create listing
    listing_id = supabase_logger.create_listing(listing_data)
    
    if listing_id:
        # Handle image uploads
        uploaded_files = request.files.getlist('images')
        image_urls = []
        
        for file in uploaded_files:
            if file and file.filename:
                filename = secure_filename(file.filename)
                image_url = supabase_logger.upload_listing_image(listing_id, file, filename)
                if image_url:
                    image_urls.append(image_url)
        
        # Update listing with image URLs if any were uploaded
        if image_urls:
            # Note: This would require an update_listing method in SupabaseLogger
            pass
        
        flash('Listing created successfully!', 'success')
        return redirect(url_for('my_listings'))
    else:
        flash('Failed to create listing. Please try again.', 'error')
        return render_template('list_vehicle.html', last_check=last_check)

@app.route('/my-listings')
@login_required
def my_listings():
    """Show current user's listings"""
    user_id = get_current_user_id()
    listings = supabase_logger.get_user_listings(user_id)
    return render_template('my_listings.html', listings=listings)

@app.route('/toggle-listing/<listing_id>')
@login_required
def toggle_listing(listing_id):
    """Toggle listing active status"""
    user_id = get_current_user_id()
    
    # Verify listing belongs to current user (simple security check)
    user_listings = supabase_logger.get_user_listings(user_id)
    listing_exists = any(listing['id'] == listing_id for listing in user_listings)
    
    if not listing_exists:
        flash('Listing not found', 'error')
        return redirect(url_for('my_listings'))
    
    # Toggle status (this is simplified - you might want to get current status first)
    supabase_logger.update_listing_status(listing_id, False)  # Deactivate for now
    flash('Listing status updated', 'success')
    
    return redirect(url_for('my_listings'))

@app.errorhandler(404)
def not_found(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    flash('An internal error occurred. Please try again.', 'error')
    return render_template('index.html'), 500

if __name__ == '__main__':
    # For development
    port = int(os.getenv('PORT', 5001))
    app.run(debug=False, host='0.0.0.0', port=port)