
import streamlit as st
import requests
import base64
import json

st.set_page_config(page_title="Grocery Receipt Scanner", layout="wide")
st.title("📸 Grocery Receipt Scanner with Multi-Photo Support")

st.markdown("Upload one or more receipt images (photo or scan). We'll extract the line items and show them in a table.")

uploaded_files = st.file_uploader("Upload receipt images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

api_key = st.secrets["MINDEE_API_KEY"]
headers = {"Authorization": f"Token {api_key}"}
endpoint = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"

all_line_items = []

if uploaded_files:
    for file in uploaded_files:
        st.markdown(f"### Processing: `{file.name}`")
        files = {"document": (file.name, file, "image/jpeg")}

        response = requests.post(endpoint, files=files, headers=headers)

        if response.status_code == 201:
            data = response.json()
            try:
                items = data["document"]["inference"]["prediction"]["line_items"]
                for item in items:
                    line = {
                        "description": item.get("description", ""),
                        "quantity": item.get("quantity", ""),
                        "total_amount": item.get("total_amount", ""),
                        "unit_price": item.get("unit_price", ""),
                        "source_file": file.name
                    }
                    all_line_items.append(line)
            except Exception as e:
                st.error(f"Failed to extract line items from {file.name}: {e}")
        else:
            st.error(f"Failed to process {file.name}. Status code: {response.status_code}")

    if all_line_items:
        st.success("✅ All receipts processed. Here's what we found:")
        df = st.data_editor(all_line_items, num_rows="dynamic", use_container_width=True)
    else:
        st.warning("No line items extracted from uploaded receipts.")
