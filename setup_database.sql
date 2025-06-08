-- Turo Vehicle Marketplace Database Schema
-- Run this in your Supabase SQL Editor

-- Users table
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  stripe_customer_id TEXT,
  is_paid BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Listings table  
CREATE TABLE IF NOT EXISTS listings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  vin TEXT,
  year INTEGER,
  make TEXT,
  model TEXT,
  mileage INTEGER,
  location TEXT NOT NULL,
  description TEXT,
  availability TEXT DEFAULT 'available_now',
  estimated_earnings INTEGER DEFAULT 0,
  images TEXT[] DEFAULT '{}',
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Contact requests table
CREATE TABLE IF NOT EXISTS contact_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  buyer_id UUID REFERENCES users(id) ON DELETE CASCADE,
  seller_id UUID REFERENCES users(id) ON DELETE CASCADE,
  listing_id UUID REFERENCES listings(id) ON DELETE CASCADE,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined')),
  message TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- VIN checks table (optional - for analytics)
CREATE TABLE IF NOT EXISTS vin_checks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vin TEXT NOT NULL,
  mileage INTEGER,
  make TEXT,
  model TEXT,
  year INTEGER,
  eligible BOOLEAN,
  reason TEXT,
  checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Earnings lookup table (for vehicle value estimates)
CREATE TABLE IF NOT EXISTS earnings_lookup (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  make TEXT NOT NULL,
  model TEXT,
  year_range TEXT,
  estimated_monthly_earning INTEGER NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_listings_user_id ON listings(user_id);
CREATE INDEX IF NOT EXISTS idx_listings_active ON listings(is_active);
CREATE INDEX IF NOT EXISTS idx_contact_requests_buyer ON contact_requests(buyer_id);
CREATE INDEX IF NOT EXISTS idx_contact_requests_seller ON contact_requests(seller_id);
CREATE INDEX IF NOT EXISTS idx_contact_requests_listing ON contact_requests(listing_id);
CREATE INDEX IF NOT EXISTS idx_vin_checks_date ON vin_checks(checked_at);

-- Insert sample earnings data
INSERT INTO earnings_lookup (make, model, year_range, estimated_monthly_earning) VALUES
('HONDA', 'ACCORD', '2018-2025', 800),
('HONDA', 'CIVIC', '2018-2025', 700),
('TOYOTA', 'CAMRY', '2018-2025', 750),
('TOYOTA', 'COROLLA', '2018-2025', 650),
('BMW', NULL, '2018-2025', 1100),
('MERCEDES', NULL, '2018-2025', 1200),
('TESLA', 'MODEL 3', '2018-2025', 1400),
('TESLA', 'MODEL S', '2018-2025', 1800),
('FORD', 'F-150', '2018-2025', 900),
('CHEVROLET', 'MALIBU', '2018-2025', 700)
ON CONFLICT DO NOTHING;

-- Enable Row Level Security (RLS) for data protection
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE contact_requests ENABLE ROW LEVEL SECURITY;

-- Create policies for secure access
CREATE POLICY "Users can view their own data" ON users
    FOR ALL USING (auth.uid()::text = id::text);

CREATE POLICY "Users can view active listings" ON listings
    FOR SELECT USING (is_active = true);

CREATE POLICY "Users can manage their own listings" ON listings
    FOR ALL USING (auth.uid()::text = user_id::text);

CREATE POLICY "Users can view their contact requests" ON contact_requests
    FOR SELECT USING (auth.uid()::text = buyer_id::text OR auth.uid()::text = seller_id::text);

CREATE POLICY "Users can create contact requests" ON contact_requests
    FOR INSERT WITH CHECK (auth.uid()::text = buyer_id::text);

CREATE POLICY "Sellers can update request status" ON contact_requests
    FOR UPDATE USING (auth.uid()::text = seller_id::text);