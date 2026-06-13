import json
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from run_pipeline import process_invoice
from services.pdf_generator import generate_pdf_report

st.set_page_config(page_title="Smart Invoice Processor", layout="wide")
st.title("Smart Invoice & Receipt Processor")
st.write("Upload one or more invoices and process them through the Azure AI pipeline.")

uploaded_files = st.file_uploader("Upload invoices", type=["pdf", "jpg", "jpeg", "png", "webp"], accept_multiple_files=True)

if uploaded_files:
    if st.button("Process Invoices"):
        all_results = []
        progress_bar = st.progress(0)
        for idx, uploaded_file in enumerate(uploaded_files):
            suffix = Path(uploaded_file.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.read())
                file_path = tmp.name
            with st.spinner(f"Processing {uploaded_file.name}..."):
                result = process_invoice(file_path)
                result["uploaded_file_name"] = uploaded_file.name
                all_results.append(result)
            progress_bar.progress((idx + 1) / len(uploaded_files))
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
        st.dataframe(summary_df, use_container_width=True)

        if len(summary_df) > 0:
            fig = px.bar(summary_df, x="Category", y="GBP Amount", title="Spend by Category GBP")
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Invoice Details")
        invoice_names = [f"{i+1}. {r['uploaded_file_name']}" for i, r in enumerate(all_results)]
        selected_invoice = st.selectbox("Select Invoice", invoice_names)
        selected_index = invoice_names.index(selected_invoice)
        result = all_results[selected_index]
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

        Path("outputs").mkdir(exist_ok=True)
        st.download_button("Download Batch JSON", json.dumps(all_results, indent=2), "batch_invoice_results.json", "application/json")
        st.download_button("Download Batch CSV", summary_df.to_csv(index=False), "batch_invoice_summary.csv", "text/csv")
        excel_path = "outputs/batch_invoice_summary.xlsx"
        summary_df.to_excel(excel_path, index=False)
        with open(excel_path, "rb") as f:
            st.download_button("Download Excel Report", f, "batch_invoice_summary.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        pdf_path = "outputs/invoice_report.pdf"
        generate_pdf_report(result, pdf_path)
        with open(pdf_path, "rb") as f:
            st.download_button("Download Selected Invoice PDF", f, "invoice_report.pdf", "application/pdf")
