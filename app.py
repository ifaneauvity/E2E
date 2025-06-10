import streamlit as st
import pandas as pd
from databricks import sql
from io import BytesIO
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Sales Forecast Tool", layout="wide")

# ----------- FORCE SIDEBAR OPEN -----------
st.markdown("""
<style>
    [data-testid='stSidebar'][aria-expanded='false'] > div:first-child {
        display: block;
    }
</style>
""", unsafe_allow_html=True)

# ----------- CUSTOM STYLES -----------
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        font-size: 1.2rem;
    }
    h1, h2, h3 {
        font-weight: 600;
        color: #2F3E46;
    }
    .stButton>button {
        background-color: #0078D4;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        height: 3em;
        width: auto;
        font-size: 1.2rem;
    }
</style>
""", unsafe_allow_html=True)

# ----------- LOAD DATA -----------
@st.cache_data
def load_forecast_from_databricks():
    connection = sql.connect(
        server_hostname=st.secrets["databricks_host"].replace("https://", ""),
        http_path=st.secrets["databricks_path"],
        access_token=st.secrets["databricks_token"]
    )
    query = f"""
        SELECT * 
        FROM {st.secrets["databricks_catalog"]}.{st.secrets["databricks_schema"]}.{st.secrets["databricks_table"]}
    """
    df = pd.read_sql(query, connection)
    connection.close()
    return df

@st.cache_data
def get_unique_options(df, column):
    return sorted(df[column].dropna().unique())

with st.spinner("Connecting to Databricks and loading data..."):
    df = load_forecast_from_databricks()

df.columns = df.columns.str.strip()
monthly_cols = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May"]
for col in monthly_cols + ["Jun", "RF10"]:
    if col not in df.columns:
        df[col] = 0
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

# ----------- SIDEBAR VIEW SWITCH -----------
view = st.sidebar.radio("Choose View:", ["🖍️ Rep Forecast Input", "📊 Sales Manager View"])

# ----------- (Rest of the app remains unchanged) -----------
