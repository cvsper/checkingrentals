# Turo Vehicle Eligibility Checker

A web application that checks whether a vehicle is eligible to be listed on Turo based on VIN number and mileage.

## Features

- **VIN Decoding**: Uses NHTSA VIN Decoder API to get vehicle information
- **Eligibility Checking**: Validates against Turo's requirements:
  - Vehicle must be less than 12 years old
  - Mileage must be less than 130,000 miles
  - Vehicle must not be on the ineligible makes/models list
  - VIN must be valid and decodable
- **Modern UI**: Clean, Uber-inspired design
- **Database Logging**: Optional Supabase integration for storing check results
- **Admin Dashboard**: View recent eligibility checks

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

## Supabase Setup (Optional)

If you want to log eligibility checks to a database:

1. Create a Supabase project at https://supabase.com
2. Create the `vin_checks` table:

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

3. Add your Supabase URL and anon key to the `.env` file

## Tech Stack

- **Backend**: Python + Flask
- **Frontend**: HTML/CSS + Jinja2 templates
- **Database**: Supabase (PostgreSQL) - optional
- **External API**: NHTSA VIN Decoder API
- **Styling**: Custom CSS with modern design

## Project Structure

```
/turo_checker_app
├── app.py                 # Main Flask application
├── vin_utils.py          # VIN decoding logic
├── eligibility_rules.py  # Turo eligibility rules
├── supabase_client.py    # Database logging
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
├── templates/
│   ├── index.html       # Homepage
│   ├── result.html      # Results page
│   └── admin.html       # Admin dashboard
└── static/
    └── styles.css       # CSS styling
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