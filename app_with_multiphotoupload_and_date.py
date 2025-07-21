
import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io

st.set_page_config(page_title="Grocery Receipt Scanner with Multi-Photo Support", layout="wide")

st.title("📸 Grocery Receipt Scanner with Multi-Photo Support")
st.markdown("Upload one or more receipt images (photo or scan). We'll extract the line items and show them in a table.")

uploaded_files = st.file_uploader("Upload receipt images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

headers = {
    "Authorization": "Token YOUR_MINDEE_API_KEY"
}
api_url = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"

all_results = []

if uploaded_files:
    with st.spinner("Processing receipt(s)..."):
        for uploaded_file in uploaded_files:
            st.markdown(f"**Processing:** `{uploaded_file.name}`", unsafe_allow_html=True)

            image = Image.open(uploaded_file).convert("RGB")
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")

            response = requests.post(
                api_url,
                files={"document": buffered.getvalue()},
                headers=headers
            )

            if response.status_code == 201:
                data = response.json()
                page = data.get("document", {}).get("inference", {}).get("pages", [{}])[0]
                prediction = page.get("prediction", {})
                line_items = prediction.get("line_items", [])
                receipt_date = data.get("document", {}).get("inference", {}).get("prediction", {}).get("date", {}).get("value", "N/A")

                for item in line_items:
                    all_results.append({
                        "description": item.get("description", ""),
                        "quantity": item.get("quantity"),
                        "total_amount": item.get("total_amount"),
                        "unit_price": item.get("unit_price"),
                        "source_file": uploaded_file.name,
                        "receipt_date": receipt_date
                    })
            else:
                st.error(f"Failed to process {uploaded_file.name} — status code {response.status_code}")

    if all_results:
        df = pd.DataFrame(all_results)
        st.success("✅ All receipts processed. Here's what we found:")
        st.dataframe(df)
