# 🌡️ Multi-Sensor IoT Dashboard

Dashboard monitoring dan kontrol sistem irigasi otomatis untuk 2 Wokwi dengan sensor berbeda menggunakan Streamlit dan MQTT.

## 📋 Fitur

### Wokwi 1 - Monitoring Suhu
- 🌤️ **Sensor Suhu Udara (DHT22)** - Monitoring suhu lingkungan
- 🌱 **Sensor Suhu Tanah (DHT22)** - Monitoring suhu tanah

### Wokwi 2 - Monitoring & Kontrol Air
- 💦 **Sensor Level Air (HC-SR04)** - Monitoring kapasitas air dalam tandon
- 📏 **Jarak Air** - Pengukuran jarak dari sensor ke permukaan air
- 🎛️ **Kontrol Pump/Servo** - Mengontrol pompa air (ON/OFF)

### Dashboard Features
- 📊 Real-time monitoring dengan metrics cards
- 📈 Grafik real-time untuk semua sensor (4 grafik terpisah)
- 🔄 Auto-refresh optional dengan interval yang dapat disesuaikan
- 💡 Status koneksi MQTT dengan timestamp
- 🎨 UI modern dengan Streamlit
- 🔍 Debug logging di terminal untuk setiap data yang masuk

## 🛠️ Instalasi

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Jalankan Dashboard

```bash
streamlit run dashboard.py
```

Dashboard akan terbuka di browser pada `http://localhost:8501`

## 📡 Konfigurasi MQTT

Dashboard menggunakan MQTT broker public:
- **Broker:** `broker.hivemq.com`
- **Port:** 1883

### MQTT Topics

#### Subscribe (Dashboard Menerima):
- `irrigation/sensor/environment` - Data suhu udara dari Wokwi 1
- `irrigation/sensor/soil` - Data suhu tanah dari Wokwi 1  
- `irrigation/sensor/water_level` - Data level air & jarak dari Wokwi 2
- `irrigation/actuator/status` - Status pump/servo dari Wokwi 2

#### Publish (Dashboard Mengirim):
- `irrigation/actuator/control` - Perintah kontrol pump/servo ke Wokwi 2

## 🔧 Format Pesan JSON

### Data Sensor

**1. Suhu Udara (`irrigation/sensor/environment`):**
```json
{
  "temperature": 28.5
}
```

**2. Suhu Tanah (`irrigation/sensor/soil`):**
```json
{
  "temperature": 25.3
}
```

**3. Water Level (`irrigation/sensor/water_level`):**
```json
{
  "capacity_percent": 94,
  "distance": 7.0
}
```
- `capacity_percent`: Persentase kapasitas air (0-100%)
- `distance`: Jarak dari sensor ke permukaan air dalam cm

**4. Status Servo (`irrigation/actuator/status`):**
```json
{
  "status": "OFF"
}
```

### Kontrol Pump/Servo

**Mengirim Perintah dari Dashboard:**
```json
{
  "pump": "ON",
  "servo": 90
}
```
atau
```json
{
  "pump": "OFF",
  "servo": 0
}
```
- `pump`: "ON" untuk hidupkan, "OFF" untuk matikan
- `servo`: Sudut servo (90° untuk ON, 0° untuk OFF)

## 🎮 Cara Menggunakan Dashboard

1. **Jalankan Wokwi Simulator:**
   - Buka kedua project Wokwi (Wokwi 1 dan Wokwi 2)
   - Pastikan code sudah sesuai dengan format JSON di atas
   - Start simulation di kedua Wokwi

2. **Jalankan Dashboard:**
   ```bash
   streamlit run dashboard.py
   ```

3. **Hubungkan ke MQTT:**
   - Klik tombol "🔄 Hubungkan" di sidebar
   - Tunggu hingga status berubah menjadi 🟢 Terhubung
   - Lihat timestamp koneksi dan data terakhir

4. **Monitor Data:**
   - **Tab "📊 Dashboard"**: Lihat metrics real-time semua sensor
   - **Tab "📈 Grafik Real-time"**: Visualisasi 4 grafik (Suhu Udara, Suhu Tanah, Level Air, Jarak Air)
   - **Tab "ℹ️ Info"**: Dokumentasi lengkap dan troubleshooting

5. **Kontrol Pump:**
   - Pastikan status 🟢 Terhubung
   - Klik "▶️ PUMP ON" untuk menghidupkan pompa
   - Klik "⏹️ PUMP OFF" untuk mematikan pompa
   - Status servo akan ter-update di dashboard

6. **Refresh Data:**
   - **Manual**: Klik tombol "🔄 Refresh" di sidebar
   - **Auto** (Optional): Centang "Aktifkan Auto Refresh" dan atur interval (5-10 detik recommended)
   - ⚠️ Auto-refresh dapat menyebabkan flicker, gunakan seperlunya

## 📊 Fitur Dashboard Detail

### Tab Dashboard
- Real-time metrics untuk:
  - Suhu Udara (°C) dengan delta perubahan
  - Suhu Tanah (°C) dengan delta perubahan
  - Level Air (%) dengan delta perubahan
  - Jarak Air (cm) dengan delta perubahan
  - Status Pump/Servo dengan indikator visual
- Progress bar untuk visualisasi kapasitas air
- Timestamp update terakhir

### Tab Grafik Real-time
- 4 Grafik terpisah:
  1. **Suhu Udara** - Line chart dengan markers
  2. **Suhu Tanah** - Line chart dengan markers
  3. **Level Air (%)** - Area chart (fill)
  4. **Jarak Air (cm)** - Line chart dengan markers
- Semua grafik dengan timestamp pada sumbu X
- Interactive hover untuk detail data
- Menyimpan hingga 50 data point terakhir

### Tab Info
- Dokumentasi lengkap format JSON
- Daftar MQTT topics
- Panduan penggunaan step-by-step
- Tips & troubleshooting
- Info sensor dan broker

## 🔍 Troubleshooting

### Dashboard tidak dapat terhubung ke MQTT
- ✅ Pastikan koneksi internet aktif
- ✅ Periksa firewall tidak memblokir port 1883
- ✅ Restart dashboard dengan `Ctrl+C` lalu jalankan ulang

### Data sensor tidak muncul
- ✅ Pastikan Wokwi simulation sedang running
- ✅ Periksa MQTT topics **sama persis** (case-sensitive)
- ✅ Lihat terminal dashboard untuk debug log:
  ```
  📨 [irrigation/sensor/water_level] {'capacity_percent': 94, 'distance': 7.0}
    💧 Water: 94% (distance: 7.0cm)
  ```
- ✅ Jika log muncul tapi UI tidak update, klik tombol "🔄 Refresh"

### Kontrol pump tidak berfungsi
- ✅ Pastikan status 🟢 Terhubung (bukan 🔴 Terputus)
- ✅ Periksa Wokwi 2 sudah subscribe ke `irrigation/actuator/control`
- ✅ Lihat terminal Wokwi 2 untuk melihat pesan yang diterima
- ✅ Pastikan format JSON sesuai: `{"pump": "ON", "servo": 90}`

### Grafik kosong / tidak ter-update
- ✅ Tunggu beberapa detik agar data masuk
- ✅ Pastikan Wokwi mengirim data dengan interval teratur (2-5 detik)
- ✅ Klik "🔄 Refresh" untuk force update
- ✅ Periksa data masuk di terminal dashboard

### Warning "missing ScriptRunContext"
- ⚠️ Warning ini **NORMAL** dan dapat diabaikan
- ℹ️ Disebabkan oleh MQTT callback di thread terpisah
- ✅ Data tetap masuk dan berfungsi dengan baik

### Tampilan dashboard "double" / flicker
- ✅ **Matikan** auto-refresh (uncheck checkbox)
- ✅ Gunakan refresh manual dengan tombol "🔄 Refresh"
- ✅ Jika tetap ingin auto-refresh, set interval ≥ 5 detik

## 📦 Dependencies

```txt
streamlit>=1.28.0     # Framework web untuk dashboard
paho-mqtt>=1.6.1      # MQTT client library
pandas>=2.1.1         # Data manipulation
plotly>=5.17.0        # Interactive charts
```

## 👨‍💻 Development

### Struktur File
```
multi-sensor-dashboard/
├── dashboard.py              # Main dashboard application
├── requirements.txt          # Python dependencies
├── README.md                 # Documentation (file ini)
├── wokwi1_diagram.json       # Wokwi 1 hardware diagram
├── wokwi1_temp_sensors.ino   # Wokwi 1 Arduino code
├── wokwi2_diagram.json       # Wokwi 2 hardware diagram
└── wokwi2_water_servo.ino    # Wokwi 2 Arduino code
```

### Modifikasi MQTT Topics
Edit variabel di bagian atas `dashboard.py`:
```python
# Topics untuk Wokwi 1 (Sensor Suhu)
TOPIC_TEMP_AIR = "irrigation/sensor/environment"
TOPIC_TEMP_SOIL = "irrigation/sensor/soil"

# Topics untuk Wokwi 2 (Sensor Air & Servo)
TOPIC_WATER_LEVEL = "irrigation/sensor/water_level"
TOPIC_SERVO_CONTROL = "irrigation/actuator/control"
TOPIC_SERVO_STATUS = "irrigation/actuator/status"
```

### Mengganti MQTT Broker
Edit variabel:
```python
MQTT_BROKER = "broker.hivemq.com"  # Ganti dengan broker lain
MQTT_PORT = 1883
```

### Mengubah Jumlah Data Point
Edit konstanta:
```python
MAX_DATA_POINTS = 50  # Ganti dengan jumlah yang diinginkan
```

## 🚀 Fitur Tambahan

- **Thread-safe data handling**: Data dari MQTT callback disimpan dengan aman
- **Global reference untuk sensor data**: Menghindari warning ScriptRunContext
- **Responsive layout**: Dashboard dapat diakses dari berbagai ukuran layar
- **Debug logging**: Setiap data yang masuk ter-log di terminal
- **Connection status tracking**: Menampilkan waktu koneksi dan data terakhir
- **Manual & auto refresh**: Fleksibilitas dalam update data

## 📄 License

Free to use for educational purposes.

## 🙏 Credits

Dashboard monitoring sistem irigasi otomatis untuk project IoT menggunakan:
- **Wokwi Simulator** - ESP32 virtual hardware simulation
- **Streamlit** - Python web framework
- **HiveMQ** - Public MQTT broker
- **Plotly** - Interactive charting library
