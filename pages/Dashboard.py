import os
import time

import pandas as pd
import plotly.express as px
import streamlit as st
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Invoice Dashboard",
    layout="wide"
)

st.title("Enhanced Invoice Analytics Dashboard")


@st.cache_data(ttl=60)
def load_processed_invoices():
    client = CosmosClient(
        url=os.getenv("COSMOS_ENDPOINT"),
        credential=DefaultAzureCredential()
    )

    database = client.get_database_client("invoice-db")
    container = database.get_container_client("processed-invoices")

    items = list(
        container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        )
    )

    return items


def get_database_client():
    client = CosmosClient(
        url=os.getenv("COSMOS_ENDPOINT"),
        credential=DefaultAzureCredential()
    )

    return client.get_database_client("invoice-db")


def delete_selected_invoice(invoice_id, vendor_name):
    """
    Delete one invoice from processed-invoices.
    Partition key for processed-invoices is /vendor_name.
    """

    database = get_database_client()
    container = database.get_container_client("processed-invoices")

    container.delete_item(
        item=invoice_id,
        partition_key=vendor_name
    )


def delete_all_invoice_data():
    """
    Delete all invoice-related records from all Cosmos DB containers.
    Uses correct partition keys:
    invoices -> /vendor_name
    processed-invoices -> /vendor_name
    vendors -> /vendor_name
    duplicates -> /invoice_hash
    """

    database = get_database_client()

    containers = {
        "invoices": "vendor_name",
        "processed-invoices": "vendor_name",
        "vendors": "vendor_name",
        "duplicates": "invoice_hash"
    }

    deleted_summary = {}

    for container_name, pk in containers.items():
        container = database.get_container_client(container_name)

        items = list(
            container.query_items(
                query=f"SELECT c.id, c.{pk} FROM c",
                enable_cross_partition_query=True
            )
        )

        deleted_count = 0

        for item in items:
            try:
                container.delete_item(
                    item=item["id"],
                    partition_key=item[pk]
                )
                deleted_count += 1

            except Exception as e:
                st.warning(
                    f"Could not delete item from {container_name}: {e}"
                )

        deleted_summary[container_name] = deleted_count

    return deleted_summary


# ----------------------------------------------------
# Admin Data Management
# ----------------------------------------------------

st.warning(
    "Admin area: use these options carefully. Deletions remove data from Azure Cosmos DB."
)

with st.expander("Admin Data Management"):
    st.write("You can delete one selected invoice or delete all stored invoice data.")

    st.info(
        "Individual delete removes only one record from processed-invoices. "
        "Delete all removes records from invoices, vendors, duplicates and processed-invoices."
    )


# ----------------------------------------------------
# Load data
# ----------------------------------------------------

items = load_processed_invoices()

if not items:
    st.warning("No processed invoices found yet.")

    with st.expander("Delete All Invoice Data"):
        confirm_delete_all_empty = st.text_input(
            "Type DELETE ALL to confirm deletion",
            key="confirm_delete_all_empty"
        )

        if st.button("Delete All Invoice Data", key="delete_all_empty"):
            if confirm_delete_all_empty == "DELETE ALL":
                deleted_summary = delete_all_invoice_data()

                st.success("All invoice data deleted successfully.")
                st.json(deleted_summary)

                st.cache_data.clear()
                time.sleep(2)
                st.rerun()
            else:
                st.error("Please type DELETE ALL exactly to confirm.")

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
# Processed Invoices Table
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
    df[existing_columns],
    use_container_width=True
)


# ----------------------------------------------------
# Delete Selected Invoice
# ----------------------------------------------------

st.subheader("Delete Selected Invoice")

invoice_options = {}

for idx, row in df.iterrows():
    label = (
        f"{row.get('invoice_number', 'No Invoice No')} | "
        f"{row.get('vendor_name', 'Unknown Vendor')} | "
        f"{row.get('currency', '')} {row.get('total_amount', '')}"
    )

    invoice_options[label] = {
        "id": row.get("id"),
        "vendor_name": row.get("vendor_name"),
        "invoice_number": row.get("invoice_number")
    }

selected_label = st.selectbox(
    "Select invoice to delete",
    list(invoice_options.keys())
)

selected_invoice = invoice_options[selected_label]

st.write("Selected invoice:")
st.json(selected_invoice)

confirm_selected_delete = st.text_input(
    "Type DELETE to confirm selected invoice deletion",
    key="confirm_selected_delete"
)

if st.button("Delete Selected Invoice"):
    if confirm_selected_delete == "DELETE":
        try:
            delete_selected_invoice(
                invoice_id=selected_invoice["id"],
                vendor_name=selected_invoice["vendor_name"]
            )

            st.success(
                f"Invoice {selected_invoice.get('invoice_number')} deleted successfully."
            )

            st.cache_data.clear()
            time.sleep(2)
            st.rerun()

        except Exception as e:
            st.error(f"Unable to delete selected invoice: {e}")

    else:
        st.error("Please type DELETE exactly to confirm selected invoice deletion.")

st.divider()


# ----------------------------------------------------
# Delete All Data
# ----------------------------------------------------

with st.expander("Delete All Invoice Data"):
    st.error(
        "This will delete ALL records from invoices, processed-invoices, vendors and duplicates."
    )

    confirm_delete_all = st.text_input(
        "Type DELETE ALL to confirm deletion of all invoice data",
        key="confirm_delete_all"
    )

    if st.button("Delete All Invoice Data"):
        if confirm_delete_all == "DELETE ALL":
            deleted_summary = delete_all_invoice_data()

            st.success("All invoice data deleted successfully.")
            st.json(deleted_summary)

            st.cache_data.clear()
            time.sleep(2)
            st.rerun()

        else:
            st.error("Please type DELETE ALL exactly to confirm.")

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
    fig_category,
    use_container_width=True
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
    fig_vendor,
    use_container_width=True
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
    fig_risk,
    use_container_width=True
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
    fig_monthly,
    use_container_width=True
)


fig_fraud = px.histogram(
    df,
    x="fraud_score",
    title="Fraud Score Distribution"
)

st.plotly_chart(
    fig_fraud,
    use_container_width=True
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
    mime="text/csv",
    on_click="ignore"
)
