import streamlit as st
import pandas as pd
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
    .stSelectbox>div>div {
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)

# ----------- TITLE -----------

st.title("📊 Sales Forecast Input Tool")

st.markdown("Upload your forecast Excel file, select your name, apply filters, and edit your June forecast in a clean, easy-to-use interface.")

# ----------- CACHED FUNCTIONS -----------

@st.cache_data
def load_excel(file):
    return pd.read_excel(file, engine="openpyxl")

@st.cache_data
def get_unique_options(df, column):
    return sorted(df[column].dropna().unique())

# ----------- MAIN APP -----------

uploaded_file = st.file_uploader("📁 Upload your Excel forecast file", type=["xlsx"])

if uploaded_file:
    with st.spinner("Loading forecast data..."):
        df = load_excel(uploaded_file)

    st.markdown("---")

    # ----------- FILTERS SECTION -----------
    st.header("🧭 Filter Your Data")

    rep_name = st.selectbox(
        "Select your name (Grouped Customer Owner)", 
        get_unique_options(df, "Grouped Customer Owner")
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        customer = st.selectbox("Grouped Customer", ["All"] + get_unique_options(df, "Grouped Customer"))
    with col2:
        coverage = st.selectbox("Coverage", ["All"] + get_unique_options(df, "Coverage"))
    with col3:
        sku = st.selectbox("SKU", ["All"] + get_unique_options(df, "SKU"))

    mask = df["Grouped Customer Owner"] == rep_name
    if customer != "All":
        mask &= df["Grouped Customer"] == customer
    if coverage != "All":
        mask &= df["Coverage"] == coverage
    if sku != "All":
        mask &= df["SKU"] == sku

    df_filtered = df[mask]

    st.markdown("---")

    # ----------- EDITABLE SECTION -----------
    st.header("📝 Edit Forecast")

    with st.form("forecast_form"):
        editable_df = st.data_editor(
            df_filtered[["Grouped Customer", "Coverage", "SKU", "Jun"]],
            num_rows="dynamic",
            use_container_width=True,
            key="editable_forecast"
        )
        submitted = st.form_submit_button("✅ Submit Forecast")

    # ----------- SUBMISSION LOGIC -----------
    if submitted:
        st.success("Forecast submitted!")

        updated_df = df.copy()
        for _, row in editable_df.iterrows():
            mask = (
                (updated_df["Grouped Customer Owner"] == rep_name) &
                (updated_df["Grouped Customer"] == row["Grouped Customer"]) &
                (updated_df["Coverage"] == row["Coverage"]) &
                (updated_df["SKU"] == row["SKU"])
            )
            updated_df.loc[mask, "Jun"] = row["Jun"]

        buffer = BytesIO()
        updated_df.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)

        st.download_button(
            label="📥 Download Updated Forecast File",
            data=buffer,
            file_name="updated_forecast.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
