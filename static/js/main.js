let currentMode = "auto";
let isHumidifierOn = false;
let mushChartInstance = null;

// Mulai sinkronisasi berkala
setInterval(syncDashboard, 1000);
initChart();

function initChart() {
    const ctx = document.getElementById('mushChart').getContext('2d');
    mushChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'Suhu (°C)', borderColor: '#74c365', data: [], tension: 0.2 }, // Hijau Logo MATCH!
                { label: 'Humid Udara (%)', borderColor: '#eab308', data: [], tension: 0.2 },
                { label: 'Soil (%)', borderColor: '#0ea5e9', data: [], tension: 0.2 }
            ]
        },
        options: { responsive: true, scales: { y: { min: 0, max: 100 } } }
    });
}

function syncDashboard() {
    fetch('/get_web_data')
        .then(res => res.json())
        .then(data => {
            // 1. Sinkronisasi Status Server Internal Laptop
            const serverStatus = document.getElementById('server-status');
            if (serverStatus) {
                serverStatus.innerText = "Server: Online";
                serverStatus.className = "status-badge status-online";
            }
            
            // 2. Sinkronisasi Status Koneksi Hardware ESP32
            const espStatus = document.getElementById('esp-status');
            if (espStatus) {
                if (data.live.wifi_status === "Connected") {
                    espStatus.innerHTML = '<span class="dot"></span> ESP32: On';
                    espStatus.className = "status-badge status-online"; // Menjadi hijau sesuai CSS kamu
                } else {
                    espStatus.innerHTML = '<span class="dot"></span> ESP32: Off';
                    espStatus.className = "status-badge status-offline"; // Menjadi merah kembali
                }
            }

            // 3. Live Update Data Sensor (Di-parse dengan aman)
            document.getElementById('val-temp').innerText = parseFloat(data.live.temperature).toFixed(1) + "°C";
            document.getElementById('val-hum').innerText = parseFloat(data.live.humidity).toFixed(0) + "%";
            document.getElementById('val-soil').innerText = parseInt(data.live.soil) + "%";
            document.getElementById('val-lamp1').innerText = parseInt(data.live.lamp1) + "%";
            document.getElementById('val-lamp2').innerText = parseInt(data.live.lamp2) + "%";
            document.getElementById('val-update').innerText = data.live.last_update;
            document.getElementById('fill-soil').style.width = parseInt(data.live.soil) + "%";

            // Alarm Media Kering
            if(parseInt(data.live.soil) < parseInt(data.setpoints.soilMin)) {
                document.getElementById('soil-alert').classList.remove('text-hidden');
            } else {
                document.getElementById('soil-alert').classList.add('text-hidden');
            }

            // Humidifier Box State
            const humBox = document.getElementById('status-humidifier');
            if (humBox) {
                humBox.innerText = data.live.humidifier ? "ON" : "OFF";
                humBox.className = data.live.humidifier ? "state-box box-on" : "state-box box-off";
            }

            // Sinkron Label Setpoint Teks
            document.getElementById('lbl-tmin').innerText = data.setpoints.suhuMin;
            document.getElementById('lbl-tmax').innerText = data.setpoints.suhuMax;
            document.getElementById('lbl-hmin').innerText = data.setpoints.humidMin;
            document.getElementById('lbl-hmax').innerText = data.setpoints.humidMax;

            // Masukkan data form konfigurasi jika user tidak sedang mengetik
            if (document.activeElement.tagName !== 'INPUT') {
                document.getElementById('inp-tmin').value = data.setpoints.suhuMin;
                document.getElementById('inp-tideal').value = data.setpoints.suhuIdeal;
                document.getElementById('inp-tmax').value = data.setpoints.suhuMax;
                document.getElementById('inp-hmin').value = data.setpoints.humidMin;
                document.getElementById('inp-hmax').value = data.setpoints.humidMax;
                document.getElementById('inp-smin').value = data.setpoints.soilMin;
            }

            // Atur visual mode tombol kontrol
            currentMode = data.setpoints.mode;
            if(currentMode === "auto") {
                document.getElementById('btn-mode-auto').classList.add('active');
                document.getElementById('btn-mode-manual').classList.remove('active');
                document.getElementById('manual-control-panel').classList.add('panel-disabled');
            } else {
                document.getElementById('btn-mode-auto').classList.remove('active');
                document.getElementById('btn-mode-manual').classList.add('active');
                document.getElementById('manual-control-panel').classList.remove('panel-disabled');
            }

            // Update Realtime Grafik Linier Chart.js
            if (mushChartInstance) {
                mushChartInstance.data.labels = data.history.labels;
                mushChartInstance.data.datasets[0].data = data.history.temp_logs;
                mushChartInstance.data.datasets[1].data = data.history.hum_logs;
                mushChartInstance.data.datasets[2].data = data.history.soil_logs;
                mushChartInstance.update();
            }
        })
        .catch((err) => {
            console.log("Dashboard Sync Error: ", err);
            const serverStatus = document.getElementById('server-status');
            if (serverStatus) {
                serverStatus.innerText = "Server: Offline";
                serverStatus.className = "status-badge status-offline";
            }
        });
}

function setControlMode(mode) {
    const payload = {
        action: "update_control", mode: mode,
        humidifier: isHumidifierOn ? 1 : 0,
        lamp1: document.getElementById('range-lamp1').value,
        lamp2: document.getElementById('range-lamp2').value
    };
    sendControlPayload(payload);
}

function toggleManualHumidifier() {
    isHumidifierOn = !isHumidifierOn;
    const btn = document.getElementById('btn-manual-hum');
    btn.innerText = isHumidifierOn ? "TURN OFF" : "TURN ON";
    btn.className = isHumidifierOn ? "btn-action active-run" : "btn-action";
    updateManualHardware();
}

function updateManualHardware() {
    const l1 = document.getElementById('range-lamp1').value;
    const l2 = document.getElementById('range-lamp2').value;
    document.getElementById('lbl-range-l1').innerText = l1;
    document.getElementById('lbl-range-l2').innerText = l2;

    if(currentMode === "manual") {
        const payload = {
            action: "update_control", mode: "manual",
            humidifier: isHumidifierOn ? 1 : 0, lamp1: l1, lamp2: l2
        };
        sendControlPayload(payload);
    }
}

function saveSetpoints() {
    const payload = {
        action: "update_setpoints",
        suhuMin: parseFloat(document.getElementById('inp-tmin').value),
        suhuIdeal: parseFloat(document.getElementById('inp-tideal').value),
        suhuMax: parseFloat(document.getElementById('inp-tmax').value),
        humidMin: parseFloat(document.getElementById('inp-hmin').value),
        humidMax: parseFloat(document.getElementById('inp-hmax').value),
        soilMin: parseInt(document.getElementById('inp-smin').value)
    };
    
    fetch('/save_settings', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    }).then(() => alert("Setpoint SMARTMUSH Berhasil Diperbarui!"));
}

function sendControlPayload(payload) {
    fetch('/save_settings', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    });
}