from flask import Flask, render_template, request, redirect, url_for, flash
import os
from vin_utils import VINDecoder
from eligibility_rules import TuroEligibilityChecker
from supabase_client import SupabaseLogger

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Initialize components
vin_decoder = VINDecoder()
eligibility_checker = TuroEligibilityChecker()
supabase_logger = SupabaseLogger()

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
    
    return render_template('result.html', 
                         vin=vin,
                         mileage=mileage,
                         vehicle_info=vehicle_info,
                         eligibility_result=eligibility_result)

@app.route('/admin')
def admin():
    """Admin page showing recent checks (optional)"""
    if not supabase_logger.is_connected():
        flash('Database not configured', 'error')
        return redirect(url_for('index'))
    
    recent_checks = supabase_logger.get_recent_checks(25)
    return render_template('admin.html', recent_checks=recent_checks)

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