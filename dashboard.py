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
        self.timestamps = deque(maxlen=MAX_DATA_POINTS)
        self.servo_status = "OFF"
        self.last_update = None
        
    def add_temp_air(self, value):
        self.temp_air.append(value)
        self._update_timestamp()
    
    def add_temp_soil(self, value):
        self.temp_soil.append(value)
        self._update_timestamp()
    
    def add_water_level(self, value):
        self.water_level.append(value)
        self._update_timestamp()
    
    def _update_timestamp(self):
        if len(self.timestamps) < MAX_DATA_POINTS or \
           (len(self.timestamps) > 0 and 
            (datetime.now() - datetime.fromisoformat(self.timestamps[-1])).seconds >= 1):
            self.timestamps.append(datetime.now().isoformat())
        self.last_update = datetime.now()

# Inisialisasi session state
if 'sensor_data' not in st.session_state:
    st.session_state.sensor_data = SensorData()
    st.session_state.mqtt_connected = False
    st.session_state.client = None

# Callback MQTT
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        st.session_state.mqtt_connected = True
        # Subscribe ke semua topic sensor
        client.subscribe(TOPIC_TEMP_AIR)
        client.subscribe(TOPIC_TEMP_SOIL)
        client.subscribe(TOPIC_WATER_LEVEL)
        client.subscribe(TOPIC_SERVO_STATUS)
        print("Connected to MQTT Broker!")
    else:
        st.session_state.mqtt_connected = False
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        
        if msg.topic == TOPIC_TEMP_AIR:
            st.session_state.sensor_data.add_temp_air(payload.get('temperature', 0))
        elif msg.topic == TOPIC_TEMP_SOIL:
            st.session_state.sensor_data.add_temp_soil(payload.get('temperature', 0))
        elif msg.topic == TOPIC_WATER_LEVEL:
            st.session_state.sensor_data.add_water_level(payload.get('level', 0))
        elif msg.topic == TOPIC_SERVO_STATUS:
            st.session_state.sensor_data.servo_status = payload.get('status', 'OFF')
            
    except json.JSONDecodeError:
        print(f"Failed to decode message from {msg.topic}")
    except Exception as e:
        print(f"Error processing message: {e}")

def on_disconnect(client, userdata, rc, properties=None):
    st.session_state.mqtt_connected = False
    print("Disconnected from MQTT Broker")

# Fungsi untuk setup MQTT client
def setup_mqtt():
    if st.session_state.client is None:
        # Gunakan CallbackAPIVersion.VERSION2 untuk menghindari deprecation warning
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_disconnect = on_disconnect
        
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_start()
            st.session_state.client = client
            return True
        except Exception as e:
            st.error(f"Gagal menghubungkan ke MQTT Broker: {e}")
            return False
    return True

# Fungsi untuk kontrol servo
def control_servo(action):
    if st.session_state.client and st.session_state.mqtt_connected:
        message = json.dumps({"action": action})
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
    if st.session_state.mqtt_connected:
        st.markdown('<p class="status-connected">🟢 Terhubung</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p class="status-disconnected">🔴 Terputus</p>', unsafe_allow_html=True)
    
    if st.button("🔄 Hubungkan ke MQTT", use_container_width=True):
        with st.spinner("Menghubungkan..."):
            if setup_mqtt():
                time.sleep(2)
                st.rerun()
    
    st.divider()
    
    # Info Broker
    st.subheader("📡 Info MQTT Broker")
    st.text(f"Broker: {MQTT_BROKER}")
    st.text(f"Port: {MQTT_PORT}")
    
    st.divider()
    
    # Kontrol Servo
    st.subheader("💧 Kontrol Servo Air")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ ON", use_container_width=True):
            if control_servo("ON"):
                st.success("Servo ON!")
            else:
                st.error("Gagal mengirim perintah")
    
    with col2:
        if st.button("⏹️ OFF", use_container_width=True):
            if control_servo("OFF"):
                st.success("Servo OFF!")
            else:
                st.error("Gagal mengirim perintah")
    
    st.text(f"Status: {st.session_state.sensor_data.servo_status}")
    
    st.divider()
    
    # Auto refresh
    st.subheader("🔄 Auto Refresh")
    auto_refresh = st.checkbox("Aktifkan Auto Refresh", value=True)
    if auto_refresh:
        refresh_rate = st.slider("Interval (detik)", 1, 10, 3)

# Setup MQTT saat pertama kali
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
        water_level_current = st.session_state.sensor_data.water_level[-1] if st.session_state.sensor_data.water_level else 0
        st.metric(
            label="💦 Level Air",
            value=f"{water_level_current:.1f} %",
            delta=f"{water_level_current - (st.session_state.sensor_data.water_level[-2] if len(st.session_state.sensor_data.water_level) > 1 else water_level_current):.1f} %"
        )
    
    with col2:
        st.metric(
            label="🎛️ Status Servo",
            value=st.session_state.sensor_data.servo_status
        )
    
    with col3:
        # Progress bar untuk water level
        st.progress(water_level_current / 100 if water_level_current <= 100 else 1.0)
        st.caption(f"Kapasitas: {water_level_current:.1f}%")

with tab2:
    st.subheader("📈 Grafik Sensor Real-time")
    
    if len(st.session_state.sensor_data.timestamps) > 0:
        # Buat subplot untuk semua sensor
        fig = make_subplots(
            rows=3, cols=1,
            subplot_titles=('Suhu Udara', 'Suhu Tanah', 'Level Air'),
            vertical_spacing=0.12,
            specs=[[{"secondary_y": False}],
                   [{"secondary_y": False}],
                   [{"secondary_y": False}]]
        )
        
        timestamps = list(st.session_state.sensor_data.timestamps)
        
        # Suhu Udara
        if st.session_state.sensor_data.temp_air:
            fig.add_trace(
                go.Scatter(
                    x=timestamps[-len(st.session_state.sensor_data.temp_air):],
                    y=list(st.session_state.sensor_data.temp_air),
                    name='Suhu Udara',
                    line=dict(color='#ff7f0e', width=2),
                    mode='lines+markers'
                ),
                row=1, col=1
            )
        
        # Suhu Tanah
        if st.session_state.sensor_data.temp_soil:
            fig.add_trace(
                go.Scatter(
                    x=timestamps[-len(st.session_state.sensor_data.temp_soil):],
                    y=list(st.session_state.sensor_data.temp_soil),
                    name='Suhu Tanah',
                    line=dict(color='#2ca02c', width=2),
                    mode='lines+markers'
                ),
                row=2, col=1
            )
        
        # Level Air
        if st.session_state.sensor_data.water_level:
            fig.add_trace(
                go.Scatter(
                    x=timestamps[-len(st.session_state.sensor_data.water_level):],
                    y=list(st.session_state.sensor_data.water_level),
                    name='Level Air',
                    line=dict(color='#1f77b4', width=2),
                    fill='tozeroy',
                    mode='lines+markers'
                ),
                row=3, col=1
            )
        
        # Update layout
        fig.update_xaxes(title_text="Waktu", row=3, col=1)
        fig.update_yaxes(title_text="°C", row=1, col=1)
        fig.update_yaxes(title_text="°C", row=2, col=1)
        fig.update_yaxes(title_text="%", row=3, col=1)
        
        fig.update_layout(
            height=800,
            showlegend=True,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("📡 Menunggu data dari sensor...")

with tab3:
    st.subheader("ℹ️ Informasi Dashboard")
    
    st.markdown("""
    ### 🎯 Fitur Dashboard:
    
    **Wokwi 1 - Monitoring Suhu:**
    - 🌤️ Sensor Suhu Udara
    - 🌱 Sensor Suhu Tanah
    
    **Wokwi 2 - Monitoring & Kontrol Air:**
    - 💦 Sensor Level Air
    - 🎛️ Kontrol Servo untuk Aliran Air
    
    ### 📋 MQTT Topics yang Digunakan:
    
    **Wokwi 1 (Subscribe):**
    - `wokwi/sensor/temp_air` - Data suhu udara
    - `wokwi/sensor/temp_soil` - Data suhu tanah
    
    **Wokwi 2 (Subscribe):**
    - `wokwi/sensor/water_level` - Data level air
    - `wokwi/status/servo` - Status servo
    
    **Wokwi 2 (Publish):**
    - `wokwi/control/servo` - Kontrol servo (ON/OFF)
    
    ### 📝 Format Pesan JSON:
    
    **Sensor Data:**
    ```json
    {
        "temperature": 25.5,  // untuk suhu
        "level": 75.0,        // untuk level air
        "status": "ON"        // untuk status servo
    }
    ```
    
    **Kontrol Servo:**
    ```json
    {
        "action": "ON"  // atau "OFF"
    }
    ```
    
    ### 🔧 Cara Menggunakan:
    1. Pastikan Wokwi Anda terhubung ke MQTT broker yang sama
    2. Klik tombol "Hubungkan ke MQTT" di sidebar
    3. Monitor data sensor secara real-time
    4. Gunakan tombol ON/OFF untuk mengontrol servo
    
    ### 💡 Tips:
    - Aktifkan Auto Refresh untuk update otomatis
    - Lihat tab "Grafik Real-time" untuk visualisasi data
    - Dashboard menyimpan hingga 50 data point terakhir
    """)

# Auto refresh
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
