
import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io
import re
from datetime import datetime

# Config
st.set_page_config(page_title="🧾 Grocery Receipt Scanner – Enhanced Splitting v3", layout="wide")
API_URL = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"
HEADERS = {"Authorization": f"Token {st.secrets['MINDEE_API_KEY']}"}

st.title("📸 Grocery Receipt Scanner – Enhanced Line Splitting v3")
st.markdown("Upload receipt images. We'll skip pure discount lines and better split merged items.")

uploaded_files = st.file_uploader("Upload receipt images", type=['jpg','jpeg','png'], accept_multiple_files=True)
all_results = []
grand_total = 0.0

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.header(f"Processing: {uploaded_file.name}")
        # OCR
        image = Image.open(uploaded_file).convert('RGB')
        buf = io.BytesIO(); image.save(buf, format='JPEG')
        resp = requests.post(API_URL, files={'document': buf.getvalue()}, headers=HEADERS)
        if resp.status_code != 201:
            st.error(f"API error {resp.status_code}")
            continue
        data = resp.json()
        # Date override
        mindee_date = data.get('document', {}).get('inference', {}).get('prediction', {}).get('date', {}).get('value', '')
        try:
            default_date = datetime.fromisoformat(mindee_date).date() if mindee_date else datetime.today().date()
        except:
            default_date = datetime.today().date()
        receipt_date = st.date_input(f"Confirm date for {uploaded_file.name}", value=default_date, key=f"date-{uploaded_file.name}")
        # Extract items
        items = data.get('document', {}).get('inference', {}).get('pages', [{}])[0].get('prediction', {}).get('line_items', [])
        total_spent = 0.0
        for item in items:
            # Normalize amount, skip negatives
            amt = item.get('total_amount')
            if isinstance(amt, str) and amt.endswith('-'):
                try:
                    amt = -abs(float(amt.replace('-', '')))
                except:
                    amt = 0.0
            amt = amt or 0.0
            if amt < 0:
                continue  # skip pure discount lines

            raw_desc = item.get('description', '').strip()
            # Remove trailing quantity block
            desc = re.sub(r"\s+\d+\s*Q.*$", "", raw_desc)
            # Trim trailing price or discount dash
            desc = re.sub(r"\s+\d+(?:\.\d+)?-?$", "", desc)
            # Enhanced splitting
            words = desc.split()
            if len(words) > 2 and amt > 0:
                primary = ' '.join(words[:2])
                leftover = ' '.join(words[2:])
                entries = [(primary, amt), (leftover, 0.0)]
            else:
                entries = [(desc, amt)]

            for d, a in entries:
                total_spent += a
                all_results.append({
                    'source_file': uploaded_file.name,
                    'receipt_date': receipt_date.isoformat(),
                    'description': d,
                    'quantity': item.get('quantity'),
                    'unit_price': item.get('unit_price'),
                    'total_amount': round(a, 2)
                })
        st.write(f"Items: {len(all_results)} — Sum = ${total_spent:.2f}")
        grand_total += total_spent
    st.sidebar.header("Grand Total")
    st.sidebar.write(f"**${grand_total:.2f}**")
    df = pd.DataFrame(all_results)
    st.subheader("All Line Items")
    st.dataframe(df)
