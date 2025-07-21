
import streamlit as st
import requests
import pandas as pd
from PIL import Image
import io
import re
from collections import defaultdict

# Configure page and cache
st.set_page_config(page_title="🧾 Grocery Receipt Scanner", layout="wide")

# Constants
API_URL = "https://api.mindee.net/v1/products/mindee/expense_receipts/v5/predict"
HEADERS = {"Authorization": f"Token {st.secrets['MINDEE_API_KEY']}"}

@st.cache_data(show_spinner=False)
def fetch_receipt_data(image_bytes: bytes) -> dict:
    """Call Mindee API and return JSON response."""
    response = requests.post(API_URL, files={"document": image_bytes}, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def extract_receipt_fields(data: dict) -> tuple:
    """Extract date and total from document-level prediction with fallback."""
    doc_pred = data.get("document", {}).get("inference", {}).get("prediction", {})
    # Try direct date
    date = doc_pred.get("date", {}).get("value")
    if not date:
        # Fallback: search pages
        for page in data.get("document", {}).get("inference", {}).get("pages", []):
            val = page.get("prediction", {}).get("date", {}).get("value")
            if val:
                date = val
                break
    date = date or "N/A"
    total = doc_pred.get("total_amount", {}).get("value") or doc_pred.get("total_incl", {}).get("value")
    return date, total

def parse_items(data: dict) -> list:
    """Parse line items, merge duplicates, handle discounts and weight pricing."""
    page = data.get("document", {}).get("inference", {}).get("pages", [{}])[0]
    items = page.get("prediction", {}).get("line_items", [])
    merged = defaultdict(lambda: {"quantity": 0, "unit_price": None, "total_amount": 0.0,
                                  "original_discount": 0.0, "price_per_pound": None, "pounds": None})
    for item in items:
        desc = item.get("description", "").strip()
        amt = item.get("total_amount") or 0.0
        # Detect discount lines: negative or trailing dash
        if isinstance(amt, float) and amt < 0 or re.search(r"\-\s*$", desc):
            # Map discount
            # Use stripped desc
            key = desc.lstrip("- ").upper()
            merged[key]["original_discount"] += amt
            continue
        # Detect weight pricing: pattern '@ XX.XX /lb'
        match = re.search(r"@\s*([0-9.]+)\s*/lb", desc)
        if match:
            price_lb = float(match.group(1))
            # Compute pounds
            pounds = amt / price_lb if price_lb else None
            key = desc.split("@")[0].strip().upper()
            merged[key]["price_per_pound"] = price_lb
            merged[key]["pounds"] = round(pounds,2) if pounds else None
        else:
            key = desc.upper()
        merged[key]["quantity"] += item.get("quantity") or 1
        merged[key]["total_amount"] += amt
        merged[key]["unit_price"] = item.get("unit_price") or merged[key]["unit_price"]
    # Build list
    results = []
    for desc, vals in merged.items():
        results.append({
            "description": desc,
            "quantity": vals["quantity"],
            "unit_price": vals["unit_price"],
            "total_amount": round(vals["total_amount"],2),
            "original_discount": round(vals["original_discount"],2) if vals["original_discount"] else None,
            "price_per_pound": vals["price_per_pound"],
            "pounds": vals["pounds"]
        })
    return results

# UI Layout: uploader and summary
col1, col2 = st.columns([2,1])
with col1:
    uploaded = st.file_uploader("Upload receipt images", accept_multiple_files=True,
                                type=["jpg","jpeg","png"])
with col2:
    st.markdown("**Total Spend**")
    st.empty()  # will update later

all_data = []
grand_total = 0.0

if uploaded:
    for file in uploaded:
        st.markdown(f"### Processing: `{file.name}`")
        img = Image.open(file).convert("RGB")
        buf = io.BytesIO(); img.save(buf, format="JPEG")
        data = fetch_receipt_data(buf.getvalue())
        date, receipt_total = extract_receipt_fields(data)
        items = parse_items(data)
        # add metadata
        for it in items:
            it["receipt_date"] = date
            it["source_file"] = file.name
            all_data.append(it)
        grand_total += receipt_total or 0.0
        # Table per receipt
        df_r = pd.DataFrame(items)
        st.dataframe(df_r)
        if receipt_total:
            st.markdown(f"**Receipt Total:** ${receipt_total:.2f}")
        # Mismatch warning
        sum_items = df_r["total_amount"].sum()
        if receipt_total and abs(sum_items - receipt_total) > 0.01:
            st.warning(f"Sum of items (${sum_items:.2f}) != Receipt total (${receipt_total:.2f})")

    # Display grand total
    col2.write(f"**${grand_total:.2f}**")

    # Combined data and download
    combined = pd.DataFrame(all_data)
    st.markdown("---")
    st.subheader("All Items Across Receipts")
    st.dataframe(combined)
    csv = combined.to_csv(index=False).encode()
    st.download_button("Download CSV", csv, "grocery_data.csv", "text/csv")
