import streamlit as st
import pandas as pd
from databricks import sql
from io import BytesIO
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="Sales Forecast Tool", layout="wide")

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

# ----------- REP FORECAST VIEW -----------
if view == "🖍️ Rep Forecast Input":
    st.title("🖍️ Edit June Forecast")

    rep_options = ["All"] + get_unique_options(df, "Grouped Customer Owner")
    rep_name = st.selectbox("Select your name (Grouped Customer Owner)", rep_options)

    df_rep = df if rep_name == "All" else df[df["Grouped Customer Owner"] == rep_name]

    col1, col2 = st.columns(2)
    with col1:
        customer = st.selectbox("Grouped Customer", ["All"] + get_unique_options(df_rep, "Grouped Customer"))
    with col2:
        sku_name = st.selectbox("SKU Name", ["All"] + get_unique_options(df_rep, "SKU Name"))

    optional_columns = [
        "A24 Total", "A24 Total_9L", "A24 Total_Value",
        "Contract_Vol_Q1", "Contract_Vol_Q2", "Contract_Vol_Q3", "Contract_Vol_Q4",
        "Contract_Vol_Q1_9L", "Contract_Vol_Q2_9L", "Contract_Vol_Q3_9L", "Contract_Vol_Q4_9L",
        "Contract_Vol_9L", "Contract_Value_Q1", "Contract_Value_Q2", "Contract_Value_Q3", "Contract_Value_Q4",
        "RF10_9L", "RF10_Value"
    ]
    selected_optional_columns = st.multiselect("📊 Select Additional Columns to Display", optional_columns)

    mask = pd.Series([True] * len(df))
    if rep_name != "All":
        mask &= df["Grouped Customer Owner"] == rep_name
    if customer != "All":
        mask &= df["Grouped Customer"] == customer
    if sku_name != "All":
        mask &= df["SKU Name"] == sku_name

    df_filtered = df[mask]
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
            "Jun": st.column_config.NumberColumn(label="✏️ June Forecast (Editable)", format="%d")
        },
        use_container_width=True,
        key="editor_june"
    )

    if st.button("🗂️ Store Draft (Calculate Totals)"):
        st.session_state["stored_forecast"] = edited_df.copy()
        if "submission_registry" not in st.session_state:
            st.session_state["submission_registry"] = {}
        st.session_state["submission_registry"][rep_name] = {
            "data": edited_df.copy(),
            "timestamp": datetime.now()
        }

    if "stored_forecast" in st.session_state:
        draft_df = st.session_state["stored_forecast"].copy()
        draft_df["Progress"] = df_filtered[monthly_cols].sum(axis=1).astype(int)
        draft_df["Actual + Forecast"] = (draft_df["Progress"] + draft_df["Jun"]).astype(int)
        draft_df["Forecast Gap"] = (draft_df["Actual + Forecast"] - draft_df["RF10"]).astype(int)

        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total RF10", f"{draft_df['RF10'].sum():,} bottles")
        kpi2.metric("Actual + Forecast", f"{draft_df['Actual + Forecast'].sum():,} bottles")
        kpi3.metric("June Forecast", f"{draft_df['Jun'].sum():,} bottles")

        csv = draft_df.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download Forecast as CSV", csv, "june_forecast.csv", "text/csv")

    with st.form("forecast_form"):
        submitted = st.form_submit_button("✅ Submit Forecast")
        if submitted:
            if "stored_forecast" not in st.session_state:
                st.error("⚠️ Please click 'Store Draft' before submitting your forecast.")
            elif (st.session_state["stored_forecast"]["Jun"] < 0).any():
                st.error("🚫 June forecast cannot contain negative values.")
            else:
                st.success("✅ Forecast submitted successfully!")

# ----------- SALES MANAGER VIEW -----------
elif view == "📊 Sales Manager View":
    st.title("📊 Sales Manager Overview")

    submission_data = st.session_state.get("submission_registry", {})
    if not submission_data:
        st.info("No forecasts have been submitted yet.")
    else:
        all_submitted = [data["data"] for data in submission_data.values()]
        df_all = pd.concat(all_submitted)
        df_all["Forecast Gap"] = df_all["Progress"] + df_all["Jun"] - df_all["RF10"]

        # KPIs
        total_rf10 = df_all["RF10"].sum()
        total_june = df_all["Jun"].sum()
        total_reps = df["Grouped Customer Owner"].nunique()
        reps_submitted = len(submission_data)

        k1, k2, k3 = st.columns(3)
        k1.metric("Total RF10", f"{total_rf10:,} bottles")
        k2.metric("Total June Forecast", f"{total_june:,} bottles")
        k3.metric("Submission Rate", f"{(reps_submitted/total_reps)*100:.0f}%")

        # Submission tracker
        st.subheader("🧾 Submission Tracker")
        sub_df = pd.DataFrame([
            {
                "Rep": rep,
                "Rows Submitted": len(data["data"]),
                "Last Submission": data["timestamp"].strftime("%Y-%m-%d %H:%M")
            } for rep, data in submission_data.items()
        ])
        st.dataframe(sub_df, use_container_width=True)

        # Drilldown
        st.subheader("🔍 Customer-Level Drilldown")
        reps = ["All"] + list(submission_data.keys())
        selected_rep = st.selectbox("Filter by Rep", reps)

        df_drill = df_all if selected_rep == "All" else submission_data[selected_rep]["data"]

        customer_options = ["All"] + df_drill["Grouped Customer"].unique().tolist()
        selected_cust = st.selectbox("Filter by Customer", customer_options)

        if selected_cust != "All":
            df_drill = df_drill[df_drill["Grouped Customer"] == selected_cust]

        st.dataframe(df_drill[["Grouped Customer", "SKU Name", "Jun", "RF10", "Progress", "Forecast Gap"]], use_container_width=True)

        # Charts
        st.subheader("📈 Charts")
        chart_df = df_all.groupby("Grouped Customer Owner")[["RF10", "Jun"]].sum().reset_index()
        fig = px.bar(chart_df, x="Grouped Customer Owner", y=["RF10", "Jun"], barmode="group", title="Forecast vs RF10 by Rep")
        st.plotly_chart(fig, use_container_width=True)

        gap_df = df_all.groupby("Grouped Customer Owner")["Forecast Gap"].sum().reset_index()
        fig2 = px.bar(gap_df, x="Grouped Customer Owner", y="Forecast Gap", color="Forecast Gap", title="Total Forecast Gap by Rep")
        st.plotly_chart(fig2, use_container_width=True)
