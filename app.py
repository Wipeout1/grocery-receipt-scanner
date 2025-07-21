
import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io
import re
from datetime import datetime

# Configure page
st.set_page_config(page_title="🧾 Grocery Receipt Scanner – Enhanced Logic", layout="wide")
API_URL = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"
HEADERS = {"Authorization": f"Token {st.secrets['MINDEE_API_KEY']}"}

st.title("📸 Grocery Receipt Scanner – Enhanced Logic")
st.markdown(
    "- Groups full-price, quantity, and discount lines intelligently\n"
    "- Parses weight-based items (price per lb, pounds)\n"
    "- Allows date override per receipt"
)

# Uploader
uploaded_files = st.file_uploader("Upload receipt images", accept_multiple_files=True, type=["jpg","jpeg","png"])

@st.cache_data(show_spinner=False)
def fetch_ocr(data_bytes):
    response = requests.post(API_URL, files={"document": data_bytes}, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def parse_receipt(raw_items):
    """Parse raw line_items list into consolidated entries."""
    entries = []
    i = 0
    while i < len(raw_items):
        item = raw_items[i]
        desc = item.get("description","").strip()
        amt = item.get("total_amount") or 0.0

        # Discount grouping
        if i+2 < len(raw_items):
            qty_line = raw_items[i+1].get("description","").strip()
            disc_item = raw_items[i+2]
            if re.match(r"^\d+\s*@\s*[0-9.]+$", qty_line):
                discount_amt = disc_item.get("total_amount") or 0.0
                disc_desc = disc_item.get("description","").strip().upper()
                if discount_amt < 0 or disc_desc.startswith(desc.upper()):
                    # Combine lines
                    qty = int(qty_line.split("@")[0].strip())
                    discount_amt = abs(discount_amt)
                    net_total = amt - discount_amt
                    unit_price = amt if qty <= 1 else amt/qty
                    entries.append({
                        "description": desc,
                        "quantity": qty,
                        "unit_price": round(unit_price,2),
                        "total_amount": round(net_total,2),
                        "original_discount": round(discount_amt,2),
                        "price_per_pound": None,
                        "pounds": None
                    })
                    i += 3
                    continue

        # Weight-based pricing
        match = re.search(r"@\s*([0-9.]+)\s*/\s*lb", desc, re.IGNORECASE)
        if match and amt > 0:
            price_lb = float(match.group(1))
            pounds = round(amt / price_lb,2) if price_lb else None
            clean_desc = re.sub(r"@.*", "", desc).strip()
            entries.append({
                "description": clean_desc,
                "quantity": None,
                "unit_price": None,
                "total_amount": round(amt,2),
                "original_discount": None,
                "price_per_pound": price_lb,
                "pounds": pounds
            })
            i += 1
            continue

        # Regular item
        entries.append({
            "description": desc,
            "quantity": item.get("quantity"),
            "unit_price": item.get("unit_price"),
            "total_amount": round(amt,2),
            "original_discount": None,
            "price_per_pound": None,
            "pounds": None
        })
        i += 1
    return entries

# Process uploads
all_rows = []
grand_total = 0.0
for file in uploaded_files or []:
    st.header(f"Receipt: {file.name}")
    img = Image.open(file).convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="JPEG")
    data = fetch_ocr(buf.getvalue())

    # Date override
    mindee_date = data.get("document",{}).get("inference",{}).get("prediction",{}).get("date",{}).get("value","")
    try:
        default_date = datetime.fromisoformat(mindee_date).date() if mindee_date else datetime.today().date()
    except:
        default_date = datetime.today().date()
    receipt_date = st.date_input("Date for "+file.name, value=default_date, key=file.name)

    raw_items = data.get("document",{}).get("inference",{}).get("pages",[{}])[0].get("prediction",{}).get("line_items",[])
    parsed = parse_receipt(raw_items)

    # Safely parse OCR total
    raw_total = data.get("document",{}).get("inference",{}).get("prediction",{}).get("total_amount",{}).get("value", None)
    try:
        ocr_total = float(raw_total)
    except (TypeError, ValueError):
        ocr_total = None

    subtotal = sum(r["total_amount"] for r in parsed)
    # Display totals
    if ocr_total is not None:
        st.write(f"OCR total: ${ocr_total:.2f} — Parsed subtotal: ${subtotal:.2f}")
        if abs(subtotal - ocr_total) > 0.01:
            st.warning("Parsed items do not sum to OCR total!")
    else:
        st.write(f"Parsed subtotal: ${subtotal:.2f}")
        st.info("⚠️ OCR total not found")

    grand_total += subtotal
    for r in parsed:
        r["source_file"] = file.name
        r["receipt_date"] = receipt_date.isoformat()
        all_rows.append(r)

# Display results
st.sidebar.subheader("Grand Total")
st.sidebar.write(f"${grand_total:.2f}")
df = pd.DataFrame(all_rows)
st.subheader("All Items")
st.dataframe(df)
st.download_button("Download CSV", df.to_csv(index=False).encode(), "receipts.csv", "text/csv")
