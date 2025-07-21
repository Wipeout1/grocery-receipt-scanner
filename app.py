
import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io
from datetime import datetime

# Config
st.set_page_config(page_title="🧾 Grocery Receipt Scanner", layout="wide")
API_URL = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"
HEADERS = {"Authorization": f"Token {st.secrets['MINDEE_API_KEY']}"}

st.title("📸 Grocery Receipt Scanner")
st.markdown("Upload receipt images. We'll extract line items, and ask you to confirm the receipt date.")

uploaded_files = st.file_uploader("Upload receipt images", type=["jpg","jpeg","png"], accept_multiple_files=True)

all_results = []
grand_total = 0.0

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.header(f"Processing: {uploaded_file.name}")
        # Read image bytes
        image = Image.open(uploaded_file).convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        # Call Mindee API
        response = requests.post(API_URL, files={"document": buf.getvalue()}, headers=HEADERS)
        if response.status_code != 201:
            st.error(f"Failed to call API for {uploaded_file.name}: {response.status_code}")
            continue
        data = response.json()
        # Extract Mindee date
        mindee_date = data.get("document", {}).get("inference", {}).get("prediction", {}).get("date", {}).get("value")
        # Parse to date object or default to today
        try:
            default_date = datetime.fromisoformat(mindee_date).date() if mindee_date else datetime.today().date()
        except:
            default_date = datetime.today().date()
        # Ask user to confirm or override
        actual_date = st.date_input(f"Select date for {uploaded_file.name}", value=default_date, key=f"date-{uploaded_file.name}")
        # Extract items
        page = data.get("document", {}).get("inference", {}).get("pages", [{}])[0]
        items = page.get("prediction", {}).get("line_items", [])
        receipt_total = data.get("document", {}).get("inference", {}).get("prediction", {}).get("total_amount", {}).get("value")
        # Build rows
        total_spent = 0.0
        for item in items:
            amt = item.get("total_amount") or 0.0
            total_spent += amt
            all_results.append({
                "source_file": uploaded_file.name,
                "receipt_date": actual_date.isoformat(),
                "description": item.get("description",""),
                "quantity": item.get("quantity"),
                "unit_price": item.get("unit_price"),
                "total_amount": amt
            })
        # Show receipt summary
        st.write(f"Items extracted: **{len(items)}**, Sum items = **${total_spent:.2f}**")
        if receipt_total:
            st.write(f"Total on receipt: **${receipt_total:.2f}**")
            if abs(total_spent - float(receipt_total)) > 0.01:
                st.warning("Sum of items does not match receipt total!")
        grand_total += total_spent
    # Display grand total
    st.sidebar.header("Grand Total")
    st.sidebar.write(f"**${grand_total:.2f}**")
    # Show combined data
    df = pd.DataFrame(all_results)
    st.subheader("All Line Items")
    st.dataframe(df)
