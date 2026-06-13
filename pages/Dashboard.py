import os
import pandas as pd
import plotly.express as px
import streamlit as st
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="Invoice Dashboard", layout="wide")
st.title("Enhanced Invoice Analytics Dashboard")

@st.cache_data(ttl=60)
def load_processed_invoices():
    client = CosmosClient(url=os.getenv("COSMOS_ENDPOINT"), credential=DefaultAzureCredential())
    database = client.get_database_client("invoice-db")
    container = database.get_container_client("processed-invoices")
    return list(container.query_items(query="SELECT * FROM c", enable_cross_partition_query=True))

items = load_processed_invoices()
if not items:
    st.warning("No processed invoices found yet.")
    st.stop()

df = pd.DataFrame(items)
df["gbp_amount"] = pd.to_numeric(df.get("gbp_amount", df.get("total_amount", 0)), errors="coerce").fillna(0)
df["fraud_score"] = pd.to_numeric(df.get("fraud_score", 0), errors="coerce").fillna(0)
df["processed_at"] = pd.to_datetime(df["processed_at"], errors="coerce")
df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
df["month"] = df["processed_at"].dt.to_period("M").astype(str)

def is_duplicate(row):
    full_result = row.get("full_result", {})
    if isinstance(full_result, dict):
        return full_result.get("validation", {}).get("duplicate_check", {}).get("is_duplicate", False)
    return False

df["is_duplicate"] = df.apply(is_duplicate, axis=1)

st.subheader("Key Metrics")
col1, col2, col3, col4, col5 = st.columns(5)
with col1: st.metric("Total Invoices", len(df))
with col2: st.metric("Total Spend GBP", f"£{df['gbp_amount'].sum():,.2f}")
with col3: st.metric("Average Invoice", f"£{df['gbp_amount'].mean():,.2f}")
with col4: st.metric("High Risk Invoices", len(df[df["risk_level"] == "High"]))
with col5: st.metric("Duplicates", int(df["is_duplicate"].sum()))
st.divider()

st.subheader("Processed Invoices")
display_columns = ["vendor_name", "invoice_number", "invoice_date", "currency", "total_amount", "gbp_amount", "category", "risk_level", "fraud_score", "approval_status", "processed_at"]
existing_columns = [col for col in display_columns if col in df.columns]
st.dataframe(df[existing_columns], use_container_width=True)
st.divider()

st.subheader("Analytics Charts")
category_spend = df.groupby("category", dropna=False)["gbp_amount"].sum().reset_index().sort_values("gbp_amount", ascending=False)
st.plotly_chart(px.bar(category_spend, x="category", y="gbp_amount", title="Spend by Category GBP"), use_container_width=True)

vendor_spend = df.groupby("vendor_name", dropna=False)["gbp_amount"].sum().reset_index().sort_values("gbp_amount", ascending=False).head(10)
st.plotly_chart(px.bar(vendor_spend, x="vendor_name", y="gbp_amount", title="Top 10 Vendors by Spend GBP"), use_container_width=True)

risk_count = df.groupby("risk_level", dropna=False).size().reset_index(name="count")
st.plotly_chart(px.pie(risk_count, names="risk_level", values="count", title="Fraud Risk Distribution"), use_container_width=True)

monthly_spend = df.groupby("month")["gbp_amount"].sum().reset_index().sort_values("month")
st.plotly_chart(px.line(monthly_spend, x="month", y="gbp_amount", markers=True, title="Monthly Spend Trend GBP"), use_container_width=True)
st.plotly_chart(px.histogram(df, x="fraud_score", title="Fraud Score Distribution"), use_container_width=True)
st.divider()
st.subheader("Downloads")
st.download_button("Download Enhanced Dashboard CSV", df.to_csv(index=False), "enhanced_invoice_dashboard.csv", "text/csv")
