import streamlit as st
import pandas as pd
from databricks import sql
from io import BytesIO
import plotly.graph_objects as go
import datetime

st.set_page_config(page_title="Sales Forecast Input Tool", layout="wide")

# ----------- CUSTOM STYLES & SIDEBAR -----------
st.markdown("""
<style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        font-size: 1.1rem;
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
        font-size: 1.15rem;
    }
    thead tr th {
        position: sticky !important;
        top: 0;
        background-color: #f0f2f6 !important;
        z-index: 10;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar for navigation and export
st.sidebar.title("Navigation")
st.sidebar.markdown("Quick links and actions:")

if st.sidebar.button("⬇️ Download Your Forecast (CSV)"):
    if "stored_forecast" in st.session_state:
        csv = st.session_state["stored_forecast"].to_csv(index=False).encode()
        st.sidebar.download_button(
            label="Download CSV",
            data=csv,
            file_name="june_forecast.csv",
            mime="text/csv"
        )
    else:
        st.sidebar.warning("Please save a draft first.")

st.sidebar.markdown("---")
st.sidebar.info("Need help? Hover over tooltips ℹ️ for guidance.")

# ----------- LOAD FROM DATABRICKS -----------
@st.cache_data
def load_forecast_from_databricks():
    try:
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
        return df, ""
    except Exception as e:
        return pd.DataFrame(), f"Error loading from Databricks: {e}"

@st.cache_data
def get_unique_options(df, column):
    return sorted(df[column].dropna().unique())

def get_main_monthly_cols():
    return ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May"]

def highlight_edited(val, base_val):
    if val != base_val:
        return 'background-color: #fff3cd; font-weight: bold'
    return ''

# ----------- TITLE & LOADING -----------
st.title("🖍️ Edit June Forecast")

with st.spinner("Connecting to Databricks and loading data..."):
    df, db_error = load_forecast_from_databricks()

if db_error:
    st.error(db_error)
    st.stop()

if st.button("🔄 Refresh from Databricks"):
    load_forecast_from_databricks.clear()
    st.rerun()

df.columns = df.columns.str.strip()

# ----------- FILTERING UI -----------
st.header("Filter Your Data")

rep_options = ["All"] + get_unique_options(df, "Grouped Customer Owner")
rep_name = st.selectbox("Select your name (Grouped Customer Owner)", rep_options, help="Filter by your name to see your customers.")

if rep_name != "All":
    df_rep = df[df["Grouped Customer Owner"] == rep_name]
else:
    df_rep = df.copy()

col1, col2 = st.columns(2)
with col1:
    customer = st.selectbox("Grouped Customer", ["All"] + get_unique_options(df_rep, "Grouped Customer"), help="Filter by customer group.")
with col2:
    sku_name = st.selectbox("SKU Name", ["All"] + get_unique_options(df_rep, "SKU Name"), help="Filter by SKU.")

optional_columns = [
    "A24 Total", "A24 Total_9L", "A24 Total_Value",
    "Contract_Vol_Q1", "Contract_Vol_Q2", "Contract_Vol_Q3", "Contract_Vol_Q4",
    "Contract_Vol_Q1_9L", "Contract_Vol_Q2_9L", "Contract_Vol_Q3_9L", "Contract_Vol_Q4_9L",
    "Contract_Vol_9L", "Contract_Value_Q1", "Contract_Value_Q2", "Contract_Value_Q3", "Contract_Value_Q4",
    "RF10_9L", "RF10_Value"
]

selected_optional_columns = st.multiselect("📊 Select Additional Columns to Display", optional_columns, help="Choose extra columns to view for more detail.")

mask = pd.Series([True] * len(df))
if rep_name != "All":
    mask &= df["Grouped Customer Owner"] == rep_name
if customer != "All":
    mask &= df["Grouped Customer"] == customer
if sku_name != "All":
    mask &= df["SKU Name"] == sku_name

df_filtered = df[mask]

# ----------- CLEANING + DEFAULTS -----------
monthly_cols = get_main_monthly_cols()
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

main_columns = ["Grouped Customer", "SKU Name", "RF10", "Progress"]
final_columns = main_columns + selected_optional_columns + ["Jun"]

column_config = {
    "Grouped Customer": st.column_config.TextColumn(disabled=True),
    "SKU Name": st.column_config.TextColumn(disabled=True),
    "RF10": st.column_config.NumberColumn(disabled=True, help="Target bottles for this customer/SKU"),
    "Progress": st.column_config.NumberColumn(disabled=True, help="Total actualized for previous months"),
    "Jun": st.column_config.NumberColumn(
        label="🔶 EDIT June Forecast",
        help="Enter your forecast for June. Only positive numbers are allowed.",
        format="%d",
        disabled=False
    )
}

for col in selected_optional_columns:
    column_config[col] = st.column_config.TextColumn(disabled=True)

# For change tracking: store original June values
if "original_june" not in st.session_state:
    st.session_state["original_june"] = display_df["Jun"].copy()

edited_df = st.data_editor(
    display_df[final_columns],
    column_config=column_config,
    use_container_width=True,
    key="editor_june"
)

# ----------- VALIDATION & HIGHLIGHTING -----------
edited_df["Jun"] = pd.to_numeric(edited_df["Jun"], errors="coerce").fillna(0).astype(int)
invalid_rows = edited_df[edited_df["Jun"] < 0]
if not invalid_rows.empty:
    st.warning("Some 'June' values are negative. Please correct them before storing/submitting your forecast.")

# Highlight edited cells
st.markdown("#### Edited Forecast Table (highlighted cells show changes since load)")
styled_df = edited_df.style.apply(
    lambda col: [highlight_edited(v, o) for v, o in zip(col, st.session_state["original_june"])] 
    if col.name == "Jun" else [''] * len(col),
    axis=0
)
st.dataframe(styled_df, use_container_width=True, height=350)

# ----------- STORE DRAFT & AUDIT -----------
if st.button("📂 Store Draft (Calculate Totals)"):
    if not invalid_rows.empty:
        st.error("Cannot store draft: please ensure all June values are non-negative.")
    else:
        st.session_state["stored_forecast"] = edited_df.copy()
        st.session_state["audit_log"] = st.session_state.get("audit_log", []) + [
            {
                "user": st.session_state.get("user", "Unknown"),
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "action": "Store Draft",
                "row_count": len(edited_df)
            }
        ]
        st.success("Draft stored! You can now review KPIs below.")

# ----------- KPI & SUMMARY -----------
if "stored_forecast" in st.session_state:
    draft_df = st.session_state["stored_forecast"].copy()
    draft_df["Progress"] = df_filtered[monthly_cols].sum(axis=1).astype(int)
    draft_df["Actual + Forecast"] = (draft_df["Progress"] + draft_df["Jun"]).astype(int)
    draft_df["Forecast Gap"] = (draft_df["Actual + Forecast"] - draft_df["RF10"]).astype(int)

    total_forecast = draft_df["Jun"].sum()
    total_rf10 = draft_df["RF10"].sum()
    total_actual_forecast = draft_df["Actual + Forecast"].sum()

    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric("Total RF10", f"{total_rf10:,} bottles")
    with kpi2:
        st.metric("Total Actual + Forecast", f"{total_actual_forecast:,} bottles")
    with kpi3:
        st.metric("Total June Forecast", f"{total_forecast:,} bottles")

    # Colored summary table
    table_df = draft_df[["Grouped Customer", "SKU Name", "Jun", "RF10", "Actual + Forecast", "Forecast Gap"]].copy()
    gap_values = table_df["Forecast Gap"].tolist()
    gap_colors = ["green" if v > 0 else "red" if v < 0 else "black" for v in gap_values]

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=list(table_df.columns),
            fill_color='#003049',
            align='left',
            font=dict(color='white', size=18)
        ),
        cells=dict(
            values=[table_df[col] for col in table_df.columns],
            fill_color=[['#f6f6f6', '#ffffff'] * (len(table_df) // 2 + 1)][:len(table_df)],
            align='left',
            font=dict(size=18),
            font_color=["black", "black", "black", "black", "black", gap_colors],
            height=34,
            line_color='lightgrey'
        )
    )])
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ----------- SUBMIT FORM & FEEDBACK -----------
with st.form("forecast_form"):
    submitted = st.form_submit_button("✅ Submit Forecast")
    if submitted:
        if not "stored_forecast" in st.session_state:
            st.error("Please store a draft before submitting.")
        elif not invalid_rows.empty:
            st.error("Please correct negative June values before submitting.")
        else:
            # Here: Save to DB or send to API, as needed!
            st.session_state["audit_log"] = st.session_state.get("audit_log", []) + [
                {
                    "user": st.session_state.get("user", "Unknown"),
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "action": "Submit Forecast",
                    "row_count": len(st.session_state["stored_forecast"])
                }
            ]
            st.success("Forecast submitted successfully! ✅")
            # Optionally: lock editor or refresh state

# ----------- AUDIT LOG (simple) -----------
if "audit_log" in st.session_state and st.sidebar.checkbox("Show Audit Log", False):
    audit_df = pd.DataFrame(st.session_state["audit_log"])
    st.sidebar.dataframe(audit_df)
