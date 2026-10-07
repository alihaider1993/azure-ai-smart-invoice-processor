import hmac
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from services.azure_clients import get_container

st.set_page_config(
    page_title="Invoice Dashboard",
    layout="wide"
)

st.title("Enhanced Invoice Analytics Dashboard")

INVOICE_CONTAINERS = ["invoices", "processed-invoices", "vendors", "duplicates"]


@st.cache_data(ttl=60)
def load_processed_invoices():
    container = get_container("processed-invoices")
    return list(
        container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        )
    )


def delete_all_invoice_data():
    deleted_summary = {}

    for container_name in INVOICE_CONTAINERS:
        container = get_container(container_name)
        item_ids = list(
            container.query_items(
                query="SELECT VALUE c.id FROM c",
                enable_cross_partition_query=True
            )
        )

        deleted_count = 0
        for item_id in item_ids:
            try:
                # All containers are partitioned on /id
                container.delete_item(item=item_id, partition_key=item_id)
                deleted_count += 1
            except Exception as e:
                st.warning(f"Could not delete item from {container_name}: {e}")

        deleted_summary[container_name] = deleted_count

    return deleted_summary


# ----------------------------------------------------
# Admin Delete Option (only shown when ADMIN_PASSWORD is configured)
# ----------------------------------------------------

admin_password = os.getenv("ADMIN_PASSWORD")

if admin_password:
    with st.sidebar.expander("Admin: delete all invoice data"):
        entered_password = st.text_input("Admin password", type="password")

        if st.button("Delete all invoice data"):
            if hmac.compare_digest(entered_password.encode(), admin_password.encode()):
                deleted_summary = delete_all_invoice_data()
                st.cache_data.clear()
                st.success("All invoice data deleted.")
                st.json(deleted_summary)
            else:
                st.error("Incorrect admin password.")


try:
    items = load_processed_invoices()
except Exception:
    st.error("Could not load invoices from Cosmos DB right now. Please refresh in a minute.")
    st.stop()

if not items:
    st.info("No invoices processed in the last 24 hours. Process a sample invoice on the main page to populate the dashboard.")
    st.stop()

df = pd.DataFrame(items)

# Clean numeric fields
df["gbp_amount"] = pd.to_numeric(
    df.get("gbp_amount", df.get("total_amount", 0)),
    errors="coerce"
).fillna(0)

df["fraud_score"] = pd.to_numeric(
    df.get("fraud_score", 0),
    errors="coerce"
).fillna(0)

df["processed_at"] = pd.to_datetime(
    df["processed_at"],
    errors="coerce"
)

df["invoice_date"] = pd.to_datetime(
    df["invoice_date"],
    errors="coerce"
)

df["month"] = df["processed_at"].dt.to_period("M").astype(str)


def is_duplicate(row):
    full_result = row.get("full_result", {})

    if isinstance(full_result, dict):
        return full_result.get(
            "validation",
            {}
        ).get(
            "duplicate_check",
            {}
        ).get(
            "is_duplicate",
            False
        )

    return False


df["is_duplicate"] = df.apply(is_duplicate, axis=1)

# ----------------------------------------------------
# Metrics
# ----------------------------------------------------

st.subheader("Key Metrics")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Invoices", len(df))

with col2:
    st.metric("Total Spend GBP", f"£{df['gbp_amount'].sum():,.2f}")

with col3:
    st.metric("Average Invoice", f"£{df['gbp_amount'].mean():,.2f}")

with col4:
    st.metric("High Risk Invoices", len(df[df["risk_level"] == "High"]))

with col5:
    st.metric("Duplicates", int(df["is_duplicate"].sum()))

st.divider()

# ----------------------------------------------------
# Table
# ----------------------------------------------------

st.subheader("Processed Invoices")

display_columns = [
    "vendor_name",
    "invoice_number",
    "invoice_date",
    "currency",
    "total_amount",
    "gbp_amount",
    "category",
    "risk_level",
    "fraud_score",
    "approval_status",
    "approval_type",
    "processed_at"
]

existing_columns = [
    col for col in display_columns if col in df.columns
]

st.dataframe(
    df[existing_columns]
)

st.divider()

# ----------------------------------------------------
# Charts
# ----------------------------------------------------

st.subheader("Analytics Charts")

category_spend = (
    df.groupby("category", dropna=False)["gbp_amount"]
    .sum()
    .reset_index()
    .sort_values("gbp_amount", ascending=False)
)

fig_category = px.bar(
    category_spend,
    x="category",
    y="gbp_amount",
    title="Spend by Category GBP"
)

st.plotly_chart(
    fig_category
)


vendor_spend = (
    df.groupby("vendor_name", dropna=False)["gbp_amount"]
    .sum()
    .reset_index()
    .sort_values("gbp_amount", ascending=False)
    .head(10)
)

fig_vendor = px.bar(
    vendor_spend,
    x="vendor_name",
    y="gbp_amount",
    title="Top 10 Vendors by Spend GBP"
)

st.plotly_chart(
    fig_vendor
)


risk_count = (
    df.groupby("risk_level", dropna=False)
    .size()
    .reset_index(name="count")
)

fig_risk = px.pie(
    risk_count,
    names="risk_level",
    values="count",
    title="Fraud Risk Distribution"
)

st.plotly_chart(
    fig_risk
)


monthly_spend = (
    df.groupby("month")["gbp_amount"]
    .sum()
    .reset_index()
    .sort_values("month")
)

fig_monthly = px.line(
    monthly_spend,
    x="month",
    y="gbp_amount",
    markers=True,
    title="Monthly Spend Trend GBP"
)

st.plotly_chart(
    fig_monthly
)


fig_fraud = px.histogram(
    df,
    x="fraud_score",
    title="Fraud Score Distribution"
)

st.plotly_chart(
    fig_fraud
)

st.divider()

# ----------------------------------------------------
# Downloads
# ----------------------------------------------------

st.subheader("Downloads")

csv_data = df.to_csv(index=False)

st.download_button(
    label="Download Enhanced Dashboard CSV",
    data=csv_data,
    file_name="enhanced_invoice_dashboard.csv",
    mime="text/csv"
)