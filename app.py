
import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io
import re
from datetime import datetime

# Configure page
st.set_page_config(page_title="🧾 Grocery Receipt Scanner – Discount Grouping", layout="wide")
API_URL = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"
HEADERS = {"Authorization": f"Token {st.secrets['MINDEE_API_KEY']}"}

st.title("📸 Grocery Receipt Scanner – Discount Grouping")
st.markdown("Upload receipt images. The app will group full-price, quantity, and discount lines into single items.")

# File uploader
uploaded_files = st.file_uploader(
    "Upload receipt images",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

# Function to call Mindee OCR
@st.cache_data(show_spinner=False)
def fetch_receipt_data(image_bytes: bytes) -> dict:
    response = requests.post(API_URL, files={"document": image_bytes}, headers=HEADERS)
    response.raise_for_status()
    return response.json()

# Process each uploaded file
all_results = []
grand_total = 0.0

if uploaded_files:
    for file in uploaded_files:
        st.header(f"Processing: {file.name}")
        # Read and send to Mindee
        img = Image.open(file).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        data = fetch_receipt_data(buf.getvalue())

        # Date override
        mindee_date = data.get("document", {}).get("inference", {}).get("prediction", {}).get("date", {}).get("value", "")
        try:
            default_date = datetime.fromisoformat(mindee_date).date() if mindee_date else datetime.today().date()
        except:
            default_date = datetime.today().date()
        receipt_date = st.date_input(
            f"Confirm date for {file.name}",
            value=default_date,
            key=f"date-{file.name}"
        )

        # Extract raw items
        page = data.get("document", {}).get("inference", {}).get("pages", [{}])[0]
        raw_items = page.get("prediction", {}).get("line_items", [])

        # Group items
        i = 0
        receipt_sum = 0.0
        while i < len(raw_items):
            item = raw_items[i]
            desc = item.get("description", "").strip()
            price_full = item.get("total_amount") or 0.0

            # Check for discount pattern: next two lines
            if (
                i + 2 < len(raw_items)
                and re.match(r"^\d+\s*@\s*[0-9.]+$", raw_items[i+1].get("description", "").strip())
                and raw_items[i+2].get("description", "").strip().upper().startswith(desc.upper())
            ):
                # Parse quantity and discount
                qty_line = raw_items[i+1].get("description", "").strip()
                qty = int(qty_line.split("@")[0].strip())
                discount_amt = abs(raw_items[i+2].get("total_amount") or 0.0)
                net_total = price_full - discount_amt

                all_results.append({
                    "source_file": file.name,
                    "receipt_date": receipt_date.isoformat(),
                    "description": desc,
                    "quantity": qty,
                    "unit_price": price_full,
                    "total_amount": round(net_total, 2),
                    "original_discount": discount_amt
                })
                receipt_sum += net_total
                i += 3
            else:
                # Regular item, no discount grouping
                qty = item.get("quantity") or 1
                all_results.append({
                    "source_file": file.name,
                    "receipt_date": receipt_date.isoformat(),
                    "description": desc,
                    "quantity": qty,
                    "unit_price": item.get("unit_price"),
                    "total_amount": round(price_full, 2),
                    "original_discount": None
                })
                receipt_sum += price_full
                i += 1

        # Display receipt total from OCR
        ocr_total = data.get("document", {}).get("inference", {}).get("prediction", {}).get("total_amount", {}).get("value")
        if ocr_total:
            st.write(f"**Receipt total (OCR):** ${ocr_total:.2f}")
        st.write(f"**Sum of grouped items:** ${receipt_sum:.2f}")
        if ocr_total and abs(receipt_sum - float(ocr_total)) > 0.01:
            st.warning("⚠️ Sum of grouped items does not match OCR receipt total.")

        grand_total += receipt_sum

    # Show grand total
    st.sidebar.header("Grand Total")
    st.sidebar.write(f"**${grand_total:.2f}**")

    # Display combined table and CSV download
    df = pd.DataFrame(all_results)
    st.subheader("All Line Items (Grouped)")
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "grocery_data_grouped.csv", "text/csv")
