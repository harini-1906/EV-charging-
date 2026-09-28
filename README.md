# IoT EV Charging Station Monitoring System (Hardware-Free)

A complete, responsive Internet of Things (IoT) Electric Vehicle (EV) Charging Station Monitoring System that runs entirely in software **WITHOUT any physical hardware**. It simulates active EV chargers using a Python background daemon thread, generating live telemetry and committing completed sessions to a SQLite database.

Developed with a premium, responsive **EV green theme** featuring glassmorphism elements, dark-mode gradients, and dynamic analytics charts.

---

## Features

1. **User Authentication & Role Management**:
   - Role-based views: **Admin** and **User**.
   - Registration and Login screens with secure password hashing (`PBKDF2-SHA256`).
   - Preconfigured demo credentials for instant testing.
2. **Real-Time Telemetry Dashboard**:
   - Dynamic polling (every 3 seconds) using JavaScript Fetch API without page reloads.
   - Core metrics: Total Stations, Available Chargers, Charging Chargers, and Completed Sessions.
   - 5 simulated charging bays, expandable dynamically by Admins.
   - Simulated variables: **Battery SOC**, **Voltage (V)**, **Current (A)**, **Power Draw (kW)**, and **Temperature (°C)**.
3. **Interactive Controls**:
   - **Start Charging**: Selects a bay, simulates a plugged-in vehicle with a random state of charge (10% - 50%), and triggers the simulation.
   - **Stop Charging**: Halts charging early, calculates exact energy consumed (kWh), generates a printable invoice receipt, and sets the bay back to *Available*.
   - **Automatic Completion**: Stations auto-terminate when the battery reaches 100%, commit the session log, and calculate billing.
4. **Billing & Invoicing**:
   - Simulates energy draw: `1% SOC ≈ 0.6 kWh`.
   - Dynamic pricing: `$0.25 / kWh`.
   - Generates a sleek receipt bill on session stop or completion.
5. **Session History & Analytics**:
   - SQLite-backed log repository showing all previous sessions.
   - Renders 3 gorgeous dark-mode Chart.js canvas elements:
     - **Daily Energy Usage (kWh)** (Line chart of past 7 days)
     - **Revenue Generated ($)** (Bar chart of past 7 days)
     - **Energy Distribution by Station (kWh)** (Horizontal bar chart)
6. **Admin Panel**:
   - **Add Station**: Create new operational bays.
   - **Delete Station**: Safely remove bays (active sessions on them are stopped and logged first).
   - **Enable/Disable Station**: Toggle bays online/offline. Offline bays clear telemetry metrics and display a disabled state.

---

## Folder Structure

The project has been organized with standard Web-App best practices:

```text
ev-charging-station/
├── app.py                  # Python Flask backend server & background IoT simulator
├── schema.sql              # SQLite database structure definitions
├── requirements.txt        # Python external library dependencies
├── README.md               # Setup, credentials, and architecture guide
├── static/
│   ├── css/
│   │   └── style.css       # Core stylesheets (Dark EV neon theme & responsive grids)
│   └── js/
│       ├── dashboard.js    # Fetch API live update loop, modal toggles, & plug-in actions
│       └── charts.js       # Chart.js initialization & history table populate functions
└── templates/
    ├── base.html           # Shared layout layout with responsive menu and custom toasts
    ├── login.html          # Authentication gate
    ├── register.html       # Sign-up interface
    ├── dashboard.html      # Real-time telemetry monitoring screen
    ├── history.html        # Historical session reports and analytics charts
    └── admin.html          # Node manager (add, delete, enable/disable)
```

---

## Installation & Running on Localhost

Follow these simple steps to set up and run the system locally:

### 1. Prerequisites
Ensure you have **Python 3.8+** installed on your system. You can verify this by running:
```bash
python --version
```

### 2. Setup Project Files
Place all files inside a single workspace folder (e.g., `D:\ev charging station\`).

### 3. Install Dependencies
Open your VS Code terminal (or standard terminal) in the workspace directory and install the packages listed in `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 4. Run the Application
Start the Flask local web server:
```bash
python app.py
```

### 5. Access the Web App
Open your browser and navigate to:
```url
http://127.0.0.1:5000
```
On the first startup, `app.py` will automatically create `database.db`, execute the schema from `schema.sql`, seed 5 initial charging stations, and generate 7 days of completed charging records for visualization in the graphs.

---

## Demo Accounts

You can log in immediately using these preconfigured accounts:

| Role | Username | Password | Purpose |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Can access Admin Panel, toggle/add/delete bays, and view overall analytics charts. |
| **Regular User** | `user` | `user123` | Can start/stop charging, view live stations, and check their own session history. |

---

## IoT Simulation Logic

The system utilizes a daemon thread (`threading.Thread`) that loops continuously every **3 seconds** in the background:
- **Available Stations**: Telemetry sensors report `0.0V`, `0.0A`, `0.00kW`, and ambient temperature (`22.0°C`).
- **Offline Stations**: Telemetry sensors report `0.0V`, `0.0A`, `0.00kW`, and null temperature (`0.0°C`).
- **Charging Stations**:
  - **Grid Voltage**: Fluctuates realistically between `228.0V` and `235.0V` (typical single-phase grid drop).
  - **Current Draw**: Varies between `16.0A` and `32.0A` (representing alternating levels of vehicle battery demand).
  - **Power Consumed**: Dynamically computed as `(Voltage * Current) / 1000` (in kW).
  - **Battery SOC**: Increments by `2%` to `6%` per loop.
  - **State of Charge (SOC) Progress**: Normalizes relative progress from the initial connection charge up to `100%`.
  - **Thermal Rise**: Simulates ambient thermal energy dissipation. Temperature rises until it reaches the thermal equilibrium range (`42.0°C - 46.5°C`).
  - **Completion**: At `100%` SOC, the thread automatically terminates the session, commits energy consumption to SQLite, issues a bill at `$0.25 / kWh`, and returns the station to the `Available` state.
