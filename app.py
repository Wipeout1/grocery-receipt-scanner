
import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io
import re
from datetime import datetime

# Config
st.set_page_config(page_title="🧾 Grocery Receipt Scanner", layout="wide")
API_URL = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"
HEADERS = {"Authorization": f"Token {st.secrets['MINDEE_API_KEY']}"}

st.title("📸 Grocery Receipt Scanner – Improved Line Splitting")
st.markdown("Upload receipt images. Trailing quantities/prices are trimmed, and discounts normalized.")

uploaded_files = st.file_uploader("Upload receipt images", type=["jpg","jpeg","png"], accept_multiple_files=True)

all_results = []
grand_total = 0.0

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.header(f"Processing: {uploaded_file.name}")
        # Read image
        image = Image.open(uploaded_file).convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        # Call API
        response = requests.post(API_URL, files={"document": buf.getvalue()}, headers=HEADERS)
        if response.status_code != 201:
            st.error(f"API error {response.status_code}")
            continue
        data = response.json()
        # Extract date
        mindee_date = data.get("document", {}).get("inference", {}).get("prediction", {}).get("date", {}).get("value", "")
        try:
            default_date = datetime.fromisoformat(mindee_date).date() if mindee_date else datetime.today().date()
        except:
            default_date = datetime.today().date()
        receipt_date = st.date_input(f"Confirm date for {uploaded_file.name}", value=default_date, key=f"date-{uploaded_file.name}")
        # Extract items
        page = data.get("document", {}).get("inference", {}).get("pages", [{}])[0]
        items = page.get("prediction", {}).get("line_items", [])
        total_spent = 0.0
        for item in items:
            raw_desc = item.get("description", "").strip()
            # Trim trailing quantity pattern "1 Q 2.50" etc.
            desc = re.sub(r"\s+\d+\s*Q.*$", "", raw_desc)
            # Trim trailing price or discount pattern "2.50-" or "3.49"
            desc = re.sub(r"\s+\d+(?:\.\d+)?-?$", "", desc)
            # Normalize discount lines (string with dash as negative)
            amt = item.get("total_amount") or 0.0
            if isinstance(amt, str) and amt.endswith("-"):
                try:
                    amt = -abs(float(amt.replace("-", "")))
                except:
                    amt = 0.0
            total_spent += amt
            all_results.append({
                "source_file": uploaded_file.name,
                "receipt_date": receipt_date.isoformat(),
                "description": desc,
                "quantity": item.get("quantity"),
                "unit_price": item.get("unit_price"),
                "total_amount": amt
            })
        st.write(f"Items extracted: {len(items)} — Sum = ${total_spent:.2f}")
        grand_total += total_spent
    st.sidebar.header("Grand Total")
    st.sidebar.write(f"**${grand_total:.2f}**")
    df = pd.DataFrame(all_results)
    st.subheader("All Line Items")
    st.dataframe(df)
