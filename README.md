# Turo Vehicle Eligibility Checker & Marketplace

A comprehensive web application that checks vehicle eligibility for Turo and provides a marketplace for connecting vehicle owners with potential Turo hosts.

## Features

### Core Eligibility Checking
- **VIN Decoding**: Uses NHTSA VIN Decoder API to get vehicle information
- **Eligibility Validation**: Checks against Turo's requirements:
  - Vehicle must be less than 12 years old
  - Mileage must be less than 130,000 miles
  - Vehicle must not be on the ineligible makes/models list
  - VIN must be valid and decodable
- **Earnings Estimates**: Shows potential monthly earnings on Turo

### Marketplace Features (Paid Users)
- **Vehicle Listings**: List eligible vehicles with photos and descriptions
- **Location-Based Search**: Find vehicles by location/ZIP code
- **Earnings Display**: Show estimated monthly earnings for each listing
- **User Management**: Secure authentication and subscription system
- **Image Uploads**: Up to 5 photos per vehicle listing
- **Listing Management**: Dashboard to manage active/inactive listings

### Technical Features
- **Modern UI**: Clean, Uber-inspired design
- **Stripe Integration**: Secure payment processing for subscriptions
- **Database Logging**: Supabase integration for data storage
- **Admin Dashboard**: View recent checks and manage earnings data
- **Responsive Design**: Works on desktop and mobile devices

## Installation

1. **Clone and navigate to the project:**
   ```bash
   cd turo_checker_app
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables (optional):**
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials if using database logging
   ```

4. **Run the application:**
   ```bash
   python app.py
   ```

5. **Open in browser:**
   ```
   http://localhost:5000
   ```

## Usage

1. Enter a 17-character VIN number
2. Enter the vehicle's current mileage
3. Click "Check eligibility"
4. View the detailed eligibility results

## Supabase Setup (Required for Marketplace)

### Database Schema

Create these tables in your Supabase project:

#### 1. VIN Checks Table
```sql
CREATE TABLE vin_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vin TEXT NOT NULL,
    mileage INTEGER NOT NULL,
    make TEXT,
    model TEXT,
    year INTEGER,
    eligible BOOLEAN,
    reason TEXT,
    checked_at TIMESTAMP DEFAULT NOW()
);
```

#### 2. Users Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    stripe_customer_id TEXT,
    is_paid BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 3. Listings Table
```sql
CREATE TABLE listings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    vin TEXT,
    mileage INTEGER,
    year INTEGER,
    make TEXT,
    model TEXT,
    location TEXT,
    description TEXT,
    availability TEXT DEFAULT 'available_now',
    images TEXT[], -- array of image URLs
    estimated_earnings INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
```

#### 4. Earnings Lookup Table (Optional)
```sql
CREATE TABLE earnings_lookup (
    make TEXT,
    model TEXT,
    year_range TEXT, -- e.g. '2018-2022'
    estimated_monthly_earning INTEGER
);
```

### Storage Setup
1. Create a storage bucket named `listings` for vehicle images
2. Set appropriate policies for public read access

### Configuration
Add your Supabase credentials to the `.env` file

## Tech Stack

- **Backend**: Python + Flask
- **Frontend**: HTML/CSS + Jinja2 templates
- **Database**: Supabase (PostgreSQL)
- **Payments**: Stripe for subscription management
- **Storage**: Supabase Storage for vehicle images
- **External API**: NHTSA VIN Decoder API
- **Authentication**: Session-based with email login
- **Styling**: Custom CSS with modern, responsive design

## Project Structure

```
/turo_checker_app
├── app.py                    # Main Flask application with all routes
├── auth.py                   # Authentication and Stripe integration
├── vin_utils.py             # VIN decoding logic
├── eligibility_rules.py     # Turo eligibility rules
├── supabase_client.py       # Database and storage operations
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── templates/
│   ├── index.html          # Homepage with VIN checker
│   ├── result.html         # Eligibility results with marketplace options
│   ├── login.html          # User authentication
│   ├── pricing.html        # Subscription pricing page
│   ├── marketplace.html    # Public vehicle marketplace
│   ├── list_vehicle.html   # Vehicle listing form
│   ├── my_listings.html    # User's listings dashboard
│   └── admin.html          # Admin dashboard
└── static/
    └── styles.css          # Comprehensive CSS styling
```

## Deployment

The app can be deployed to platforms like:
- Render
- Railway
- Replit
- Heroku
- Any platform supporting Python Flask apps

## Notes

- This is an unofficial tool for reference only
- Turo's actual eligibility requirements may vary
- The app works without Supabase (logging will be skipped)
- VIN validation follows standard VIN format rules