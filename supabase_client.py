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
        
        self.client: Optional[Client] = None
        
        if self.supabase_url and self.supabase_key:
            try:
                self.client = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                print(f"Failed to initialize Supabase client: {e}")
    
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
            # Try to get existing user
            response = self.client.table('users').select('*').eq('email', email).execute()
            
            if response.data:
                return response.data[0]
            
            # Create new user
            user_data = {
                'id': str(uuid.uuid4()),
                'email': email,
                'stripe_customer_id': stripe_customer_id,
                'is_paid': False,
                'created_at': datetime.now().isoformat()
            }
            
            response = self.client.table('users').insert(user_data).execute()
            return response.data[0] if response.data else None
            
        except Exception as e:
            print(f"Failed to create/get user: {e}")
            return None
    
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
            return None
        
        try:
            listing_data['id'] = str(uuid.uuid4())
            listing_data['created_at'] = datetime.now().isoformat()
            listing_data['is_active'] = True
            
            response = self.client.table('listings').insert(listing_data).execute()
            return listing_data['id'] if response.data else None
            
        except Exception as e:
            print(f"Failed to create listing: {e}")
            return None
    
    def get_active_listings(self, limit: int = 50) -> List[Dict]:
        """Get all active marketplace listings"""
        if not self.client:
            return []
        
        try:
            response = self.client.table('listings')\
                .select('*')\
                .eq('is_active', True)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Failed to fetch listings: {e}")
            return []
    
    def get_user_listings(self, user_id: str) -> List[Dict]:
        """Get all listings for a specific user"""
        if not self.client:
            return []
        
        try:
            response = self.client.table('listings')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .execute()
            
            return response.data if response.data else []
            
        except Exception as e:
            print(f"Failed to fetch user listings: {e}")
            return []
    
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
    
    # Image upload methods
    def upload_listing_image(self, listing_id: str, image_file, filename: str) -> Optional[str]:
        """Upload image to Supabase storage"""
        if not self.client:
            return None
        
        try:
            # Upload to listings folder
            path = f"listings/{listing_id}/{filename}"
            
            response = self.client.storage.from_('listings').upload(path, image_file)
            
            if response:
                # Get public URL
                public_url = self.client.storage.from_('listings').get_public_url(path)
                return public_url
            
            return None
            
        except Exception as e:
            print(f"Failed to upload image: {e}")
            return None