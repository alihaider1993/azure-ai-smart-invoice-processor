import os
import pandas as pd
import streamlit as st
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Invoice History", layout="wide")
st.title("Invoice History")

@st.cache_data(ttl=60)
def load_invoices():
    client = CosmosClient(url=os.getenv("COSMOS_ENDPOINT"), credential=DefaultAzureCredential())
    database = client.get_database_client("invoice-db")
    container = database.get_container_client("processed-invoices")
    return list(container.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))

items = load_invoices()
if not items:
    st.warning("No invoice history found.")
    st.stop()

df = pd.DataFrame(items)
if "gbp_amount" not in df.columns: df["gbp_amount"] = df["total_amount"]
df["gbp_amount"] = pd.to_numeric(df["gbp_amount"], errors="coerce").fillna(0)
df["fraud_score"] = pd.to_numeric(df["fraud_score"], errors="coerce").fillna(0)

st.sidebar.header("Filters")
vendors = ["All"] + sorted(df["vendor_name"].dropna().unique().tolist())
categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
risks = ["All"] + sorted(df["risk_level"].dropna().unique().tolist())
selected_vendor = st.sidebar.selectbox("Vendor", vendors)
selected_category = st.sidebar.selectbox("Category", categories)
selected_risk = st.sidebar.selectbox("Risk Level", risks)
search_text = st.sidebar.text_input("Search invoice number or vendor")
filtered_df = df.copy()
if selected_vendor != "All": filtered_df = filtered_df[filtered_df["vendor_name"] == selected_vendor]
if selected_category != "All": filtered_df = filtered_df[filtered_df["category"] == selected_category]
if selected_risk != "All": filtered_df = filtered_df[filtered_df["risk_level"] == selected_risk]
if search_text:
    search_text = search_text.lower()
    filtered_df = filtered_df[filtered_df["vendor_name"].astype(str).str.lower().str.contains(search_text) | filtered_df["invoice_number"].astype(str).str.lower().str.contains(search_text)]

st.subheader("Invoice Records")
columns = ["vendor_name", "invoice_number", "invoice_date", "currency", "total_amount", "gbp_amount", "category", "risk_level", "fraud_score", "approval_status", "processed_at"]
existing_columns = [col for col in columns if col in filtered_df.columns]
st.dataframe(filtered_df[existing_columns], use_container_width=True)
st.subheader("Selected Invoice Details")
if not filtered_df.empty:
    selected_index = st.selectbox("Select invoice row", filtered_df.index.tolist())
    selected_invoice = filtered_df.loc[selected_index].to_dict()
    st.json(selected_invoice.get("full_result", selected_invoice))
else:
    st.info("No records match the selected filters.")
st.download_button("Download Filtered History CSV", filtered_df.to_csv(index=False), "invoice_history.csv", "text/csv")
