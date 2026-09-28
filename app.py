# app.py
# Main application backend for the EV Charging Station Monitoring System.
# Handles Flask routes, user authentication, SQLite database operations, and live IoT simulation.

import os
import time
import random
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_ev_monitoring_key_123'
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db():
    """Returns a database connection for the current request context."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    """Closes the database connection at the end of the request."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Initializes the SQLite database with the schema and mock data if it doesn't exist."""
    db_exists = os.path.exists(DATABASE)
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Always try to create tables if they don't exist
    with app.open_resource('schema.sql', mode='r') as f:
        cursor.executescript(f.read())
    
    # Check if we need to insert mock data
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # Create a default admin user
        admin_password = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
            ('admin', admin_password, 'admin@evstation.com', 'admin')
        )
        # Create a default regular user
        user_password = generate_password_hash('user123')
        cursor.execute(
            "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
            ('user', user_password, 'user@evstation.com', 'user')
        )
        
    cursor.execute("SELECT COUNT(*) FROM stations")
    if cursor.fetchone()[0] == 0:
        # Create 5 initial EV Charging Stations
        for i in range(1, 6):
            cursor.execute(
                "INSERT INTO stations (name, status, battery_percentage, charging_progress, voltage, current, temperature, power_consumption, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f'EV-Charging Station {i}', 'Available', 0, 0, 0.0, 0.0, 22.0, 0.0, 1)
            )
            
        # Add some completed mock sessions for charts visualization
        # We'll generate mock completed sessions for the past 7 days
        cursor.execute("SELECT id FROM users WHERE username = 'user'")
        user_id = cursor.fetchone()[0]
        
        now = datetime.now()
        for d in range(7, 0, -1):
            date_str = (now - timedelta(days=d)).strftime('%Y-%m-%d')
            # Generate 2-4 sessions per day
            for s in range(random.randint(2, 4)):
                station_id = random.randint(1, 5)
                initial_bat = random.randint(10, 45)
                final_bat = 100
                energy = round((final_bat - initial_bat) * 0.6, 2) # approx 0.6 kWh per 1% battery
                cost = round(energy * 8.0, 2) # ₹8.00 per kWh
                
                start_time = f"{date_str} {random.randint(8, 20):02d}:{random.randint(0, 59):02d}:00"
                end_time = (datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S') + timedelta(minutes=random.randint(30, 90))).strftime('%Y-%m-%d %H:%M:%S')
                
                cursor.execute(
                    "INSERT INTO sessions (user_id, station_id, start_time, end_time, initial_battery, final_battery, energy_consumed, cost, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, station_id, start_time, end_time, initial_bat, final_bat, energy, cost, 'Completed')
                )
                
    conn.commit()
    conn.close()

# ----------------- IoT Simulator Background Thread -----------------
def start_simulator():
    """Starts the IoT background simulator thread to update active stations every 3 seconds."""
    def run_sim():
        while True:
            time.sleep(3)
            # Create a separate database connection for the background thread
            conn = sqlite3.connect(DATABASE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            try:
                # 1. Fetch all active sessions
                cursor.execute("SELECT * FROM sessions WHERE status = 'Active'")
                active_sessions = cursor.fetchall()
                
                # 2. Fetch all stations
                cursor.execute("SELECT * FROM stations")
                stations = cursor.fetchall()
                stations_dict = {s['id']: dict(s) for s in stations}
                
                for session_rec in active_sessions:
                    station_id = session_rec['station_id']
                    initial_battery = session_rec['initial_battery']
                    
                    if station_id not in stations_dict:
                        continue
                    
                    station = stations_dict[station_id]
                    
                    # If station is disabled or offline, force stop charging
                    if not station['enabled'] or station['status'] != 'Charging':
                        continue
                    
                    current_battery = station['battery_percentage']
                    
                    # Simulate charging progress: increment battery by 2% to 6%
                    increment = random.randint(2, 6)
                    new_battery = min(current_battery + increment, 100)
                    
                    # Calculate relative charging progress (0% to 100%)
                    if initial_battery >= 100:
                        progress = 100
                    else:
                        progress = int((new_battery - initial_battery) / (100.0 - initial_battery) * 100)
                    progress = min(progress, 100)
                    
                    # Simulate electrical and thermal properties
                    voltage = round(random.uniform(228.0, 235.0), 1)  # ~230V
                    current = round(random.uniform(16.0, 32.0), 1)    # 16A to 32A charging
                    power = round((voltage * current) / 1000.0, 2)     # Power in kW
                    
                    prev_temp = station['temperature'] or 22.0
                    # Temp rises when charging and stabilizes between 40°C and 48°C
                    if prev_temp < 42.0:
                        temp = round(prev_temp + random.uniform(0.8, 1.8), 1)
                    else:
                        temp = round(random.uniform(42.0, 46.5), 1)
                    
                    # If battery reached 100%, finalize the charging session
                    if new_battery >= 100:
                        final_battery = 100
                        # Calculate energy consumed based on charging delta
                        energy = round((final_battery - initial_battery) * 0.6, 2)
                        cost = round(energy * 8.0, 2) # ₹8.00 per kWh
                        
                        # Complete session in database
                        cursor.execute(
                            "UPDATE sessions SET end_time = ?, final_battery = ?, energy_consumed = ?, cost = ?, status = ? WHERE id = ?",
                            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), final_battery, energy, cost, 'Completed', session_rec['id'])
                        )
                        
                        # Revert station state back to Available
                        cursor.execute(
                            "UPDATE stations SET status = 'Available', battery_percentage = 0, charging_progress = 0, voltage = 0.0, current = 0.0, power_consumption = 0.0, temperature = 22.0 WHERE id = ?",
                            (station_id,)
                        )
                    else:
                        # Update station live data
                        cursor.execute(
                            "UPDATE stations SET battery_percentage = ?, charging_progress = ?, voltage = ?, current = ?, temperature = ?, power_consumption = ? WHERE id = ?",
                            (new_battery, progress, voltage, current, temp, power, station_id)
                        )
                
                # Check for idle or disabled stations to ensure values are clean
                for s_id, station in stations_dict.items():
                    if not station['enabled']:
                        # Station is disabled - force status Offline and clear live metrics
                        cursor.execute(
                            "UPDATE stations SET status = 'Offline', battery_percentage = 0, charging_progress = 0, voltage = 0.0, current = 0.0, power_consumption = 0.0, temperature = 0.0 WHERE id = ?",
                            (s_id,)
                        )
                    elif station['status'] == 'Available' and (station['voltage'] > 0 or station['current'] > 0):
                        # Station is available but has residual metrics - reset
                        cursor.execute(
                            "UPDATE stations SET battery_percentage = 0, charging_progress = 0, voltage = 0.0, current = 0.0, power_consumption = 0.0, temperature = 22.0 WHERE id = ?",
                            (s_id,)
                        )
                        
                conn.commit()
            except Exception as e:
                print(f"IoT Simulator Background Thread Error: {e}")
                conn.rollback()
            finally:
                conn.close()
                
    sim_thread = threading.Thread(target=run_sim, daemon=True)
    sim_thread.start()

# ----------------- Decorators -----------------
def login_required(f):
    """Decorator to protect routes requiring user login."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to protect routes requiring administrator privileges."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ----------------- Page Routes -----------------
@app.route('/')
def index():
    """Home redirect route."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handles User and Admin login authentication."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    error = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            error = "Invalid username or password."
            
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handles new User registration."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    error = None
    success = None
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        email = request.form['email'].strip()
        
        if not username or not password or not email:
            error = "All fields are required."
        else:
            db = get_db()
            cursor = db.cursor()
            try:
                hashed_pass = generate_password_hash(password)
                cursor.execute(
                    "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, 'user')",
                    (username, hashed_pass, email)
                )
                db.commit()
                
                # Fetch new user to obtain their auto-incremented ID
                cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                user = cursor.fetchone()
                
                # Log them in automatically
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                
                return redirect(url_for('dashboard'))
            except sqlite3.IntegrityError:
                error = "Username already exists. Please choose another."
                
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    """Logs out the active user and clears the session."""
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Renders the main dashboard page."""
    return render_template('dashboard.html')

@app.route('/history')
@login_required
def history():
    """Renders the charging session history page."""
    return render_template('history.html')

@app.route('/admin')
@admin_required
def admin():
    """Renders the administrator management panel."""
    return render_template('admin.html')

# ----------------- JSON API Endpoints -----------------

@app.route('/api/stations', methods=['GET'])
@login_required
def api_get_stations():
    """Returns a list of all charging stations and their current IoT metrics."""
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM stations")
    stations = [dict(row) for row in cursor.fetchall()]
    return jsonify(stations)

@app.route('/api/stations/<int:station_id>/start', methods=['POST'])
@login_required
def api_start_charging(station_id):
    """Starts a new EV charging session on an available station."""
    db = get_db()
    cursor = db.cursor()
    
    # Fetch station state
    cursor.execute("SELECT * FROM stations WHERE id = ?", (station_id,))
    station = cursor.fetchone()
    
    if not station:
        return jsonify({'success': False, 'message': 'Station not found.'}), 404
        
    if not station['enabled']:
        return jsonify({'success': False, 'message': 'Station is offline/disabled.'}), 400
        
    if station['status'] != 'Available':
        return jsonify({'success': False, 'message': 'Station is not available.'}), 400
        
    # Generate a random initial battery percentage (10% to 50%) for mock simulation
    initial_battery = random.randint(10, 50)
    
    # Update station state to Charging
    cursor.execute(
        "UPDATE stations SET status = 'Charging', battery_percentage = ?, charging_progress = 0, voltage = 230.0, current = 16.0, power_consumption = 3.68, temperature = 25.0 WHERE id = ?",
        (initial_battery, station_id)
    )
    
    # Create active session in database
    cursor.execute(
        "INSERT INTO sessions (user_id, station_id, initial_battery, status) VALUES (?, ?, ?, 'Active')",
        (session['user_id'], station_id, initial_battery)
    )
    
    db.commit()
    return jsonify({'success': True, 'message': 'Charging session started successfully.'})

@app.route('/api/stations/<int:station_id>/stop', methods=['POST'])
@login_required
def api_stop_charging(station_id):
    """Stops an active EV charging session early and generates the invoice bill."""
    db = get_db()
    cursor = db.cursor()
    
    # Fetch station state
    cursor.execute("SELECT * FROM stations WHERE id = ?", (station_id,))
    station = cursor.fetchone()
    
    if not station:
        return jsonify({'success': False, 'message': 'Station not found.'}), 404
        
    if station['status'] != 'Charging':
        return jsonify({'success': False, 'message': 'Station is not active.'}), 400
        
    # Get active session
    cursor.execute(
        "SELECT * FROM sessions WHERE station_id = ? AND status = 'Active'",
        (station_id,)
    )
    session_rec = cursor.fetchone()
    
    if not session_rec:
        return jsonify({'success': False, 'message': 'Active session not found.'}), 404
        
    # Stop charging metrics calculation
    final_battery = station['battery_percentage']
    initial_battery = session_rec['initial_battery']
    
    # 1% charge ~ 0.6 kWh
    energy = round(max((final_battery - initial_battery) * 0.6, 0.0), 2)
    cost = round(energy * 8.0, 2)  # ₹8.00 per kWh
    
    # Close session
    cursor.execute(
        "UPDATE sessions SET end_time = ?, final_battery = ?, energy_consumed = ?, cost = ?, status = 'Completed' WHERE id = ?",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), final_battery, energy, cost, session_rec['id'])
    )
    
    # Reset station status back to Available
    cursor.execute(
        "UPDATE stations SET status = 'Available', battery_percentage = 0, charging_progress = 0, voltage = 0.0, current = 0.0, power_consumption = 0.0, temperature = 22.0 WHERE id = ?",
        (station_id,)
    )
    
    db.commit()
    return jsonify({
        'success': True,
        'message': 'Charging stopped.',
        'bill': {
            'energy': energy,
            'cost': cost,
            'initial_battery': initial_battery,
            'final_battery': final_battery
        }
    })

@app.route('/api/sessions/history', methods=['GET'])
@login_required
def api_get_history():
    """Returns charging history records. Regular users see their own history, Admins see all."""
    db = get_db()
    cursor = db.cursor()
    
    if session.get('role') == 'admin':
        cursor.execute("""
            SELECT s.*, u.username, st.name as station_name 
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            JOIN stations st ON s.station_id = st.id
            ORDER BY s.start_time DESC
        """)
    else:
        cursor.execute("""
            SELECT s.*, u.username, st.name as station_name 
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            JOIN stations st ON s.station_id = st.id
            WHERE s.user_id = ?
            ORDER BY s.start_time DESC
        """, (session['user_id'],))
        
    history_list = [dict(row) for row in cursor.fetchall()]
    return jsonify(history_list)

@app.route('/api/stats', methods=['GET'])
@login_required
def api_get_stats():
    """Returns aggregated statistical data for rendering dashboard summary and charts."""
    db = get_db()
    cursor = db.cursor()
    
    # 1. Dashboard summary cards calculations
    cursor.execute("SELECT COUNT(*) FROM stations")
    total_stations = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM stations WHERE status = 'Available' AND enabled = 1")
    available_stations = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM stations WHERE status = 'Charging'")
    charging_stations = cursor.fetchone()[0]
    
    # Completed sessions
    if session.get('role') == 'admin':
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'Completed'")
    else:
        cursor.execute("SELECT COUNT(*) FROM sessions WHERE status = 'Completed' AND user_id = ?", (session['user_id'],))
    completed_sessions = cursor.fetchone()[0]
    
    # 2. Charts Data (Daily usage for the last 7 days)
    # We fetch energy, sessions, and revenue grouped by day.
    if session.get('role') == 'admin':
        cursor.execute("""
            SELECT date(start_time) as date, 
                   COUNT(id) as sessions_count, 
                   SUM(energy_consumed) as total_energy, 
                   SUM(cost) as total_revenue
            FROM sessions 
            WHERE status = 'Completed' 
              AND start_time >= date('now', '-7 days')
            GROUP BY date(start_time)
            ORDER BY date(start_time) ASC
        """)
    else:
        cursor.execute("""
            SELECT date(start_time) as date, 
                   COUNT(id) as sessions_count, 
                   SUM(energy_consumed) as total_energy, 
                   SUM(cost) as total_revenue
            FROM sessions 
            WHERE status = 'Completed' 
              AND user_id = ? 
              AND start_time >= date('now', '-7 days')
            GROUP BY date(start_time)
            ORDER BY date(start_time) ASC
        """, (session['user_id'],))
        
    db_chart_rows = cursor.fetchall()
    
    # Fill in potential missing days with 0 so the line charts always show complete 7 days
    now = datetime.now()
    dates_list = [(now - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(6, -1, -1)]
    
    chart_data = {d: {'sessions': 0, 'energy': 0.0, 'revenue': 0.0} for d in dates_list}
    for row in db_chart_rows:
        d = row['date']
        if d in chart_data:
            chart_data[d] = {
                'sessions': row['sessions_count'] or 0,
                'energy': round(row['total_energy'] or 0.0, 2),
                'revenue': round(row['total_revenue'] or 0.0, 2)
            }
            
    sorted_chart_keys = sorted(chart_data.keys())
    
    # 3. Bar Chart: Energy usage per station (admin sees all, user sees their own per station)
    if session.get('role') == 'admin':
        cursor.execute("""
            SELECT st.name, SUM(s.energy_consumed) as total_energy
            FROM sessions s
            JOIN stations st ON s.station_id = st.id
            WHERE s.status = 'Completed'
            GROUP BY s.station_id
        """)
    else:
        cursor.execute("""
            SELECT st.name, SUM(s.energy_consumed) as total_energy
            FROM sessions s
            JOIN stations st ON s.station_id = st.id
            WHERE s.status = 'Completed' AND s.user_id = ?
            GROUP BY s.station_id
        """, (session['user_id'],))
    station_chart_rows = cursor.fetchall()
    station_energy = {row['name']: round(row['total_energy'] or 0.0, 2) for row in station_chart_rows}
    
    # Combine stats dictionary
    stats = {
        'summary': {
            'total_stations': total_stations,
            'available_stations': available_stations,
            'charging_stations': charging_stations,
            'completed_sessions': completed_sessions
        },
        'timeline': {
            'labels': sorted_chart_keys,
            'sessions': [chart_data[k]['sessions'] for k in sorted_chart_keys],
            'energy': [chart_data[k]['energy'] for k in sorted_chart_keys],
            'revenue': [chart_data[k]['revenue'] for k in sorted_chart_keys]
        },
        'stations': {
            'labels': list(station_energy.keys()),
            'energy': list(station_energy.values())
        }
    }
    
    return jsonify(stats)

# ----------------- Admin Action Endpoints -----------------

@app.route('/api/admin/add_station', methods=['POST'])
@admin_required
def api_add_station():
    """Adds a new EV charging station to the system."""
    name = request.form.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Station name cannot be empty.'}), 400
        
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(
            "INSERT INTO stations (name, status, battery_percentage, charging_progress, voltage, current, temperature, power_consumption, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, 'Available', 0, 0, 0.0, 0.0, 22.0, 0.0, 1)
        )
        db.commit()
        return jsonify({'success': True, 'message': f'Station "{name}" added successfully.'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'A station with this name already exists.'}), 400

@app.route('/api/admin/delete_station/<int:station_id>', methods=['POST'])
@admin_required
def api_delete_station(station_id):
    """Deletes a charging station. Active sessions on it are stopped."""
    db = get_db()
    cursor = db.cursor()
    
    # Check if station exists
    cursor.execute("SELECT * FROM stations WHERE id = ?", (station_id,))
    station = cursor.fetchone()
    if not station:
        return jsonify({'success': False, 'message': 'Station not found.'}), 404
        
    # If the station is charging, stop the session first
    if station['status'] == 'Charging':
        cursor.execute("SELECT id, initial_battery FROM sessions WHERE station_id = ? AND status = 'Active'", (station_id,))
        session_rec = cursor.fetchone()
        if session_rec:
            final_battery = station['battery_percentage']
            energy = round(max((final_battery - session_rec['initial_battery']) * 0.6, 0.0), 2)
            cost = round(energy * 8.0, 2)
            cursor.execute(
                "UPDATE sessions SET end_time = ?, final_battery = ?, energy_consumed = ?, cost = ?, status = 'Completed' WHERE id = ?",
                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), final_battery, energy, cost, session_rec['id'])
            )
            
    # Delete station from DB
    cursor.execute("DELETE FROM stations WHERE id = ?", (station_id,))
    db.commit()
    return jsonify({'success': True, 'message': 'Station deleted successfully.'})

@app.route('/api/admin/toggle_station/<int:station_id>', methods=['POST'])
@admin_required
def api_toggle_station(station_id):
    """Toggles station availability (Enable/Disable)."""
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute("SELECT * FROM stations WHERE id = ?", (station_id,))
    station = cursor.fetchone()
    if not station:
        return jsonify({'success': False, 'message': 'Station not found.'}), 404
        
    new_enabled = 0 if station['enabled'] else 1
    new_status = 'Available' if new_enabled == 1 else 'Offline'
    
    # If disabling a charging station, stop session first
    if new_enabled == 0 and station['status'] == 'Charging':
        cursor.execute("SELECT id, initial_battery FROM sessions WHERE station_id = ? AND status = 'Active'", (station_id,))
        session_rec = cursor.fetchone()
        if session_rec:
            final_battery = station['battery_percentage']
            energy = round(max((final_battery - session_rec['initial_battery']) * 0.6, 0.0), 2)
            cost = round(energy * 8.0, 2)
            cursor.execute(
                "UPDATE sessions SET end_time = ?, final_battery = ?, energy_consumed = ?, cost = ?, status = 'Completed' WHERE id = ?",
                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), final_battery, energy, cost, session_rec['id'])
            )
            
    # Update station status
    cursor.execute(
        "UPDATE stations SET enabled = ?, status = ?, battery_percentage = 0, charging_progress = 0, voltage = 0.0, current = 0.0, power_consumption = 0.0, temperature = 0.0 WHERE id = ?",
        (new_enabled, new_status, station_id)
    )
    
    db.commit()
    state_label = "enabled" if new_enabled == 1 else "disabled"
    return jsonify({'success': True, 'message': f'Station has been {state_label}.', 'enabled': new_enabled})

# ----------------- Start Flask Server -----------------
if __name__ == '__main__':
    # Initialize the database and tables
    init_db()
    
    # Start the IoT background simulator thread
    # In Flask's debug mode, the reloader runs, which starts a child process.
    # To prevent launching two simulator threads, we check the environment.
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        start_simulator()
        
    print("EV Charging Station Monitoring backend starting...")
    app.run(host='127.0.0.1', port=5000, debug=True)
