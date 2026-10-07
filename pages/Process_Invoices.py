import io
import json
import logging
import os
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from run_pipeline import process_invoice
from services.azure_clients import get_container
from services.pdf_generator import generate_pdf_report

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
SAMPLE_INVOICES = {
    "Northwind Office Supplies (UK, GBP): clean invoice": "northwind_office_supplies.pdf",
    "Atlas Cloud Services (US, USD): over £1,000 after conversion": "atlas_cloud_services_usd.pdf",
    "QuickFix Maintenance (EU, EUR receipt photo): suspicious": "quickfix_maintenance_receipt.png",
}
MAX_FILES_PER_BATCH = 3
DAILY_INVOICE_LIMIT = int(os.getenv("DAILY_INVOICE_LIMIT", "40"))
REPO_URL = "https://github.com/alihaider1993/azure-ai-smart-invoice-processor"

st.set_page_config(page_title="Smart Invoice Processor", layout="wide")
st.title("Smart Invoice & Receipt Processor")
st.write("Process invoices through a 6-agent Azure AI pipeline: extraction, validation, classification, fraud scoring, reporting and approval.")
st.info(
    "**Public demo.** Try the fictional sample invoices, or upload your own. "
    "Please don't upload real or sensitive invoices. "
    "Processed data is deleted automatically after 24 hours. "
    f"[View the source on GitHub]({REPO_URL})."
)


def invoices_processed_last_24h() -> int:
    """processed-invoices has a 24-hour TTL, so its item count is a rolling daily usage figure."""
    container = get_container("processed-invoices")
    return next(iter(container.query_items("SELECT VALUE COUNT(1) FROM c", enable_cross_partition_query=True)), 0)


def run_batch(files: list[tuple[str, Path]]) -> list[dict]:
    results = []
    progress_bar = st.progress(0)
    for idx, (display_name, file_path) in enumerate(files):
        with st.spinner(f"Processing {display_name}..."):
            try:
                result = process_invoice(str(file_path))
                result["uploaded_file_name"] = display_name
                results.append(result)
            except Exception:
                logging.exception("Failed to process %s", display_name)
                st.error(
                    f"Couldn't process **{display_name}**. The file may be unreadable, "
                    "or the Azure AI services may be busy. Try again in a minute or try a sample invoice."
                )
        progress_bar.progress((idx + 1) / len(files))
    return results


source = st.radio("Choose invoices", ["Sample invoices", "Upload your own"], horizontal=True)

if source == "Sample invoices":
    selected_samples = st.multiselect(
        "Sample invoices",
        list(SAMPLE_INVOICES),
        default=list(SAMPLE_INVOICES)[:1],
        help="Fictional invoices, each designed to trigger a different approval outcome. "
             "Samples are shared, so if someone processed one in the last 24 hours you'll see duplicate detection reject it.",
    )
    batch = [(name, SAMPLES_DIR / SAMPLE_INVOICES[name]) for name in selected_samples]
else:
    uploaded_files = st.file_uploader(
        f"Upload up to {MAX_FILES_PER_BATCH} invoices (PDF, JPG, PNG or WEBP, max 5 MB each)",
        type=["pdf", "jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )
    batch = uploaded_files or []

too_many_files = len(batch) > MAX_FILES_PER_BATCH
if too_many_files:
    st.warning(f"Please choose at most {MAX_FILES_PER_BATCH} invoices per batch.")

if st.button("Process invoices", type="primary", disabled=not batch or too_many_files):
    try:
        processed_today = invoices_processed_last_24h()
    except Exception:
        logging.exception("Could not read usage count")
        processed_today = 0

    if processed_today + len(batch) > DAILY_INVOICE_LIMIT:
        st.warning(
            f"This demo has reached its limit of {DAILY_INVOICE_LIMIT} invoices per 24 hours, which keeps Azure costs down. "
            "Please try again tomorrow, or browse the Dashboard and Invoice history pages."
        )
    elif source == "Sample invoices":
        st.session_state["results"] = run_batch(batch)
    else:
        temp_paths = []
        try:
            for uploaded_file in batch:
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp:
                    tmp.write(uploaded_file.getvalue())
                    temp_paths.append((uploaded_file.name, Path(tmp.name)))
            st.session_state["results"] = run_batch(temp_paths)
        finally:
            for _, temp_path in temp_paths:
                temp_path.unlink(missing_ok=True)

all_results = st.session_state.get("results", [])

if all_results:
    st.success(f"{len(all_results)} invoice(s) processed successfully")

    summary_rows = []
    for result in all_results:
        invoice = result["invoice_data"]
        validation = result["validation"]
        classification = result["classification"]["classification"]
        fraud = result["fraud"]
        currency_conversion = validation.get("currency_conversion", {})
        approval = result.get("approval", {})
        summary_rows.append({
            "File": result.get("uploaded_file_name"),
            "Vendor": invoice.get("vendor_name"),
            "Invoice Number": invoice.get("invoice_number"),
            "Original Amount": invoice.get("total_amount"),
            "Currency": invoice.get("currency"),
            "GBP Amount": currency_conversion.get("gbp_amount"),
            "Category": classification.get("category"),
            "Risk Level": fraud.get("risk_level"),
            "Fraud Score": fraud.get("fraud_score"),
            "Approval Status": approval.get("approval_status"),
            "Approval Type": approval.get("approval_type")
        })

    summary_df = pd.DataFrame(summary_rows)
    st.subheader("Batch Processing Summary")
    st.dataframe(summary_df)

    fig = px.bar(summary_df, x="Category", y="GBP Amount", title="Spend by Category GBP")
    st.plotly_chart(fig)

    st.subheader("Invoice Details")
    invoice_names = [f"{i+1}. {r['uploaded_file_name']}" for i, r in enumerate(all_results)]
    selected_invoice = st.selectbox("Select Invoice", invoice_names)
    result = all_results[invoice_names.index(selected_invoice)]
    invoice = result["invoice_data"]
    validation = result["validation"]
    classification = result["classification"]["classification"]
    fraud = result["fraud"]
    report = result["report"]
    approval = result.get("approval", {})

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Invoice Data", "Validation", "Classification", "Fraud Risk", "Final Report", "Approval"])
    with tab1: st.json(invoice)
    with tab2: st.json(validation)
    with tab3: st.json(classification)
    with tab4:
        col1, col2 = st.columns(2)
        with col1: st.metric("Risk Level", fraud["risk_level"])
        with col2: st.metric("Fraud Score", fraud["fraud_score"])
        st.write(fraud["fraud_flags"])
    with tab5:
        st.subheader("Executive Summary")
        st.write(report["executive_summary"])
        st.subheader("Action Items")
        for item in report["action_items"]: st.write(f"- {item}")
    with tab6:
        st.subheader("Approval Workflow")
        st.json(approval)

    excel_buffer = io.BytesIO()
    summary_df.to_excel(excel_buffer, index=False)
    pdf_buffer = io.BytesIO()
    generate_pdf_report(result, pdf_buffer)

    st.download_button("Download Batch JSON", json.dumps(all_results, indent=2), "batch_invoice_results.json", "application/json", on_click="ignore")
    st.download_button("Download Batch CSV", summary_df.to_csv(index=False), "batch_invoice_summary.csv", "text/csv", on_click="ignore")
    st.download_button("Download Excel Report", excel_buffer.getvalue(), "batch_invoice_summary.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", on_click="ignore")
    st.download_button("Download Selected Invoice PDF", pdf_buffer.getvalue(), "invoice_report.pdf", "application/pdf", on_click="ignore")
