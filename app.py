import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Grocery Receipt Scanner", layout="wide")
st.title("🧾 Grocery Receipt Scanner")
st.write("Upload a grocery receipt image or PDF to extract items and categorize them.")

uploaded_file = st.file_uploader("Upload Receipt", type=["jpg", "jpeg", "png", "pdf"])

if uploaded_file:
    with st.spinner("Processing receipt..."):
        files = {"document": (uploaded_file.name, uploaded_file, uploaded_file.type)}
        headers = {"Authorization": f"Token {st.secrets['MINDEE_API_KEY']}"}
        response = requests.post("https://api.mindee.net/v1/products/mindee/receipt/v4/predict", files=files, headers=headers)

        if response.status_code == 200:
            data = response.json()
            items = data.get("document", {}).get("inference", {}).get("prediction", {}).get("line_items", [])
            rows = []
            for item in items:
                desc = item.get("description", {}).get("value", "Unknown")
                amt = item.get("total_amount", {}).get("value", 0.0)
                rows.append({"Item": desc, "Amount": amt})

            df = pd.DataFrame(rows)
            df["Category"] = df["Item"].apply(lambda x: "Produce" if "apple" in x.lower() or "banana" in x.lower() else "Uncategorized")

            st.write("### Receipt Items")
            edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            st.write("### Total by Category")
            st.dataframe(edited_df.groupby("Category")["Amount"].sum().reset_index())

            csv = edited_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "categorized_receipt.csv", "text/csv")
        else:
            st.error("Failed to process receipt. Please try again.")
