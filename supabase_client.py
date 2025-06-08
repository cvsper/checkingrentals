import os
from supabase import create_client, Client
from typing import Dict, Optional
from datetime import datetime

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