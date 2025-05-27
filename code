import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Sales Forecast Input Tool", layout="wide")
st.title("📈 Sales Forecast Input Tool")

# Step 1: Upload Excel file
uploaded_file = st.file_uploader("Upload your Excel forecast file", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Step 2: Filter by Grouped Customer Owner (Sales Rep)
    rep_name = st.selectbox("Select your name (Grouped Customer Owner)", df["Grouped Customer Owner"].dropna().unique())

    df_filtered = df[df["Grouped Customer Owner"] == rep_name]

    # Step 3: Additional Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        customer = st.selectbox("Grouped Customer", ["All"] + sorted(df_filtered["Grouped Customer"].dropna().unique()))
    with col2:
        coverage = st.selectbox("Coverage", ["All"] + sorted(df_filtered["Coverage"].dropna().unique()))
    with col3:
        sku = st.selectbox("SKU", ["All"] + sorted(df_filtered["SKU"].dropna().unique()))

    # Apply filters
    if customer != "All":
        df_filtered = df_filtered[df_filtered["Grouped Customer"] == customer]
    if coverage != "All":
        df_filtered = df_filtered[df_filtered["Coverage"] == coverage]
    if sku != "All":
        df_filtered = df_filtered[df_filtered["SKU"] == sku]

    # Step 4: Editable June forecast column
    st.subheader("✏️ Edit June Forecast")
    editable_df = st.data_editor(
        df_filtered[["Grouped Customer", "Coverage", "SKU", "Jun"]],
        num_rows="dynamic",
        use_container_width=True
    )

    # Step 5: Submit Forecast
    if st.button("✅ Submit Forecast"):
        st.success("Forecast submitted!")

        # Replace June values in original df with edited values
        updated_df = df.copy()
        for i, row in editable_df.iterrows():
            mask = (
                (updated_df["Grouped Customer Owner"] == rep_name) &
                (updated_df["Grouped Customer"] == row["Grouped Customer"]) &
                (updated_df["Coverage"] == row["Coverage"]) &
                (updated_df["SKU"] == row["SKU"])
            )
            updated_df.loc[mask, "Jun"] = row["Jun"]

        # Step 6: Provide download link
        buffer = BytesIO()
        updated_df.to_excel(buffer, index=False)
        buffer.seek(0)

        st.download_button(
            label="📥 Download Updated Forecast File",
            data=buffer,
            file_name="updated_forecast.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
