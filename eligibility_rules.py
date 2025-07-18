from datetime import datetime
from typing import Dict, List, Tuple

class TuroEligibilityChecker:
    def __init__(self):
        self.max_vehicle_age = 12
        self.max_mileage = 130000
        self.current_year = datetime.now().year
        
        # List of ineligible makes/models (commonly restricted on Turo)
        self.ineligible_makes = {
            'LOTUS', 'MCLAREN', 'FERRARI', 'LAMBORGHINI', 'BUGATTI', 
            'KOENIGSEGG', 'PAGANI', 'MAYBACH', 'ROLLS-ROYCE', 'BENTLEY',
            'ASTON MARTIN', 'MASERATI'
        }
        
        # Specific ineligible models (even if make is generally allowed)
        self.ineligible_models = {
            'DODGE': ['VIPER', 'CHALLENGER HELLCAT', 'CHARGER HELLCAT'],
            'CHEVROLET': ['CORVETTE ZR1', 'CORVETTE Z06'],
            'FORD': ['GT', 'SHELBY GT500'],
            'NISSAN': ['GT-R'],
            'HONDA': ['NSX'],
            'ACURA': ['NSX'],
            'BMW': ['I8', 'M8'],
            'MERCEDES': ['AMG GT', 'SLS AMG'],
            'AUDI': ['R8'],
            'PORSCHE': ['911 TURBO', '918 SPYDER', 'CARRERA GT']
        }
    
    def check_age_eligibility(self, model_year: int) -> Tuple[bool, str]:
        """Check if vehicle meets age requirements"""
        if not model_year:
            return False, "Unable to determine model year"
        
        vehicle_age = self.current_year - model_year
        
        if vehicle_age > self.max_vehicle_age:
            return False, f"Vehicle is {vehicle_age} years old (maximum allowed: {self.max_vehicle_age} years)"
        
        return True, f"Vehicle age: {vehicle_age} years (within limit)"
    
    def check_mileage_eligibility(self, mileage: int) -> Tuple[bool, str]:
        """Check if vehicle meets mileage requirements"""
        if mileage > self.max_mileage:
            return False, f"Mileage {mileage:,} exceeds maximum of {self.max_mileage:,} miles"
        
        return True, f"Mileage: {mileage:,} miles (within limit)"
    
    def check_make_model_eligibility(self, make: str, model: str = None) -> Tuple[bool, str]:
        """Check if make/model is eligible"""
        if not make:
            return False, "Unable to determine vehicle make"
        
        make_upper = make.upper()
        
        # Check if make is completely ineligible
        if make_upper in self.ineligible_makes:
            return False, f"{make} vehicles are not eligible for Turo"
        
        # Check specific model restrictions
        if model and make_upper in self.ineligible_models:
            model_upper = model.upper()
            for ineligible_model in self.ineligible_models[make_upper]:
                if ineligible_model in model_upper:
                    return False, f"{make} {model} is not eligible for Turo"
        
        return True, f"{make} {model or ''} is eligible by make/model"
    
    def check_title_status_eligibility(self, title_status: str) -> Tuple[bool, str]:
        """Check if vehicle title status is eligible for Turo"""
        if not title_status:
            return False, "Title status verification required - cannot determine eligibility without valid title information"
        
        title_status_upper = title_status.upper()
        
        # Check for unknown/unverified status
        if 'UNKNOWN' in title_status_upper or 'VERIFICATION REQUIRED' in title_status_upper:
            return False, "Title status must be verified before determining Turo eligibility. Please check your vehicle title document."
        
        # List of problematic title statuses that make vehicles ineligible
        problematic_statuses = [
            'SALVAGE', 'FLOOD', 'LEMON', 'REBUILT', 'JUNK', 'TOTAL LOSS',
            'FIRE', 'HAIL', 'WATER', 'DAMAGED', 'RECONSTRUCTED', 'DISMANTLED',
            'PARTS ONLY', 'NON-REPAIRABLE', 'CERTIFICATE OF DESTRUCTION',
            'BRANDED', 'PRIOR SALVAGE', 'PRIOR FLOOD', 'MANUFACTURER BUYBACK'
        ]
        
        # Check if title contains any problematic keywords
        for status in problematic_statuses:
            if status in title_status_upper:
                return False, f"Vehicles with {title_status} titles are not eligible for Turo"
        
        # Only accept explicitly clean titles
        if 'CLEAN' in title_status_upper or 'CLEAR' in title_status_upper:
            return True, f"Title status: {title_status} (eligible)"
        
        # If title status is not explicitly clean or contains unknown terms
        return False, f"Title status '{title_status}' requires manual verification. Only vehicles with verified clean titles are eligible for Turo."
    
    def check_full_eligibility(self, vehicle_info: Dict, mileage: int) -> Dict:
        """Perform complete eligibility check"""
        make = vehicle_info.get('make', '')
        model = vehicle_info.get('model', '')
        year = vehicle_info.get('year')
        title_status = vehicle_info.get('title_status', 'Clean')
        
        # Individual checks
        age_eligible, age_reason = self.check_age_eligibility(year)
        mileage_eligible, mileage_reason = self.check_mileage_eligibility(mileage)
        make_model_eligible, make_model_reason = self.check_make_model_eligibility(make, model)
        title_eligible, title_reason = self.check_title_status_eligibility(title_status)
        
        # Overall eligibility - ALL checks must pass
        overall_eligible = age_eligible and mileage_eligible and make_model_eligible and title_eligible
        
        # Prepare reasons
        reasons = []
        if not age_eligible:
            reasons.append(age_reason)
        if not mileage_eligible:
            reasons.append(mileage_reason)
        if not make_model_eligible:
            reasons.append(make_model_reason)
        if not title_eligible:
            reasons.append(title_reason)
        
        if overall_eligible:
            reasons = ["✅ Vehicle meets all Turo eligibility requirements!"]
        
        return {
            'eligible': overall_eligible,
            'reasons': reasons,
            'details': {
                'age_check': {'passed': age_eligible, 'reason': age_reason},
                'mileage_check': {'passed': mileage_eligible, 'reason': mileage_reason},
                'make_model_check': {'passed': make_model_eligible, 'reason': make_model_reason},
                'title_check': {'passed': title_eligible, 'reason': title_reason}
            }
        }