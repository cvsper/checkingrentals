-- Temporarily disable RLS for demo app functionality
-- Run this in your Supabase SQL Editor

-- Disable RLS on all tables for demo
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
ALTER TABLE listings DISABLE ROW LEVEL SECURITY;  
ALTER TABLE contact_requests DISABLE ROW LEVEL SECURITY;
ALTER TABLE vin_checks DISABLE ROW LEVEL SECURITY;

-- Drop existing restrictive policies
DROP POLICY IF EXISTS "Users can view their own data" ON users;
DROP POLICY IF EXISTS "Users can view active listings" ON listings;
DROP POLICY IF EXISTS "Users can manage their own listings" ON listings;
DROP POLICY IF EXISTS "Users can view their contact requests" ON contact_requests;
DROP POLICY IF EXISTS "Users can create contact requests" ON contact_requests;
DROP POLICY IF EXISTS "Sellers can update request status" ON contact_requests;

-- Create permissive policies for demo app
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE listings ENABLE ROW LEVEL SECURITY;
ALTER TABLE contact_requests ENABLE ROW LEVEL SECURITY;

-- Allow public access to users table for demo
CREATE POLICY "Allow all operations on users" ON users FOR ALL TO public USING (true) WITH CHECK (true);

-- Allow public access to listings for demo  
CREATE POLICY "Allow all operations on listings" ON listings FOR ALL TO public USING (true) WITH CHECK (true);

-- Allow public access to contact requests for demo
CREATE POLICY "Allow all operations on contact_requests" ON contact_requests FOR ALL TO public USING (true) WITH CHECK (true);

-- VIN checks don't need RLS for demo
CREATE POLICY "Allow all operations on vin_checks" ON vin_checks FOR ALL TO public USING (true) WITH CHECK (true);