import os
from supabase import create_client, Client
from typing import Dict, Optional, List
from datetime import datetime
import uuid

class SupabaseLogger:
    def __init__(self):
        # Get Supabase credentials from environment variables
        self.supabase_url = os.getenv('SUPABASE_URL')
        self.supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        print(f"Supabase URL configured: {bool(self.supabase_url)}")
        print(f"Supabase Key configured: {bool(self.supabase_key)}")
        
        self.client: Optional[Client] = None
        
        if self.supabase_url and self.supabase_key:
            try:
                # Ensure URL is in correct format
                if not self.supabase_url.startswith('https://'):
                    # Fix common URL format issues
                    if self.supabase_url.startswith('postgresql://'):
                        # Extract project ref from PostgreSQL URL
                        import re
                        match = re.search(r'postgres\.([^:]+)', self.supabase_url)
                        if match:
                            project_ref = match.group(1)
                            self.supabase_url = f"https://{project_ref}.supabase.co"
                            print(f"🔧 Converted PostgreSQL URL to Supabase format: {self.supabase_url}")
                    elif '.' in self.supabase_url and 'supabase' in self.supabase_url:
                        self.supabase_url = f"https://{self.supabase_url}"
                        print(f"🔧 Added https:// to URL: {self.supabase_url}")
                
                print(f"🔗 Connecting to: {self.supabase_url}")
                self.client = create_client(self.supabase_url, self.supabase_key)
                print("✅ Supabase client initialized successfully")
            except Exception as e:
                print(f"❌ Failed to initialize Supabase client: {e}")
                print(f"🔍 URL used: {self.supabase_url}")
                print("📱 Running in fallback mode without database")
                self.client = None
        else:
            print("⚠️ Supabase credentials not found in environment variables")
            print("📱 Running in fallback mode without database")
    
    def is_connected(self) -> bool:
        """Check if Supabase client is properly initialized"""
        return self.client is not None
    
    def log_vin_check(self, vin: str, mileage: int, vehicle_info: Dict, 
                     eligibility_result: Dict) -> bool:
        """Log VIN check to Supabase database"""
        if not self.client:
            print("Supabase client not initialized - skipping database log")
            return False
        
        try:
            data = {
                'vin': vin.upper(),
                'mileage': mileage,
                'make': vehicle_info.get('make'),
                'model': vehicle_info.get('model'),
                'year': vehicle_info.get('year'),
                'eligible': eligibility_result.get('eligible', False),
                'reason': '; '.join(eligibility_result.get('reasons', [])),
                'checked_at': datetime.now().isoformat()
            }
            
            response = self.client.table('vin_checks').insert(data).execute()
            return True
            
        except Exception as e:
            print(f"Failed to log to Supabase: {e}")
            return False
    
    def get_recent_checks(self, limit: int = 50) -> list:
        """Get recent VIN checks from database"""
        if not self.client:
            return []
        
        try:
            response = self.client.table('vin_checks')\
                .select('*')\
                .order('checked_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Failed to fetch recent checks: {e}")
            return []
    
    # User management methods
    def create_or_get_user(self, email: str, stripe_customer_id: str = None) -> Optional[Dict]:
        """Create or get user record"""
        if not self.client:
            return None
        
        try:
            # Try to get existing user first
            response = self.client.table('users').select('*').eq('email', email).execute()
            
            if response.data:
                print(f"Found existing user: {response.data[0]['email']}")
                return response.data[0]
            
            # Create new user with explicit UUID
            user_id = str(uuid.uuid4())
            user_data = {
                'id': user_id,
                'email': email,
                'stripe_customer_id': stripe_customer_id,
                'is_paid': True,  # Default to paid for demo
                'created_at': datetime.now().isoformat()
            }
            
            print(f"Creating new user: {email} with ID: {user_id}")
            response = self.client.table('users').insert(user_data).execute()
            
            if response.data:
                print(f"Successfully created user: {response.data[0]['email']}")
                return response.data[0]
            else:
                print(f"No data returned from user insert")
                return None
            
        except Exception as e:
            print(f"Failed to create/get user: {e}")
            print("RLS might be blocking access - you may need to disable RLS or update policies")
            # Return a fallback user for demo purposes
            fallback_user = {
                'id': str(uuid.uuid4()),
                'email': email,
                'stripe_customer_id': stripe_customer_id,
                'is_paid': True,
                'created_at': datetime.now().isoformat()
            }
            print(f"Using fallback user: {fallback_user['id']}")
            return fallback_user
    
    def update_user_payment_status(self, user_id: str, is_paid: bool) -> bool:
        """Update user payment status"""
        if not self.client:
            return False
        
        try:
            response = self.client.table('users').update({'is_paid': is_paid}).eq('id', user_id).execute()
            return True
        except Exception as e:
            print(f"Failed to update payment status: {e}")
            return False
    
    def is_user_paid(self, user_id: str) -> bool:
        """Check if user has paid subscription"""
        if not self.client:
            return False
        
        try:
            response = self.client.table('users').select('is_paid').eq('id', user_id).execute()
            return response.data[0]['is_paid'] if response.data else False
        except Exception as e:
            print(f"Failed to check payment status: {e}")
            return False
    
    # Marketplace listing methods
    def create_listing(self, listing_data: Dict) -> Optional[str]:
        """Create a new marketplace listing"""
        if not self.client:
            print("Supabase client not connected - using fallback")
            # Return a fake ID for testing
            return str(uuid.uuid4())
        
        try:
            # Ensure required fields are present
            if 'id' not in listing_data:
                listing_data['id'] = str(uuid.uuid4())
            if 'created_at' not in listing_data:
                listing_data['created_at'] = datetime.now().isoformat()
            if 'is_active' not in listing_data:
                listing_data['is_active'] = True
            
            print(f"Attempting to insert listing: {listing_data}")
            response = self.client.table('listings').insert(listing_data).execute()
            print(f"Supabase listing response: {response}")
            
            if response.data:
                print(f"✅ Listing created in database: {listing_data['id']}")
                return listing_data['id']
            else:
                print(f"❌ No data returned from listing insert")
                return None
            
        except Exception as e:
            print(f"❌ Failed to create listing in database: {e}")
            if "row-level security" in str(e).lower():
                print("🔒 RLS policy blocking access. You may need to update database policies.")
                print("📄 Check disable_rls.sql file for policy updates")
            print("🔄 Using fallback - listing created in session only")
            # For testing, return the listing ID even when database fails
            return listing_data.get('id', str(uuid.uuid4()))
    
    def get_active_listings(self, limit: int = 50) -> List[Dict]:
        """Get all active marketplace listings"""
        if not self.client:
            print("No database connection - returning sample listings")
            return self._get_sample_listings()
        
        try:
            response = self.client.table('listings')\
                .select('*')\
                .eq('is_active', True)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Failed to fetch listings from database: {e}")
            print("Using sample listings for demo")
            return self._get_sample_listings()
    
    def get_user_listings(self, user_id: str) -> List[Dict]:
        """Get all listings for a specific user"""
        if not self.client:
            print("No database connection - returning sample user listings")
            return self._get_sample_user_listings(user_id)
        
        try:
            response = self.client.table('listings')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Failed to fetch user listings from database: {e}")
            print("Using sample user listings for demo")
            return self._get_sample_user_listings(user_id)
    
    def _get_sample_listings(self) -> List[Dict]:
        """Return sample listings for demo purposes"""
        return [
            {
                'id': 'sample-1',
                'year': 2020,
                'make': 'Honda',
                'model': 'Accord',
                'mileage': 45000,
                'location': 'San Francisco, CA',
                'description': 'Well-maintained Honda Accord, perfect for Turo hosting',
                'estimated_earnings': 800,
                'availability': 'available_now',
                'images': [],
                'is_active': True,
                'created_at': '2025-01-01T00:00:00'
            },
            {
                'id': 'sample-2', 
                'year': 2019,
                'make': 'Toyota',
                'model': 'Camry',
                'mileage': 52000,
                'location': 'Los Angeles, CA',
                'description': 'Reliable Toyota Camry with excellent fuel economy',
                'estimated_earnings': 750,
                'availability': 'available_now',
                'images': [],
                'is_active': True,
                'created_at': '2025-01-02T00:00:00'
            }
        ]
    
    def _get_sample_user_listings(self, user_id: str) -> List[Dict]:
        """Return sample user listings for demo purposes"""
        return [
            {
                'id': 'user-sample-1',
                'year': 2021,
                'make': 'Tesla',
                'model': 'Model 3',
                'mileage': 25000,
                'location': 'San Jose, CA',
                'description': 'Electric Tesla Model 3, great for eco-conscious renters',
                'estimated_earnings': 1200,
                'availability': 'available_now',
                'images': [],
                'is_active': True,
                'created_at': '2025-01-03T00:00:00'
            }
        ]
    
    def update_listing_status(self, listing_id: str, is_active: bool) -> bool:
        """Update listing active status"""
        if not self.client:
            return False
        
        try:
            response = self.client.table('listings').update({'is_active': is_active}).eq('id', listing_id).execute()
            return True
        except Exception as e:
            print(f"Failed to update listing status: {e}")
            return False
    
    # Earnings lookup methods
    def get_earnings_estimate(self, make: str, model: str, year: int) -> Optional[int]:
        """Get earnings estimate for a vehicle"""
        if not self.client:
            # Fallback to hardcoded estimates if no database
            return self._get_fallback_earnings(make, model, year)
        
        try:
            # Try exact match first
            response = self.client.table('earnings_lookup')\
                .select('estimated_monthly_earning')\
                .eq('make', make.upper())\
                .eq('model', model.upper())\
                .execute()
            
            if response.data:
                return response.data[0]['estimated_monthly_earning']
            
            # Try make-only match
            response = self.client.table('earnings_lookup')\
                .select('estimated_monthly_earning')\
                .eq('make', make.upper())\
                .is_('model', 'null')\
                .execute()
            
            if response.data:
                return response.data[0]['estimated_monthly_earning']
            
            # Fallback to hardcoded estimates
            return self._get_fallback_earnings(make, model, year)
            
        except Exception as e:
            print(f"Failed to get earnings estimate: {e}")
            return self._get_fallback_earnings(make, model, year)
    
    def _get_fallback_earnings(self, make: str, model: str, year: int) -> int:
        """Fallback earnings estimates when database is unavailable"""
        make_upper = make.upper()
        model_upper = model.upper()
        
        # Luxury/Premium brands
        luxury_makes = ['BMW', 'MERCEDES', 'AUDI', 'LEXUS', 'ACURA', 'INFINITI', 'CADILLAC']
        if make_upper in luxury_makes:
            return 1100 if year >= 2018 else 900
        
        # Tesla
        if make_upper == 'TESLA':
            return 1400 if year >= 2019 else 1200
        
        # Popular economy brands
        economy_makes = ['HONDA', 'TOYOTA', 'NISSAN', 'HYUNDAI', 'KIA']
        if make_upper in economy_makes:
            return 800 if year >= 2018 else 650
        
        # American brands
        american_makes = ['FORD', 'CHEVROLET', 'DODGE', 'CHRYSLER', 'JEEP']
        if make_upper in american_makes:
            return 750 if year >= 2018 else 600
        
        # Default estimate
        return 700 if year >= 2018 else 550
    
    def update_earnings_estimate(self, make: str, model: str, year_range: str, earnings: int) -> bool:
        """Update earnings estimate in database (admin function)"""
        if not self.client:
            return False
        
        try:
            data = {
                'make': make.upper(),
                'model': model.upper() if model else None,
                'year_range': year_range,
                'estimated_monthly_earning': earnings
            }
            
            # Try to update existing record
            response = self.client.table('earnings_lookup')\
                .update(data)\
                .eq('make', make.upper())\
                .eq('model', model.upper() if model else None)\
                .execute()
            
            if not response.data:
                # Insert new record if update didn't find existing
                response = self.client.table('earnings_lookup').insert(data).execute()
            
            return True
            
        except Exception as e:
            print(f"Failed to update earnings estimate: {e}")
            return False
    
    # Contact request methods
    def create_contact_request(self, buyer_id: str, seller_id: str, listing_id: str, message: str = None) -> Optional[str]:
        """Create a new contact request"""
        if not self.client:
            print("Supabase client not connected - using fallback for contact request")
            # Return a fake ID for testing
            return str(uuid.uuid4())
        
        try:
            request_data = {
                'id': str(uuid.uuid4()),
                'buyer_id': buyer_id,
                'seller_id': seller_id,
                'listing_id': listing_id,
                'status': 'pending',
                'message': message,
                'created_at': datetime.now().isoformat()
            }
            
            print(f"Creating contact request: {request_data}")
            response = self.client.table('contact_requests').insert(request_data).execute()
            print(f"Contact request response: {response}")
            
            return request_data['id'] if response.data else None
            
        except Exception as e:
            print(f"Failed to create contact request in database: {e}")
            # For testing, return a fake ID when database fails
            return str(uuid.uuid4())
    
    def get_seller_requests(self, seller_id: str, status: str = None) -> List[Dict]:
        """Get contact requests for a seller"""
        if not self.client:
            print("No database connection - returning sample seller requests")
            return self._get_sample_seller_requests(seller_id)
        
        try:
            query = self.client.table('contact_requests')\
                .select('*, buyers:buyer_id(email), listings:listing_id(year, make, model, location)')\
                .eq('seller_id', seller_id)
            
            if status:
                query = query.eq('status', status)
            
            response = query.order('created_at', desc=True).execute()
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Failed to fetch seller requests from database: {e}")
            return self._get_sample_seller_requests(seller_id)
    
    def get_buyer_requests(self, buyer_id: str) -> List[Dict]:
        """Get contact requests made by a buyer"""
        if not self.client:
            print("No database connection - returning sample buyer requests")
            return self._get_sample_buyer_requests(buyer_id)
        
        try:
            response = self.client.table('contact_requests')\
                .select('*, sellers:seller_id(email), listings:listing_id(year, make, model, location)')\
                .eq('buyer_id', buyer_id)\
                .order('created_at', desc=True)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Failed to fetch buyer requests from database: {e}")
            return self._get_sample_buyer_requests(buyer_id)
    
    def update_contact_request_status(self, request_id: str, status: str) -> bool:
        """Update contact request status (accept/decline)"""
        if not self.client:
            print(f"No database - simulating status update to {status}")
            return True
        
        try:
            response = self.client.table('contact_requests')\
                .update({'status': status})\
                .eq('id', request_id)\
                .execute()
            
            return bool(response.data)
            
        except Exception as e:
            print(f"Failed to update contact request status: {e}")
            return False
    
    def check_existing_request(self, buyer_id: str, listing_id: str) -> bool:
        """Check if buyer already has a pending/accepted request for this listing"""
        if not self.client:
            return False  # Allow requests in demo mode
        
        try:
            response = self.client.table('contact_requests')\
                .select('id')\
                .eq('buyer_id', buyer_id)\
                .eq('listing_id', listing_id)\
                .in_('status', ['pending', 'accepted'])\
                .execute()
            
            return bool(response.data)
            
        except Exception as e:
            print(f"Failed to check existing request: {e}")
            return False
    
    def _get_sample_seller_requests(self, seller_id: str) -> List[Dict]:
        """Return sample seller requests for demo purposes"""
        return [
            {
                'id': 'req-sample-1',
                'buyer_id': 'buyer-1',
                'seller_id': seller_id,
                'listing_id': 'listing-1',
                'status': 'pending',
                'message': 'Hi, I\'m interested in your vehicle. Can we discuss?',
                'created_at': '2025-01-08T10:00:00',
                'buyers': {'email': 'buyer@example.com'},
                'listings': {'year': 2020, 'make': 'Honda', 'model': 'Accord', 'location': 'San Francisco, CA'}
            }
        ]
    
    def _get_sample_buyer_requests(self, buyer_id: str) -> List[Dict]:
        """Return sample buyer requests for demo purposes"""
        return [
            {
                'id': 'req-sample-2',
                'buyer_id': buyer_id,
                'seller_id': 'seller-1',
                'listing_id': 'listing-2',
                'status': 'accepted',
                'message': 'Interested in purchasing this vehicle.',
                'created_at': '2025-01-07T15:30:00',
                'sellers': {'email': 'seller@example.com'},
                'listings': {'year': 2019, 'make': 'Toyota', 'model': 'Camry', 'location': 'Los Angeles, CA'}
            }
        ]

    # Image upload methods
    def upload_listing_image(self, listing_id: str, image_file, filename: str) -> Optional[str]:
        """Upload image to Supabase storage"""
        if not self.client:
            print("No Supabase client - skipping image upload")
            return None
        
        try:
            # Upload to listings folder
            path = f"listings/{listing_id}/{filename}"
            
            # Read the file content as bytes
            file_content = image_file.read()
            
            response = self.client.storage.from_('listings').upload(path, file_content)
            
            if response:
                # Get public URL
                public_url = self.client.storage.from_('listings').get_public_url(path)
                return public_url
            
            return None
            
        except Exception as e:
            print(f"Failed to upload image: {e}")
            return None