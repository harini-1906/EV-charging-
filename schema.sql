-- schema.sql
-- Database schema for the IoT-based EV Charging Station Monitoring System.
-- This file defines the tables for users, charging stations, and charging sessions.

-- 1. Users Table: Stores credentials, emails, and roles (user or admin)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' -- 'user' or 'admin'
);

-- 2. Stations Table: Stores charging station information and live IoT metrics
CREATE TABLE IF NOT EXISTS stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    status TEXT NOT NULL DEFAULT 'Available', -- 'Available', 'Charging', 'Offline'
    battery_percentage INTEGER DEFAULT 0,      -- Current battery level (0-100)
    charging_progress INTEGER DEFAULT 0,       -- Charging session progress (0-100)
    voltage REAL DEFAULT 0.0,                  -- Simulated live voltage (V)
    current REAL DEFAULT 0.0,                  -- Simulated live current (A)
    temperature REAL DEFAULT 20.0,             -- Simulated station temperature (°C)
    power_consumption REAL DEFAULT 0.0,        -- Live charging rate (kW)
    enabled INTEGER DEFAULT 1                  -- 1 = Enabled (Online), 0 = Disabled (Offline)
);

-- 3. Sessions Table: Stores completed and ongoing charging sessions for billing and reporting
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    station_id INTEGER NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    initial_battery INTEGER DEFAULT 0,
    final_battery INTEGER DEFAULT 0,
    energy_consumed REAL DEFAULT 0.0, -- Total energy in kWh
    cost REAL DEFAULT 0.0,            -- Cost calculated at standard rate ($/kWh)
    status TEXT DEFAULT 'Active',     -- 'Active' or 'Completed'
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(station_id) REFERENCES stations(id)
);
