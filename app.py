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

    total_forecast = draft_df["Jun"].sum()
    total_rf10 = draft_df["RF10"].sum()
    total_actual_forecast = draft_df["Actual + Forecast"].sum()

    # KPI cards display (styled like metric cards)
    kpi1, kpi2, kpi3 = st.columns(3)

    with kpi1:
        st.markdown(f"""
        <div style="background-color: #f9f9f9; padding: 1.5rem; border-radius: 10px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h4 style="margin-bottom: 0.5rem; color: #333;">Total RF10</h4>
            <p style="font-size: 1.8rem; font-weight: bold; color: #1f77b4;">{total_rf10:,}</p>
        </div>
        """, unsafe_allow_html=True)

    with kpi2:
        st.markdown(f"""
        <div style="background-color: #f9f9f9; padding: 1.5rem; border-radius: 10px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h4 style="margin-bottom: 0.5rem; color: #333;">Total Actual + Forecast</h4>
            <p style="font-size: 1.8rem; font-weight: bold; color: #9467bd;">{total_actual_forecast:,}</p>
        </div>
        """, unsafe_allow_html=True)

    with kpi3:
        st.markdown(f"""
        <div style="background-color: #f9f9f9; padding: 1.5rem; border-radius: 10px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
            <h4 style="margin-bottom: 0.5rem; color: #333;">Total June Forecast</h4>
            <p style="font-size: 1.8rem; font-weight: bold; color: #2ca02c;">{total_forecast:,} units</p>
        </div>
        """, unsafe_allow_html=True)

    # Reorder and clean up for bottom table
    table_df = draft_df[["Grouped Customer", "SKU Name", "Jun", "RF10", "Actual + Forecast", "Forecast Gap"]].copy()

    def format_forecast_gap(val):
        color = "green" if val > 0 else "red" if val < 0 else "black"
        return f"<span style='color: {color}; font-weight: bold;'>{val}</span>"

    styled_cells = {
        col: table_df[col] if col != "Forecast Gap" else [format_forecast_gap(v) for v in table_df[col]]
        for col in table_df.columns
    }

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(table_df.columns),
            fill_color='#003049',
            align='left',
            font=dict(color='white', size=14)
        ),
        cells=dict(
            values=list(styled_cells.values()),
            fill_color=[["#f6f6f6" if i % 2 == 0 else "#ffffff" for i in range(len(table_df))]] * len(table_df.columns),
            align='left',
            font=dict(size=14),
            format=[""] * len(table_df.columns),
            height=30,
            line_color='lightgrey',
            suffix=None,
            unsafe_allow_html=True
        )
    )])
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))

    st.plotly_chart(fig, use_container_width=True)

# ----------- SUBMIT FORM -----------
with st.form("forecast_form"):
    submitted = st.form_submit_button("✅ Submit Forecast")
