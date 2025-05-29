import streamlit as st
import pandas as pd
from databricks import sql
from io import BytesIO
import plotly.graph_objects as go

st.set_page_config(page_title="Sales Forecast Input Tool", layout="wide")

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

st.title("🖍️ Edit June Forecast")

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

with st.spinner("Connecting to Databricks and loading data..."):
    df = load_forecast_from_databricks()

df.columns = df.columns.str.strip()

# ----------- FILTERING UI -----------
st.header("🧱 Filter Your Data")

owner_options = ["All"] + get_unique_options(df, "Grouped Customer Owner")
rep_name = st.selectbox("Select your name (Grouped Customer Owner)", owner_options)

if rep_name != "All":
    df_rep = df[df["Grouped Customer Owner"] == rep_name]
else:
    df_rep = df.copy()

col1, col2 = st.columns(2)
with col1:
    customer = st.selectbox("Grouped Customer", ["All"] + get_unique_options(df_rep, "Grouped Customer"))
with col2:
    sku_name = st.selectbox("SKU Name", ["All"] + get_unique_options(df_rep, "SKU Name"))

# ----------- Optional Columns -----------
optional_columns = [
    "A24 Total", "A24 Total_9L", "A24 Total_Value",
    "Contract_Vol_Q1", "Contract_Vol_Q2", "Contract_Vol_Q3", "Contract_Vol_Q4",
    "Contract_Vol_Q1_9L", "Contract_Vol_Q2_9L", "Contract_Vol_Q3_9L", "Contract_Vol_Q4_9L",
    "Contract_Vol_9L", "Contract_Value_Q1", "Contract_Value_Q2", "Contract_Value_Q3", "Contract_Value_Q4",
    "RF10_9L", "RF10_Value"
]

selected_optional_columns = st.multiselect(
    "📊 Select Additional Columns to Display",
    optional_columns
)

mask = pd.Series(True, index=df.index)
if rep_name != "All":
    mask &= df["Grouped Customer Owner"] == rep_name
if customer != "All":
    mask &= df["Grouped Customer"] == customer
if sku_name != "All":
    mask &= df["SKU Name"] == sku_name

df_filtered = df[mask]

# ----------- CLEANING + DEFAULTS -----------
monthly_cols = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May"]
for col in monthly_cols + ["Jun", "RF10"]:
    if col not in df_filtered.columns:
        df_filtered[col] = 0
    df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce").fillna(0)

# ----------- BUILD EDITOR TABLE -----------
display_df = df_filtered[["Grouped Customer", "SKU Name", "Jun", "RF10"]].copy()
display_df["Progress"] = df_filtered[monthly_cols].sum(axis=1).astype(int)
display_df["Jun"] = pd.to_numeric(display_df["Jun"], errors="coerce").fillna(0).astype(int)
display_df["RF10"] = display_df["RF10"].round(0).astype(int)

for col in selected_optional_columns:
    if col in df_filtered.columns:
        display_df[col] = df_filtered[col]

main_columns = ["Grouped Customer", "SKU Name", "RF10", "Progress", "Jun"]
final_columns = main_columns + selected_optional_columns

edited_df = st.data_editor(
    display_df[final_columns],
    column_config={
        "Grouped Customer": st.column_config.TextColumn(disabled=True),
        "SKU Name": st.column_config.TextColumn(disabled=True),
        "RF10": st.column_config.NumberColumn(disabled=True),
        "Progress": st.column_config.NumberColumn(disabled=True),
        "Jun": st.column_config.NumberColumn(
            label="✏️ June Forecast (Editable)",
            help="Enter forecast values for June",
            format="%d",
            disabled=False
        )
    },
    use_container_width=True,
    key="editor_june"
)

# ----------- STORE DRAFT -----------
if st.button("🗂️ Store Draft (Calculate Totals)"):
    st.session_state["stored_forecast"] = edited_df.copy()

# ----------- SUBMIT FORM -----------
with st.form("forecast_form"):
    submitted = st.form_submit_button("✅ Submit Forecast")
