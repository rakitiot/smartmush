from flask import Flask, render_template, request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
DB_FILE = "smartmush_db.db"

# Inisialisasi Database Lokal python app.py di terminal atau di cmd
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Tabel Log Sensor
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature REAL,
            humidity REAL,
            soil INTEGER
        )
    ''')
    # Tabel Pengaturan (Setpoint & Override)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            suhuMin REAL, suhuIdeal REAL, suhuMax REAL,
            humidMin REAL, humidMax REAL, soilMin INTEGER,
            mode_kontrol TEXT, status_humidifier INTEGER,
            power_lamp1 INTEGER, power_lamp2 INTEGER
        )
    ''')
    # Isi data default jika pengaturan masih kosong
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO settings (id, suhuMin, suhuIdeal, suhuMax, humidMin, humidMax, soilMin, mode_kontrol, status_humidifier, power_lamp1, power_lamp2)
            VALUES (1, 24.0, 27.0, 30.0, 80.0, 85.0, 40, 'auto', 0, 0, 0)
        ''')
    conn.commit()
    conn.close()

init_db()

# Variabel RAM untuk status real-time ESP32
live_status = {
    "temperature": 0.0, "humidity": 0.0, "soil": 0,
    "lamp1": 0, "lamp2": 0, "humidifier": False,
    "wifi_status": "Disconnected", "last_update": "-"
}

@app.route('/')
def index():
    return render_template('dashboard.html')

# Endpoint 1: ESP32 melakukan POST data sensor sekaligus GET instruksi/setpoint dari web
@app.route('/update', methods=['POST'])
@app.route('/update', methods=['POST'])
def update_from_esp():
    global live_status
    try:
        if not request.is_json:
            return jsonify({"status": "error", "message": "Must be JSON"}), 400
        
        content = request.get_json()
        
        # 1. Simpan data terbaru dengan parsing tipe data yang aman
        live_status["temperature"] = float(content.get("temperature", live_status["temperature"]))
        live_status["humidity"] = float(content.get("humidity", live_status["humidity"]))
        live_status["soil"] = int(content.get("soil", live_status["soil"]))
        live_status["lamp1"] = int(content.get("lamp1", live_status["lamp1"]))
        live_status["lamp2"] = int(content.get("lamp2", live_status["lamp2"]))
        
        # Konversi data humidifier agar seragam menjadi boolean Python murni
        h_val = content.get("humidifier")
        if isinstance(h_val, str):
            live_status["humidifier"] = True if h_val.lower() == "true" else False
        else:
            live_status["humidifier"] = bool(h_val)
            
        live_status["wifi_status"] = "Connected"
        live_status["last_update"] = datetime.now().strftime("%H:%M:%S")

        # 2. Log data sensor ke Database SQLite
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sensor_logs (timestamp, temperature, humidity, soil)
            VALUES (?, ?, ?, ?)
        ''', (live_status["last_update"], live_status["temperature"], live_status["humidity"], live_status["soil"]))
        
        cursor.execute("DELETE FROM sensor_logs WHERE id NOT IN (SELECT id FROM sensor_logs ORDER BY id DESC LIMIT 30)")
        
        # 3. Ambil data konfigurasi dari database
        cursor.execute("SELECT suhuMin, suhuIdeal, suhuMax, humidMin, humidMax, soilMin, mode_kontrol, status_humidifier, power_lamp1, power_lamp2 FROM settings WHERE id=1")
        row = cursor.fetchone()
        conn.commit()
        conn.close()

        # Susun respon balikan dalam bentuk int/bool murni agar mudah dibaca ESP32
        config_payload = {
            "suhuMin": float(row[0]), "suhuIdeal": float(row[1]), "suhuMax": float(row[2]),
            "humidMin": float(row[3]), "humidMax": float(row[4]), "soilMin": int(row[5]),
            "mode": str(row[6]),
            "manual_humidifier": True if row[7] == 1 else False,
            "manual_lamp1": int(row[8]),
            "manual_lamp2": int(row[9])
        }
        return jsonify(config_payload), 200

    except Exception as e:
        print(f"Error on HTTP Post: {str(e)}") # Memunculkan pesan error ke terminal console Python
        return jsonify({"status": "error", "message": str(e)}), 500

# Endpoint 2: Browser mengambil data real-time + riwayat log untuk grafik
@app.route('/get_web_data', methods=['GET'])
def get_web_data():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Ambil pengaturan saat ini
    cursor.execute("SELECT suhuMin, suhuIdeal, suhuMax, humidMin, humidMax, soilMin, mode_kontrol FROM settings WHERE id=1")
    setp = cursor.fetchone()
    
    # Ambil riwayat log sensor untuk grafik
    cursor.execute("SELECT timestamp, temperature, humidity, soil FROM sensor_logs ORDER BY id DESC LIMIT 10")
    logs = cursor.fetchall()[::-1] # balik urutan agar waktu berjalan ke kanan
    conn.close()

    history = {
        "labels": [l[0] for l in logs],
        "temp_logs": [l[1] for l in logs],
        "hum_logs": [l[2] for l in logs],
        "soil_logs": [l[3] for l in logs]
    }

    return jsonify({
        "live": live_status,
        "setpoints": {
            "suhuMin": setp[0], "suhuIdeal": setp[1], "suhuMax": setp[2],
            "humidMin": setp[3], "humidMax": setp[4], "soilMin": setp[5], "mode": setp[6]
        },
        "history": history
    })

# Endpoint 3: Browser mengirim perubahan setpoint atau kendali manual ke database
@app.route('/save_settings', methods=['POST'])
def save_settings():
    content = request.get_json()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if content.get("action") == "update_setpoints":
        cursor.execute('''
            UPDATE settings SET suhuMin=?, suhuIdeal=?, suhuMax=?, humidMin=?, humidMax=?, soilMin=? WHERE id=1
        ''', (content['suhuMin'], content['suhuIdeal'], content['suhuMax'], content['humidMin'], content['humidMax'], content['soilMin']))
    
    elif content.get("action") == "update_control":
        cursor.execute('''
            UPDATE settings SET mode_kontrol=?, status_humidifier=?, power_lamp1=?, power_lamp2=? WHERE id=1
        ''', (content['mode'], content['humidifier'], content['lamp1'], content['lamp2']))

    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)