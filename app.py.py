
import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io

# Constants
MINDEE_EXPENSE_RECEIPTS_API = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"

st.set_page_config(page_title="🧾 Grocery Receipt Scanner", layout="wide")

st.title("🧾 Grocery Receipt Scanner")
st.markdown("Upload one or more receipt images (photo or scan). We'll extract the line items and show them in a table.")

uploaded_files = st.file_uploader("Upload receipt images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

headers = {
    "Authorization": f"Token {st.secrets['MINDEE_API_KEY']}"
}

all_results = []

if uploaded_files:
    with st.spinner("Processing receipt(s)..."):
        for uploaded_file in uploaded_files:
            st.markdown(f"**Processing:** `{uploaded_file.name}`", unsafe_allow_html=True)

            image = Image.open(uploaded_file).convert("RGB")
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG")

            response = requests.post(
                MINDEE_EXPENSE_RECEIPTS_API,
                files={"document": buffered.getvalue()},
                headers=headers
            )

            if response.status_code == 201:
                data = response.json()
                document = data.get("document", {}).get("inference", {}).get("prediction", {})
                page = data.get("document", {}).get("inference", {}).get("pages", [{}])[0]
                prediction = page.get("prediction", {})
                line_items = prediction.get("line_items", [])
                receipt_date = document.get("date", {}).get("value", "N/A")
                total_amount = document.get("total_amount", {}).get("value")

                for item in line_items:
                    all_results.append({
                        "description": item.get("description", ""),
                        "quantity": item.get("quantity"),
                        "total_amount": item.get("total_amount"),
                        "unit_price": item.get("unit_price"),
                        "receipt_date": receipt_date,
                        "source_file": uploaded_file.name,
                        "original_discount": None,  # placeholder for future use
                        "price_per_pound": None,    # placeholder for future use
                        "pounds": None              # placeholder for future use
                    })

                # Add summary row
                if total_amount:
                    all_results.append({
                        "description": "🧾 TOTAL",
                        "quantity": "",
                        "total_amount": float(total_amount),
                        "unit_price": "",
                        "receipt_date": receipt_date,
                        "source_file": uploaded_file.name,
                        "original_discount": "",
                        "price_per_pound": "",
                        "pounds": ""
                    })
            else:
                st.error(f"Failed to process {uploaded_file.name} — status code {response.status_code}")

    if all_results:
        df = pd.DataFrame(all_results)
        st.success("✅ All receipts processed. Here's what we found:")
        st.dataframe(df)
