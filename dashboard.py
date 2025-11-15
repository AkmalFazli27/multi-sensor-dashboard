import streamlit as st
import paho.mqtt.client as mqtt
import json
import time
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from collections import deque
import threading

# Konfigurasi MQTT Broker (Wokwi menggunakan broker public)
MQTT_BROKER = "broker.hivemq.com"  # Atau gunakan broker.emqx.io
MQTT_PORT = 1883

# Topics untuk Wokwi 1 (Sensor Suhu)
TOPIC_TEMP_AIR = "irrigation/sensor/environment"
TOPIC_TEMP_SOIL = "irrigation/sensor/soil"

# Topics untuk Wokwi 2 (Sensor Air & Servo)
TOPIC_WATER_LEVEL = "irrigation/sensor/water_level"
TOPIC_SERVO_CONTROL = "irrigation/actuator/control"
TOPIC_SERVO_STATUS = "irrigation/actuator/status"

# Inisialisasi data storage dengan deque untuk performa lebih baik
MAX_DATA_POINTS = 50


class SensorData:
    def __init__(self):
        self.temp_air = deque(maxlen=MAX_DATA_POINTS)
        self.temp_soil = deque(maxlen=MAX_DATA_POINTS)
        self.water_level = deque(maxlen=MAX_DATA_POINTS)
        self.water_distance = deque(maxlen=MAX_DATA_POINTS)  # Distance in cm
        self.timestamps = deque(maxlen=MAX_DATA_POINTS)
        self.servo_status = "OFF"
        self.last_update = None
        self.mqtt_connected = False
        self.connection_time = None

    def add_temp_air(self, value):
        self.temp_air.append(value)
        self._update_timestamp()

    def add_temp_soil(self, value):
        self.temp_soil.append(value)
        self._update_timestamp()

    def add_water_level(self, capacity, distance=None):
        self.water_level.append(capacity)
        if distance is not None:
            self.water_distance.append(distance)
        self._update_timestamp()

    def _update_timestamp(self):
        if len(self.timestamps) < MAX_DATA_POINTS or (
            len(self.timestamps) > 0
            and (datetime.now() - datetime.fromisoformat(self.timestamps[-1])).seconds
            >= 1
        ):
            self.timestamps.append(datetime.now().isoformat())
        self.last_update = datetime.now()

    def set_mqtt_connected(self, status):
        self.mqtt_connected = status
        if status:
            self.connection_time = datetime.now()
        else:
            self.connection_time = None


# Inisialisasi session state
if "sensor_data" not in st.session_state:
    st.session_state.sensor_data = SensorData()
    st.session_state.mqtt_connected = False
    st.session_state.client = None

# Referensi global untuk callback MQTT (menghindari warning ScriptRunContext)
_sensor_data_ref = st.session_state.sensor_data


# Callback MQTT
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        # Update status koneksi menggunakan referensi global
        _sensor_data_ref.set_mqtt_connected(True)
        
        # Subscribe ke semua topic sensor
        client.subscribe(TOPIC_TEMP_AIR)
        client.subscribe(TOPIC_TEMP_SOIL)
        client.subscribe(TOPIC_WATER_LEVEL)
        client.subscribe(TOPIC_SERVO_STATUS)
        client.subscribe(TOPIC_SERVO_CONTROL)

        print("✅ Connected to MQTT Broker!")
        print(f"📡 Subscribed to: {TOPIC_TEMP_AIR}, {TOPIC_TEMP_SOIL}, {TOPIC_WATER_LEVEL}, {TOPIC_SERVO_STATUS}")
    else:
        _sensor_data_ref.set_mqtt_connected(False)
        print(f"❌ Failed to connect, return code {rc}")


def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        
        # Debug logging
        print(f"📨 [{topic}] {payload}")

        # Gunakan referensi global untuk menghindari warning ScriptRunContext
        if topic == TOPIC_TEMP_AIR:
            temp = payload.get("temperature", 0)
            _sensor_data_ref.add_temp_air(temp)
            print(f"  🌤️ Air Temp: {temp}°C")
        elif topic == TOPIC_TEMP_SOIL:
            temp = payload.get("temperature", 0)
            _sensor_data_ref.add_temp_soil(temp)
            print(f"  🌱 Soil Temp: {temp}°C")
        elif topic == TOPIC_WATER_LEVEL:
            # Handle water level with capacity_percent and distance
            capacity = payload.get("capacity_percent", 0)
            distance = payload.get("distance", 0)
            _sensor_data_ref.add_water_level(capacity, distance)
            print(f"  💧 Water: {capacity}% (distance: {distance}cm)")
        elif topic == TOPIC_SERVO_STATUS:
            status = payload.get("status", "OFF")
            _sensor_data_ref.servo_status = status
            print(f"  🎛️ Servo: {status}")

    except json.JSONDecodeError as e:
        print(f"❌ Failed to decode JSON from {msg.topic}: {e}")
    except Exception as e:
        print(f"❌ Error processing message from {msg.topic}: {e}")


def on_disconnect(client, userdata, rc, properties=None):
    _sensor_data_ref.set_mqtt_connected(False)
    print("🔌 Disconnected from MQTT Broker")


# Fungsi untuk setup MQTT client
def setup_mqtt():
    try:
        # Reset status koneksi sebelum mencoba koneksi baru
        if hasattr(st.session_state, "sensor_data") and st.session_state.sensor_data:
            st.session_state.sensor_data.set_mqtt_connected(False)
        st.session_state.mqtt_connected = False

        # Tutup koneksi lama jika ada
        if st.session_state.client is not None:
            try:
                st.session_state.client.loop_stop()
                st.session_state.client.disconnect()
            except:
                pass
            st.session_state.client = None

        # Buat client baru
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect

        # Set timeout yang lebih pendek untuk koneksi
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        st.session_state.client = client

        # Wait sebentar untuk koneksi
        time.sleep(1)

        # Cek apakah koneksi berhasil
        connection_success = is_mqtt_connected()

        if connection_success:
            st.success(f"✅ Berhasil terhubung ke {MQTT_BROKER}")
            return True
        else:
            st.warning("⏳ Sedang mencoba terhubung...")
            return True  # Return true karena proses async

    except Exception as e:
        st.error(f"❌ Gagal menghubungkan ke MQTT Broker: {e}")
        st.session_state.client = None
        return False


# Fungsi untuk cek status koneksi MQTT
def is_mqtt_connected():
    """Check MQTT connection status from multiple sources"""
    # Cek dari session state
    session_connected = getattr(st.session_state, "mqtt_connected", False)

    # Cek dari sensor_data juga
    sensor_connected = False
    if hasattr(st.session_state, "sensor_data") and st.session_state.sensor_data:
        sensor_connected = st.session_state.sensor_data.mqtt_connected

    # Cek apakah client aktif
    client_active = (
        st.session_state.client is not None
        and hasattr(st.session_state.client, "_sock")
        and st.session_state.client._sock is not None
    )

    # Return true jika salah satu indikator menunjukkan terhubung
    return session_connected or sensor_connected or client_active


# Fungsi untuk kontrol servo
def control_servo(action):
    if st.session_state.client and is_mqtt_connected():
        # Format baru: {"pump": "ON/OFF", "servo": 90/0}
        servo_angle = 90 if action == "ON" else 0
        message = json.dumps({"pump": action, "servo": servo_angle})

        # Publish ke topic utama
        st.session_state.client.publish(TOPIC_SERVO_CONTROL, message)
        return True
    return False

# ==================== STREAMLIT UI ====================

# Konfigurasi halaman
st.set_page_config(
    page_title="Multi-Sensor IoT Dashboard",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .sensor-card {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #f0f2f6;
        margin-bottom: 1rem;
    }
    .status-connected {
        color: #00b300;
        font-weight: bold;
    }
    .status-disconnected {
        color: #ff0000;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🌡️ Multi-Sensor IoT Dashboard</div>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Pengaturan")

    # MQTT Connection Status
    st.subheader("Status Koneksi MQTT")
    mqtt_status = is_mqtt_connected()
    if mqtt_status:
        st.markdown(
            '<p class="status-connected">🟢 Terhubung</p>', unsafe_allow_html=True
        )
        # Tampilkan waktu koneksi jika ada
        if (
            hasattr(st.session_state, "sensor_data")
            and st.session_state.sensor_data
            and st.session_state.sensor_data.connection_time
        ):
            conn_time = st.session_state.sensor_data.connection_time.strftime(
                "%H:%M:%S"
            )
            st.caption(f"Terhubung sejak: {conn_time}")

        # Tampilkan info data terakhir
        if (
            hasattr(st.session_state, "sensor_data")
            and st.session_state.sensor_data
            and st.session_state.sensor_data.last_update
        ):
            last_data = st.session_state.sensor_data.last_update.strftime("%H:%M:%S")
            st.caption(f"Data terakhir: {last_data}")
    else:
        st.markdown(
            '<p class="status-disconnected">🔴 Terputus</p>', unsafe_allow_html=True
        )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Hubungkan", use_container_width=True):
            with st.spinner("Menghubungkan..."):
                if setup_mqtt():
                    time.sleep(2)
                    st.rerun()

    with col_btn2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    st.divider()

    # Info Broker
    st.subheader("📡 Info MQTT Broker")
    st.text(f"Broker: {MQTT_BROKER}")
    st.text(f"Port: {MQTT_PORT}")

    st.divider()

    # Kontrol Servo
    st.subheader("💧 Kontrol Pump & Servo")

    # Cek status koneksi untuk kontrol servo
    can_control = is_mqtt_connected()

    if not can_control:
        st.warning("⚠️ MQTT tidak terhubung - tidak bisa mengontrol pump/servo")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ PUMP ON", use_container_width=True, disabled=not can_control):
            if control_servo("ON"):
                st.success("Pump ON!")
                # Force update servo status
                if hasattr(st.session_state, "sensor_data"):
                    st.session_state.sensor_data.servo_status = "ON"
            else:
                st.error("Gagal mengirim perintah")

    with col2:
        if st.button("⏹️ PUMP OFF", use_container_width=True, disabled=not can_control):
            if control_servo("OFF"):
                st.success("Pump OFF!")
                # Force update servo status
                if hasattr(st.session_state, "sensor_data"):
                    st.session_state.sensor_data.servo_status = "OFF"
            else:
                st.error("Gagal mengirim perintah")

    # Status servo dengan indikator visual
    servo_status = st.session_state.sensor_data.servo_status
    status_color = "🟢" if servo_status == "ON" else "🔴"
    st.markdown(f"**Status: {status_color} {servo_status}**")

    st.divider()

    # Auto refresh
    st.subheader("🔄 Auto Refresh")
    auto_refresh_active = st.checkbox("Aktifkan Auto Refresh", value=False, help="⚠️ Dapat menyebabkan tampilan flicker")
    if auto_refresh_active:
        refresh_rate_value = st.slider("Interval (detik)", 1, 10, 5)
    else:
        refresh_rate_value = 5

# Setup MQTT saat pertama kali (hanya jika belum ada)
if st.session_state.client is None:
    setup_mqtt()

# Main content area
tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📈 Grafik Real-time", "ℹ️ Info"])

with tab1:
    # Metrics Row - Wokwi 1 (Sensor Suhu)
    st.subheader("🌡️ Wokwi 1 - Sensor Suhu")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        temp_air_current = st.session_state.sensor_data.temp_air[-1] if st.session_state.sensor_data.temp_air else 0
        st.metric(
            label="🌤️ Suhu Udara",
            value=f"{temp_air_current:.1f} °C",
            delta=f"{temp_air_current - (st.session_state.sensor_data.temp_air[-2] if len(st.session_state.sensor_data.temp_air) > 1 else temp_air_current):.1f} °C"
        )
    
    with col2:
        temp_soil_current = st.session_state.sensor_data.temp_soil[-1] if st.session_state.sensor_data.temp_soil else 0
        st.metric(
            label="🌱 Suhu Tanah",
            value=f"{temp_soil_current:.1f} °C",
            delta=f"{temp_soil_current - (st.session_state.sensor_data.temp_soil[-2] if len(st.session_state.sensor_data.temp_soil) > 1 else temp_soil_current):.1f} °C"
        )
    
    with col3:
        if st.session_state.sensor_data.last_update:
            time_diff = (datetime.now() - st.session_state.sensor_data.last_update).seconds
            st.metric(
                label="⏱️ Update Terakhir",
                value=f"{time_diff} detik yang lalu"
            )
        else:
            st.metric(label="⏱️ Update Terakhir", value="N/A")
    
    st.divider()
    
    # Metrics Row - Wokwi 2 (Sensor Air & Servo)
    st.subheader("💧 Wokwi 2 - Sensor Air & Servo")
    col1, col2, col3 = st.columns(3)

    with col1:
        water_level_current = (
            st.session_state.sensor_data.water_level[-1]
            if st.session_state.sensor_data.water_level
            else 0
        )
        st.metric(
            label="💦 Level Air",
            value=f"{water_level_current:.1f} %",
            delta=f"{water_level_current - (st.session_state.sensor_data.water_level[-2] if len(st.session_state.sensor_data.water_level) > 1 else water_level_current):.1f} %",
        )

    with col2:
        # Show distance info
        water_distance_current = (
            st.session_state.sensor_data.water_distance[-1]
            if st.session_state.sensor_data.water_distance
            else 0
        )
        st.metric(
            label="📏 Jarak Air",
            value=f"{water_distance_current:.1f} cm",
            delta=f"{water_distance_current - (st.session_state.sensor_data.water_distance[-2] if len(st.session_state.sensor_data.water_distance) > 1 else water_distance_current):.1f} cm",
        )

    with col3:
        st.metric(
            label="🎛️ Status Servo", value=st.session_state.sensor_data.servo_status
        )

        # Progress bar untuk water level
        st.progress(water_level_current / 100 if water_level_current <= 100 else 1.0)
        st.caption(f"Kapasitas: {water_level_current:.1f}%")

with tab2:
    st.subheader("📈 Grafik Sensor Real-time")

    if len(st.session_state.sensor_data.timestamps) > 0:
        # Buat subplot untuk semua sensor (termasuk distance)
        fig = make_subplots(
            rows=4,
            cols=1,
            subplot_titles=(
                "Suhu Udara",
                "Suhu Tanah",
                "Level Air (%)",
                "Jarak Air (cm)",
            ),
            vertical_spacing=0.08,
            specs=[
                [{"secondary_y": False}],
                [{"secondary_y": False}],
                [{"secondary_y": False}],
                [{"secondary_y": False}],
            ],
        )

        timestamps = list(st.session_state.sensor_data.timestamps)

        # Suhu Udara
        if st.session_state.sensor_data.temp_air:
            fig.add_trace(
                go.Scatter(
                    x=timestamps[-len(st.session_state.sensor_data.temp_air) :],
                    y=list(st.session_state.sensor_data.temp_air),
                    name="Suhu Udara",
                    line=dict(color="#ff7f0e", width=2),
                    mode="lines+markers",
                ),
                row=1,
                col=1,
            )

        # Suhu Tanah
        if st.session_state.sensor_data.temp_soil:
            fig.add_trace(
                go.Scatter(
                    x=timestamps[-len(st.session_state.sensor_data.temp_soil) :],
                    y=list(st.session_state.sensor_data.temp_soil),
                    name="Suhu Tanah",
                    line=dict(color="#2ca02c", width=2),
                    mode="lines+markers",
                ),
                row=2,
                col=1,
            )

        # Level Air
        if st.session_state.sensor_data.water_level:
            fig.add_trace(
                go.Scatter(
                    x=timestamps[-len(st.session_state.sensor_data.water_level) :],
                    y=list(st.session_state.sensor_data.water_level),
                    name="Level Air",
                    line=dict(color="#1f77b4", width=2),
                    fill="tozeroy",
                    mode="lines+markers",
                ),
                row=3,
                col=1,
            )

        # Distance Air
        if st.session_state.sensor_data.water_distance:
            fig.add_trace(
                go.Scatter(
                    x=timestamps[-len(st.session_state.sensor_data.water_distance) :],
                    y=list(st.session_state.sensor_data.water_distance),
                    name="Jarak Air",
                    line=dict(color="#d62728", width=2),
                    mode="lines+markers",
                ),
                row=4,
                col=1,
            )

        # Update layout
        fig.update_xaxes(title_text="Waktu", row=4, col=1)
        fig.update_yaxes(title_text="°C", row=1, col=1)
        fig.update_yaxes(title_text="°C", row=2, col=1)
        fig.update_yaxes(title_text="%", row=3, col=1)
        fig.update_yaxes(title_text="cm", row=4, col=1)

        fig.update_layout(height=1000, showlegend=True, hovermode="x unified")

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📡 Menunggu data dari sensor...")

with tab3:
    st.subheader("ℹ️ Informasi Dashboard")
    
    st.markdown(
        """
    ### 🎯 Fitur Dashboard:
    
    **Wokwi 1 - Monitoring Suhu:**
    - 🌤️ Sensor Suhu Udara (DHT22)
    - 🌱 Sensor Suhu Tanah (DHT22)
    
    **Wokwi 2 - Monitoring & Kontrol Air:**
    - 💦 Sensor Level Air (HC-SR04)
    - 📏 Jarak Air dari Sensor
    - 🎛️ Kontrol Pump/Servo untuk Aliran Air
    
    ### 📋 MQTT Topics yang Digunakan:
    
    **Subscribe (Dashboard Menerima Data):**
    - `irrigation/sensor/environment` - Data suhu udara dari Wokwi 1
    - `irrigation/sensor/soil` - Data suhu tanah dari Wokwi 1
    - `irrigation/sensor/water_level` - Data level air & jarak dari Wokwi 2
    - `irrigation/actuator/status` - Status pump/servo dari Wokwi 2
    
    **Publish (Dashboard Mengirim Perintah):**
    - `irrigation/actuator/control` - Kontrol pump/servo ke Wokwi 2
    
    ### 📝 Format Pesan JSON yang Digunakan:
    
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
    - `distance`: Jarak dari sensor ke permukaan air (cm)
    
    **4. Status Servo (`irrigation/actuator/status`):**
    ```json
    {
        "status": "OFF"
    }
    ```
    - `status`: "ON" atau "OFF"
    
    **5. Kontrol Pump/Servo (`irrigation/actuator/control`):**
    ```json
    {
        "pump": "ON",
        "servo": 90
    }
    ```
    - `pump`: "ON" untuk hidupkan, "OFF" untuk matikan
    - `servo`: Sudut servo (90° untuk ON, 0° untuk OFF)
    
    ### 🔧 Cara Menggunakan Dashboard:
    
    1. **Koneksi MQTT:**
       - Klik tombol "🔄 Hubungkan" di sidebar
       - Tunggu hingga status menjadi 🟢 Terhubung
    
    2. **Monitor Data:**
       - Tab "📊 Dashboard" untuk melihat data real-time
       - Tab "📈 Grafik Real-time" untuk visualisasi
    
    3. **Kontrol Pump:**
       - Pastikan MQTT terhubung
       - Klik "▶️ PUMP ON" untuk hidupkan
       - Klik "⏹️ PUMP OFF" untuk matikan
    
    4. **Refresh Data:**
       - Manual: Klik tombol "🔄 Refresh" di sidebar
       - Auto: Centang "Aktifkan Auto Refresh" (optional)
    
    ### 💡 Tips & Catatan:
    
    - Dashboard menyimpan hingga 50 data point terakhir
    - Auto refresh dapat menyebabkan flicker, gunakan seperlunya
    - Data MQTT masuk real-time meskipun auto-refresh off
    - Lihat terminal untuk debug log setiap data yang masuk
    - Broker: `broker.hivemq.com` (public MQTT broker)
    
    ### 🐛 Troubleshooting:
    
    - **MQTT tidak terhubung:** Cek koneksi internet & Wokwi
    - **Data tidak masuk:** Pastikan topic MQTT sama persis
    - **Kontrol tidak berfungsi:** Pastikan status 🟢 Terhubung
    - **Grafik kosong:** Tunggu data masuk atau refresh manual
    """
    )

if auto_refresh_active:
    # Pastikan tidak ada race condition dengan menambahkan delay
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    current_time = time.time()
    time_since_refresh = current_time - st.session_state.last_refresh
    
    # Hanya refresh jika sudah melewati interval yang ditentukan
    if time_since_refresh >= refresh_rate_value:
        st.session_state.last_refresh = current_time
        time.sleep(0.1)  # Small delay untuk mencegah double rendering
        st.rerun()
    else:
        # Tunggu sisa waktu
        remaining = refresh_rate_value - time_since_refresh
        time.sleep(min(remaining, 1))  # Check every 1 second max
        st.rerun()
