import requests
import re
from typing import Dict, Optional

class VINDecoder:
    def __init__(self):
        self.base_url = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVin"
    
    def validate_vin(self, vin: str) -> bool:
        """Validate VIN format (17 characters, alphanumeric excluding I, O, Q)"""
        if len(vin) != 17:
            return False
        
        # VIN pattern: no I, O, or Q allowed
        pattern = r'^[A-HJ-NPR-Z0-9]{17}$'
        return bool(re.match(pattern, vin.upper()))
    
    def decode_vin(self, vin: str) -> Optional[Dict]:
        """Decode VIN using NHTSA API"""
        if not self.validate_vin(vin):
            return None
        
        try:
            url = f"{self.base_url}/{vin.upper()}?format=json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'Results' not in data:
                return None
            
            # Extract relevant information
            vehicle_info = {
                'make': None,
                'model': None,
                'year': None,
                'body_class': None,
                'title_status': 'Clean'  # Default to clean title
            }
            
            for result in data['Results']:
                variable = result.get('Variable', '').lower()
                value = result.get('Value')
                
                if value and value != 'Not Applicable':
                    if 'make' in variable and not vehicle_info['make']:
                        vehicle_info['make'] = value
                    elif 'model' in variable and 'year' not in variable and not vehicle_info['model']:
                        vehicle_info['model'] = value
                    elif 'model year' in variable:
                        try:
                            vehicle_info['year'] = int(value)
                        except (ValueError, TypeError):
                            pass
                    elif 'body class' in variable:
                        vehicle_info['body_class'] = value
                    elif 'title' in variable or 'brand' in variable:
                        # Check for title status indicators
                        if any(keyword in value.lower() for keyword in ['salvage', 'flood', 'lemon', 'rebuilt', 'junk']):
                            vehicle_info['title_status'] = value
                        elif 'clean' in value.lower():
                            vehicle_info['title_status'] = 'Clean'
            
            return vehicle_info if vehicle_info['make'] and vehicle_info['year'] else None
            
        except requests.RequestException:
            return None
        except Exception:
            return None