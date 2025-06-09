from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
import os
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from vin_utils import VINDecoder
from eligibility_rules import TuroEligibilityChecker
from supabase_client import SupabaseLogger
import base64
import uuid
import json
from auth import (
    init_auth_session, login_required, paid_user_required, 
    login_user, logout_user, get_current_user_id, is_current_user_paid,
    create_stripe_checkout_session, handle_stripe_webhook
)

# Load environment variables
load_dotenv()

# Initialize Stripe after loading environment variables
import stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
print(f"Stripe API key loaded: {bool(stripe.api_key)}")

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Initialize components
vin_decoder = VINDecoder()
eligibility_checker = TuroEligibilityChecker()
supabase_logger = SupabaseLogger()

# Debug: Check if environment variables are loaded
print(f"SUPABASE_URL loaded: {bool(os.getenv('SUPABASE_URL'))}")
print(f"SUPABASE_ANON_KEY loaded: {bool(os.getenv('SUPABASE_ANON_KEY'))}")
print(f"Supabase client connected: {supabase_logger.is_connected()}")

def generate_placeholder_image(year, make, model):
    """Generate a data URL for a placeholder image"""
    # Create SVG content
    svg_content = f"""<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#667eea"/>
  <text x="50%" y="40%" font-family="Arial, sans-serif" font-size="18" fill="#ffffff" text-anchor="middle" dominant-baseline="middle">🚗</text>
  <text x="50%" y="65%" font-family="Arial, sans-serif" font-size="14" fill="#ffffff" text-anchor="middle" dominant-baseline="middle">{year} {make} {model}</text>
</svg>"""
    
    # Encode as base64
    encoded = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
    return f"data:image/svg+xml;base64,{encoded}"

def save_uploaded_image(listing_id, image_file, filename):
    """Save uploaded image locally and return URL"""
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join('static', 'uploads', 'listings', listing_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename to avoid conflicts
        file_ext = os.path.splitext(filename)[1].lower()
        unique_filename = f"{str(uuid.uuid4())}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # Save the file
        image_file.seek(0)  # Reset file pointer
        image_file.save(file_path)
        
        # Return URL relative to static folder
        return f"/static/uploads/listings/{listing_id}/{unique_filename}"
        
    except Exception as e:
        print(f"Failed to save image locally: {e}")
        return None

# Global in-memory storage for listings (survives across requests)
GLOBAL_USER_LISTINGS = {}

def get_all_cached_listings():
    """Get all listings from all users in the global cache"""
    all_listings = []
    for user_id, listings in GLOBAL_USER_LISTINGS.items():
        all_listings.extend(listings)
    return all_listings

def migrate_cached_listings_to_database():
    """Migrate all cached listings to database (one-time operation)"""
    if not supabase_logger.is_connected():
        print("❌ Cannot migrate: Supabase not connected")
        return False
    
    try:
        migrated_count = 0
        for user_id, listings in GLOBAL_USER_LISTINGS.items():
            for listing in listings:
                # Try to create listing in database
                result = supabase_logger.create_listing(listing.copy())
                if result:
                    migrated_count += 1
                    print(f"✅ Migrated listing: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
                else:
                    print(f"❌ Failed to migrate: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
        
        print(f"🎉 Migration complete! Migrated {migrated_count} listings to database")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

def save_user_listings_to_cache(user_id, listings):
    """Save user listings to global memory cache"""
    try:
        GLOBAL_USER_LISTINGS[user_id] = listings.copy()
        print(f"Saved {len(listings)} listings to memory cache for user {user_id}")
        return True
    except Exception as e:
        print(f"Failed to save user listings to cache: {e}")
        return False

def load_user_listings_from_cache(user_id):
    """Load user listings from global memory cache"""
    try:
        listings = GLOBAL_USER_LISTINGS.get(user_id, [])
        if listings:
            print(f"Loaded {len(listings)} listings from memory cache for user {user_id}")
        return listings.copy() if listings else []
    except Exception as e:
        print(f"Failed to load user listings from cache: {e}")
        return []

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
        
        print(f"Login attempt for email: {email}")
        print(f"Supabase connected: {supabase_logger.is_connected()}")
        
        if not email:
            flash('Please enter your email address', 'error')
            return render_template('login.html')
        
        login_result = login_user(email, supabase_logger)
        print(f"Login result: {login_result}")
        
        if login_result:
            # Load cached listings for this user
            user_id = get_current_user_id()
            if user_id:
                cached_listings = load_user_listings_from_cache(user_id)
                if cached_listings:
                    session['user_listings'] = cached_listings
                    # Also add to marketplace listings
                    if 'all_listings' not in session:
                        session['all_listings'] = []
                    # Add user's cached listings to marketplace if not already there
                    existing_ids = {l.get('id') for l in session['all_listings']}
                    for listing in cached_listings:
                        if listing.get('id') not in existing_ids:
                            session['all_listings'].append(listing)
                    print(f"Restored {len(cached_listings)} listings for user {user_id}")
            
            flash('Successfully logged in!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login failed. Please try again.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Log out current user"""
    user_id = get_current_user_id()
    
    # Save user listings to a persistent store before logout
    if user_id and 'user_listings' in session:
        user_listings = session.get('user_listings', [])
        # Store in a simple file-based cache for demo
        save_user_listings_to_cache(user_id, user_listings)
        print(f"Saved {len(user_listings)} listings for user {user_id} to cache")
    
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

@app.route('/demo-payment')
@login_required
def demo_payment():
    """Demo payment bypass for testing"""
    session['is_paid'] = True
    flash('Demo payment successful! You now have marketplace access.', 'success')
    return redirect(url_for('marketplace'))

@app.route('/debug-session')
@login_required
def debug_session():
    """Debug session data"""
    return jsonify({
        'user_id': session.get('user_id'),
        'user_email': session.get('user_email'),
        'is_paid': session.get('is_paid'),
        'user_listings_count': len(session.get('user_listings', [])),
        'all_listings_count': len(session.get('all_listings', [])),
        'user_listings': session.get('user_listings', []),
        'all_listings': session.get('all_listings', [])
    })

@app.route('/migrate-database')
def migrate_database():
    """Migrate cached listings to database (admin only)"""
    cached_count = len(get_all_cached_listings())
    
    if not supabase_logger.is_connected():
        return jsonify({
            'success': False,
            'message': 'Supabase not connected. Please check environment variables and restart.',
            'cached_listings': cached_count,
            'global_cache_users': list(GLOBAL_USER_LISTINGS.keys()),
            'supabase_connected': False
        })
    
    success = migrate_cached_listings_to_database()
    
    return jsonify({
        'success': success,
        'message': f'Migration {"completed" if success else "failed"}',
        'cached_listings_found': cached_count,
        'global_cache_users': list(GLOBAL_USER_LISTINGS.keys()),
        'supabase_connected': supabase_logger.is_connected()
    })

@app.route('/debug-cache')
def debug_cache():
    """Debug the global cache state"""
    return jsonify({
        'global_cache_size': len(GLOBAL_USER_LISTINGS),
        'users_in_cache': list(GLOBAL_USER_LISTINGS.keys()),
        'total_listings': len(get_all_cached_listings()),
        'cache_details': {user_id: len(listings) for user_id, listings in GLOBAL_USER_LISTINGS.items()},
        'supabase_connected': supabase_logger.is_connected()
    })

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
    # Check session listings first
    session_listings = session.get('all_listings', [])
    print(f"Session marketplace listings found: {len(session_listings)}")
    
    # Add placeholder images to existing listings that don't have them or have broken URLs
    for listing in session_listings:
        print(f"Session marketplace listing: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
        images = listing.get('images', [])
        print(f"  Current images: {images}")
        needs_fix = False
        
        # Check if listing has no images
        if not images or len(images) == 0:
            needs_fix = True
            print(f"  No images found")
        
        # Check if listing has old via.placeholder URLs
        elif any('via.placeholder.com' in str(img) for img in images):
            needs_fix = True
            print(f"  Found old placeholder URLs")
        
        if needs_fix:
            placeholder_url = generate_placeholder_image(
                listing.get('year'), 
                listing.get('make'), 
                listing.get('model')
            )
            listing['images'] = [placeholder_url]
            print(f"  Added new SVG placeholder image")
        else:
            print(f"  Images OK, no fix needed")
    
    # Update session with modified listings
    if session_listings:
        session['all_listings'] = session_listings
    
    # Try to get listings from database
    listings = []
    try:
        db_listings = supabase_logger.get_active_listings()
        print(f"Database marketplace returned {len(db_listings)} listings")
        listings.extend(db_listings)
    except Exception as e:
        print(f"Failed to get database listings: {e}")
    
    # Add session listings
    if session_listings:
        print(f"Adding {len(session_listings)} session listings to marketplace")
        listings.extend(session_listings)
    else:
        print("No session marketplace listings found")
    
    # Add all cached listings from global memory
    cached_listings = get_all_cached_listings()
    if cached_listings:
        print(f"Adding {len(cached_listings)} cached listings to marketplace")
        # Avoid duplicates
        existing_ids = {l.get('id') for l in listings}
        for cached_listing in cached_listings:
            if cached_listing.get('id') not in existing_ids:
                listings.append(cached_listing)
    
    # If still no listings, show sample ones
    if not listings:
        print("No listings found, using samples")
        listings = supabase_logger._get_sample_listings()
    
    print(f"Showing {len(listings)} total listings in marketplace")
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
    
    print(f"Creating listing for user: {user_id}")
    print(f"Last check data: {last_check}")
    
    if not last_check or not last_check.get('eligibility_result', {}).get('eligible', False):
        flash('Please complete a successful eligibility check first', 'error')
        return redirect(url_for('index'))
    
    # Get form data
    location = request.form.get('location', '').strip()
    description = request.form.get('description', '').strip()
    availability = request.form.get('availability', 'available_now')
    
    print(f"Form data - Location: {location}, Description: {description}, Availability: {availability}")
    
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
    
    print(f"Listing data to create: {listing_data}")
    
    # Create listing - always store in session since database tables don't exist
    print("Creating listing...")
    listing_id = str(uuid.uuid4())
    listing_data['id'] = listing_id
    listing_data['created_at'] = datetime.now().isoformat()
    listing_data['is_active'] = True
    
    # Store in session (primary storage for demo)
    if 'user_listings' not in session:
        session['user_listings'] = []
    session['user_listings'].append(listing_data)
    
    # Also add to global session listings for marketplace
    if 'all_listings' not in session:
        session['all_listings'] = []
    session['all_listings'].append(listing_data)
    
    print(f"Stored listing in session: {listing_id}")
    print(f"Total user listings in session: {len(session['user_listings'])}")
    print(f"Total marketplace listings in session: {len(session['all_listings'])}")
    
    # Try database insert but don't rely on it
    try:
        db_result = supabase_logger.create_listing(listing_data.copy())
        if db_result:
            print(f"Also created in database: {db_result}")
    except Exception as e:
        print(f"Database failed (expected): {e}")
    
    if listing_id:
        # Handle image uploads - for demo, store as base64 or placeholder URLs
        uploaded_files = request.files.getlist('images')
        image_urls = []
        
        # Always add at least one placeholder image for better display
        placeholder_url = generate_placeholder_image(
            listing_data['year'], 
            listing_data['make'], 
            listing_data['model']
        )
        
        if uploaded_files and any(file.filename for file in uploaded_files):
            for i, file in enumerate(uploaded_files):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    print(f"Processing image: {filename}")
                    
                    # Try local storage first
                    local_url = save_uploaded_image(listing_id, file, filename)
                    if local_url:
                        image_urls.append(local_url)
                        print(f"Image saved locally: {local_url}")
                    else:
                        # Try Supabase storage as backup
                        supabase_url = supabase_logger.upload_listing_image(listing_id, file, filename)
                        if supabase_url:
                            image_urls.append(supabase_url)
                            print(f"Image uploaded to Supabase: {supabase_url}")
                        else:
                            # Use placeholder if both fail
                            image_urls.append(placeholder_url)
                            print(f"Both uploads failed, using placeholder")
        else:
            # No files uploaded, use placeholder
            image_urls.append(placeholder_url)
            print(f"No images uploaded, using placeholder")
        
        # Update listing with image URLs
        listing_data['images'] = image_urls
        
        # Update session listings with images
        if 'user_listings' in session:
            for listing in session['user_listings']:
                if listing['id'] == listing_id:
                    listing['images'] = image_urls
                    break
        
        if 'all_listings' in session:
            for listing in session['all_listings']:
                if listing['id'] == listing_id:
                    listing['images'] = image_urls
                    break
        
        print(f"Added {len(image_urls)} images to listing")
        
        # Save user listings to cache for persistence across sessions
        user_listings = session.get('user_listings', [])
        save_user_listings_to_cache(user_id, user_listings)
        
        flash('Listing created successfully!', 'success')
        return redirect(url_for('my_listings'))
    else:
        print("Failed to create listing in database")
        flash('Failed to create listing. Please try again.', 'error')
        return render_template('list_vehicle.html', last_check=last_check)

@app.route('/my-listings')
@login_required
def my_listings():
    """Show current user's listings"""
    user_id = get_current_user_id()
    
    # Check cached listings first
    cached_listings = load_user_listings_from_cache(user_id)
    print(f"Cached listings found: {len(cached_listings)}")
    
    # Check session listings
    session_listings = session.get('user_listings', [])
    print(f"Session listings found: {len(session_listings)}")
    
    # Merge cached and session listings
    all_user_listings = []
    seen_ids = set()
    
    for listing in cached_listings + session_listings:
        if listing.get('id') not in seen_ids:
            all_user_listings.append(listing)
            seen_ids.add(listing.get('id'))
    
    # Add placeholder images to existing listings that don't have them or have broken URLs
    for listing in all_user_listings:
        print(f"User listing: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
        images = listing.get('images', [])
        print(f"  Current images: {images}")
        needs_fix = False
        
        # Check if listing has no images
        if not images or len(images) == 0:
            needs_fix = True
            print(f"  No images found")
        
        # Check if listing has old via.placeholder URLs
        elif any('via.placeholder.com' in str(img) for img in images):
            needs_fix = True
            print(f"  Found old placeholder URLs")
        
        if needs_fix:
            placeholder_url = generate_placeholder_image(
                listing.get('year'), 
                listing.get('make'), 
                listing.get('model')
            )
            listing['images'] = [placeholder_url]
            print(f"  Added new SVG placeholder image")
        else:
            print(f"  Images OK, no fix needed")
    
    # Update both session and cache with modified listings
    session['user_listings'] = all_user_listings
    save_user_listings_to_cache(user_id, all_user_listings)
    
    # Try to get listings from database
    db_listings = []
    try:
        db_listings = supabase_logger.get_user_listings(user_id)
        print(f"Database returned {len(db_listings)} listings")
    except Exception as e:
        print(f"Failed to get database user listings: {e}")
    
    # Combine all listings (database + cached/session)
    final_listings = []
    seen_ids = set()
    
    # Add cached/session listings first (these are most up-to-date)
    for listing in all_user_listings:
        if listing.get('id') not in seen_ids:
            final_listings.append(listing)
            seen_ids.add(listing.get('id'))
    
    # Add database listings if not already present
    for listing in db_listings:
        if listing.get('id') not in seen_ids:
            final_listings.append(listing)
            seen_ids.add(listing.get('id'))
    
    print(f"Total listings to show: {len(final_listings)}")
    
    # Debug: Print each listing's image data
    for i, listing in enumerate(final_listings):
        print(f"Listing {i+1}: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
        print(f"  Images: {listing.get('images', 'No images key')}")
        print(f"  Images length: {len(listing.get('images', []))}")
    
    return render_template('my_listings.html', listings=final_listings)

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

# Contact request routes
@app.route('/contact-seller', methods=['POST'])
@paid_user_required
def contact_seller():
    """Create a contact request to a seller"""
    buyer_id = get_current_user_id()
    listing_id = request.form.get('listing_id')
    message = request.form.get('message', '').strip()
    
    if not listing_id:
        flash('Listing not found', 'error')
        return redirect(url_for('marketplace'))
    
    print(f"Contact request from buyer {buyer_id} for listing {listing_id}")
    
    # Get listing to find seller_id
    try:
        # Check all possible sources for the listing
        listing = None
        
        # 1. Check session listings
        session_listings = session.get('all_listings', []) + session.get('user_listings', [])
        for l in session_listings:
            if l.get('id') == listing_id:
                listing = l
                print(f"Found listing in session: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
                break
        
        # 2. Check cached listings (global memory)
        if not listing:
            cached_listings = get_all_cached_listings()
            for l in cached_listings:
                if l.get('id') == listing_id:
                    listing = l
                    print(f"Found listing in cache: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
                    break
        
        # 3. Check database
        if not listing:
            db_listings = supabase_logger.get_active_listings()
            for l in db_listings:
                if l.get('id') == listing_id:
                    listing = l
                    print(f"Found listing in database: {listing.get('year')} {listing.get('make')} {listing.get('model')}")
                    break
        
        if not listing:
            print(f"Listing {listing_id} not found in any source")
            flash('Listing not found', 'error')
            return redirect(url_for('marketplace'))
        
        seller_id = listing.get('user_id')
        if not seller_id:
            flash('Unable to contact seller', 'error')
            return redirect(url_for('marketplace'))
        
        # Prevent self-contact
        if buyer_id == seller_id:
            flash('You cannot contact yourself', 'error')
            return redirect(url_for('marketplace'))
        
        # Check for existing request
        if supabase_logger.check_existing_request(buyer_id, listing_id):
            flash('You already have a pending request for this listing', 'warning')
            return redirect(url_for('marketplace'))
        
        # Create contact request
        request_id = supabase_logger.create_contact_request(buyer_id, seller_id, listing_id, message)
        
        # Always store in session as backup (since DB might fail due to RLS)
        contact_request = {
            'id': request_id if request_id else str(uuid.uuid4()),
            'buyer_id': buyer_id,
            'seller_id': seller_id,
            'listing_id': listing_id,
            'status': 'pending',
            'message': message,
            'created_at': datetime.now().isoformat(),
            'buyer_email': session.get('user_email'),
            'listing_info': listing  # Store listing details for display
        }
        
        # Store in session
        if 'contact_requests' not in session:
            session['contact_requests'] = []
        session['contact_requests'].append(contact_request)
        
        print(f"Stored contact request in session: {contact_request['id']}")
        flash('Contact request sent successfully! The seller will be notified.', 'success')
        
    except Exception as e:
        print(f"Error creating contact request: {e}")
        flash('An error occurred. Please try again.', 'error')
    
    return redirect(url_for('marketplace'))

@app.route('/requests')
@login_required
def seller_requests():
    """Show contact requests for the current user (as seller)"""
    user_id = get_current_user_id()
    
    # Get requests from database
    db_requests = supabase_logger.get_seller_requests(user_id)
    print(f"Found {len(db_requests)} database seller requests for user {user_id}")
    
    # Get requests from session storage
    session_requests = session.get('contact_requests', [])
    seller_session_requests = [req for req in session_requests if req.get('seller_id') == user_id]
    print(f"Found {len(seller_session_requests)} session seller requests for user {user_id}")
    
    # Combine requests (session first since they're most recent)
    all_requests = seller_session_requests + db_requests
    
    # Remove duplicates by ID
    seen_ids = set()
    unique_requests = []
    for req in all_requests:
        if req.get('id') not in seen_ids:
            unique_requests.append(req)
            seen_ids.add(req.get('id'))
    
    print(f"Total unique seller requests: {len(unique_requests)}")
    
    return render_template('seller_requests.html', requests=unique_requests)

@app.route('/my-requests')
@login_required
def buyer_requests():
    """Show contact requests made by the current user (as buyer)"""
    user_id = get_current_user_id()
    
    # Get requests from database
    db_requests = supabase_logger.get_buyer_requests(user_id)
    print(f"Found {len(db_requests)} database buyer requests for user {user_id}")
    
    # Get requests from session storage
    session_requests = session.get('contact_requests', [])
    buyer_session_requests = [req for req in session_requests if req.get('buyer_id') == user_id]
    print(f"Found {len(buyer_session_requests)} session buyer requests for user {user_id}")
    
    # Combine requests (session first since they're most recent)
    all_requests = buyer_session_requests + db_requests
    
    # Remove duplicates by ID
    seen_ids = set()
    unique_requests = []
    for req in all_requests:
        if req.get('id') not in seen_ids:
            unique_requests.append(req)
            seen_ids.add(req.get('id'))
    
    print(f"Total unique buyer requests: {len(unique_requests)}")
    
    return render_template('buyer_requests.html', requests=unique_requests)

@app.route('/respond-request/<request_id>/<action>')
@login_required
def respond_to_request(request_id, action):
    """Accept or decline a contact request"""
    user_id = get_current_user_id()
    
    if action not in ['accept', 'decline']:
        flash('Invalid action', 'error')
        return redirect(url_for('seller_requests'))
    
    new_status = action + 'ed'
    
    # Update in database
    db_success = supabase_logger.update_contact_request_status(request_id, new_status)
    
    # Update in session storage
    session_requests = session.get('contact_requests', [])
    session_updated = False
    for req in session_requests:
        if req.get('id') == request_id and req.get('seller_id') == user_id:
            req['status'] = new_status
            session_updated = True
            break
    
    if session_updated:
        session['contact_requests'] = session_requests
        print(f"Updated contact request {request_id} status to {new_status} in session")
    
    success = db_success or session_updated
    
    if success:
        if action == 'accept':
            flash('Contact request accepted! You can now communicate with the buyer.', 'success')
            # TODO: Send email notification to buyer
        else:
            flash('Contact request declined.', 'info')
    else:
        flash('Failed to update request. Please try again.', 'error')
    
    return redirect(url_for('seller_requests'))

@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(os.path.join('static', 'uploads'), filename)

@app.errorhandler(404)
def not_found(error):
    return render_template('index.html'), 404

@app.errorhandler(500)
def internal_error(error):
    flash('An internal error occurred. Please try again.', 'error')
    return render_template('index.html'), 500

if __name__ == '__main__':
    # For development
    port = int(os.getenv('PORT', 5003))
    app.run(debug=False, host='0.0.0.0', port=port)