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
    table {
        border-collapse: collapse;
        width: 100%;
        font-family: Arial, sans-serif;
    }
    thead tr {
        background-color: #003049;
        color: white;
    }
    tbody tr:nth-child(odd) {
        background-color: #f6f6f6;
    }
    tbody tr:nth-child(even) {
        background-color: #ffffff;
    }
    td, th {
        padding: 10px;
        text-align: left;
        border-bottom: 1px solid #ddd;
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

rep_name = st.selectbox("Select your name (Grouped Customer Owner)", get_unique_options(df, "Grouped Customer Owner"))
df_rep = df[df["Grouped Customer Owner"] == rep_name]

col1, col2 = st.columns(2)
with col1:
    customer = st.selectbox("Grouped Customer", ["All"] + get_unique_options(df_rep, "Grouped Customer"))
with col2:
    sku_name = st.selectbox("SKU Name", ["All"] + get_unique_options(df_rep, "SKU Name"))

mask = (df["Grouped Customer Owner"] == rep_name)
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

edited_df = st.data_editor(
    display_df[["Grouped Customer", "SKU Name", "RF10", "Progress", "Jun"]],
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

# ----------- BOTTOM TABLE AFTER CALCULATION -----------
if "stored_forecast" in st.session_state:
    draft_df = st.session_state["stored_forecast"].copy()
    draft_df["Progress"] = df_filtered[monthly_cols].sum(axis=1).astype(int)
    draft_df["Actual + Forecast"] = (draft_df["Progress"] + draft_df["Jun"]).astype(int)
    draft_df["Forecast Gap"] = (draft_df["Actual + Forecast"] - draft_df["RF10"]).astype(int)

    def color_gap(val):
        if pd.isna(val):
            return ""
        color = "#28a745" if val > 0 else "#dc3545" if val < 0 else "black"
        return f"color: {color}"

    styled_df = draft_df.style.applymap(color_gap, subset=["Forecast Gap"])

    total_forecast = draft_df["Jun"].sum()
    total_rf10 = draft_df["RF10"].sum()
    total_actual_forecast = draft_df["Actual + Forecast"].sum()

    draft_df = draft_df[[
        "Grouped Customer", "SKU Name", "Jun", "RF10", "Actual + Forecast", "Forecast Gap"
    ]]

    st.dataframe(
        styled_df.format(precision=0),
        use_container_width=True,
        hide_index=True
    )

    st.markdown(
        f"""
        <div style="margin-top: 1rem; font-size: 1.2rem; font-weight: 600; color: #004080; text-align: right; padding-right: 2rem;">
            📦 Total RF10: <span style="color:#0078D4;">{total_rf10:,.0f}</span> &nbsp;&nbsp;|
            📈 Total Actual + Forecast: <span style="color:#6f42c1;">{total_actual_forecast:,.0f}</span> &nbsp;&nbsp;|
            🧱 Total June Forecast: <span style="color:#28a745;">{total_forecast:,.0f}</span> units
        </div>
        """,
        unsafe_allow_html=True
    )

# ----------- SUBMIT FORM -----------
with st.form("forecast_form"):
    submitted = st.form_submit_button("✅ Submit Forecast")
