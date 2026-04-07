import streamlit as st
from supabase import create_client, Client
import pandas as pd
import time

# --- Page Configuration ---
st.set_page_config(page_title="EV Real Time Dashboard", page_icon="⚡", layout="wide")
st.title("⚡ Tesla Model S Range Prediction")

# --- Initialize Database Connection ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error(f"Failed to connect to Supabase. Please check your .streamlit/secrets.toml file. Error: {e}")
    st.stop()

# --- Fetch Data ---
def get_data():
    # Fetch the 100 most recent rows, ordered by ID (newest first)
    response = supabase.table('ev_telemetry').select("*").order('id', desc=True).limit(100).execute()
    
    if response.data:
        df = pd.DataFrame(response.data)
        # Sort back to chronological order for the charts to flow left-to-right
        df = df.sort_values(by='id', ascending=True) 
        return df
    return pd.DataFrame()

df = get_data()

# --- Dashboard Layout ---
if not df.empty:
    latest = df.iloc[-1]

    # 1. Top Row: Key Performance Indicators (KPIs)
    st.subheader("EV Live Telemetry")
    col1, col2, col3 = st.columns(3)
    
    # We display the absolute latest value from the database here
    col1.metric("Predicted Range", f"{latest['predicted_range']:.2f} km")
    col2.metric("Current Speed", f"{latest['speed_kmh']:.1f} KMH")
    col3.metric("Battery Status", f"{latest['battery_status']:.1f} %")

    st.divider()

    # 2. Bottom Row: Visual Trends
    st.subheader("Historical Trends")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.write("🔋 **Predicted Range Over Time (km)**")
        st.line_chart(df.set_index('time_sec')['predicted_range'], color="#1f77b4")

        st.write("⚡ **Battery Drain Over Time (%)**")
        st.line_chart(df.set_index('time_sec')['battery_status'], color="#2ca02c")

    with chart_col2:
        st.write("🏎️ **Speed Profile (KMH)**")
        st.line_chart(df.set_index('time_sec')['speed_kmh'], color="#ff7f0e")

else:
    st.info("Waiting for telemetry data... Run your main.py script to start streaming!")

# --- Real-Time Loop ---
# This forces the Streamlit app to refresh every 1 second
time.sleep(1)
st.rerun()