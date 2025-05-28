import streamlit as st
import pandas as pd
from databricks import sql
from io import BytesIO

st.set_page_config(page_title="Sales Forecast Input Tool", layout="wide")

# ----------- CUSTOM STYLES -----------
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
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
    }
    .stDownloadButton>button {
        background-color: #28A745;
        color: white;
        font-weight: 600;
        border-radius: 8px;
        height: 3em;
        width: auto;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Sales Forecast Input Tool")

# ----------- LOAD FROM DATABRICKS -----------

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

# ----------- APP LOGIC -----------

with st.spinner("Connecting to Databricks and loading data..."):
    df = load_forecast_from_databricks()

# Strip columns after loading
df.columns = df.columns.str.strip()

# ----------- FILTERS -----------
st.header("🧭 Filter Your Data")

# Step 1: Select rep name
rep_name = st.selectbox(
    "Select your name (Grouped Customer Owner)",
    get_unique_options(df, "Grouped Customer Owner")
)

# Filter the full dataset down to the selected rep first
df_rep = df[df["Grouped Customer Owner"] == rep_name]

# Step 2: Dynamically filter options based on rep's data
col1, col2 = st.columns(2)

with col1:
    customer = st.selectbox("Grouped Customer", ["All"] + get_unique_options(df_rep, "Grouped Customer"))
with col2:
    sku_name = st.selectbox("SKU Name", ["All"] + get_unique_options(df_rep, "SKU Name"))

# Apply selected filters
mask = (df["Grouped Customer Owner"] == rep_name)
if customer != "All":
    mask &= (df["Grouped Customer"] == customer)
if sku_name != "All":
    mask &= (df["SKU Name"] == sku_name)

df_filtered = df[mask]

st.markdown("---")

# ----------- DATA EDITING FORM -----------
st.header("📝 Edit June Forecast")

# Only show relevant columns
display_df = df_filtered[["Grouped Customer", "SKU Name", "RF10", "May", "Jun"]].copy()

# Clean 'Jun' column: convert '-' or blanks to 0, and force numeric
display_df["Jun"] = pd.to_numeric(display_df["Jun"], errors="coerce").fillna(0).astype(int)

# Make only 'Jun' editable — freeze others
with st.form("forecast_form"):
    editable_df = st.data_editor(
        display_df,
        column_config={
            "Grouped Customer": st.column_config.TextColumn(disabled=True),
            "SKU Name": st.column_config.TextColumn(disabled=True),
            "RF10": st.column_config.NumberColumn(disabled=True),
            "May": st.column_config.NumberColumn(disabled=True),
            "Jun": st.column_config.NumberColumn(
                label="✏️ June Forecast (Editable)",
                help="Enter forecast values for June",
                format="%d",
                disabled=False
            )
        },
        use_container_width=True,
        key="editable_forecast"
    )

    total_forecast = editable_df["Jun"].sum()
    st.markdown(f"**🧮 Total June Forecast: {total_forecast:,.0f} units**")

    submitted = st.form_submit_button("✅ Submit Forecast")

