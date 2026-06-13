# Full 6-Agent Smart Invoice Processor Pipeline
# Author: Syed Ali Haider

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
from agents.agent1_extractor import extract_invoice
from agents.agent2_validator import validate_invoice
from agents.agent3_classifier import classify_invoice
from agents.agent4_fraud_detector import detect_fraud
from agents.agent5_reporter import generate_report
from agents.agent6_approval import approve_invoice

load_dotenv()

def save_processed_invoice(result: dict):
    client = CosmosClient(url=os.getenv("COSMOS_ENDPOINT"), credential=DefaultAzureCredential())
    database = client.get_database_client("invoice-db")
    container = database.get_container_client("processed-invoices")
    invoice = result["invoice_data"]
    validation = result["validation"]
    currency_conversion = validation.get("currency_conversion", {})
    approval = result.get("approval", {})
    original_amount = currency_conversion.get("original_amount", invoice.get("total_amount"))
    original_currency = currency_conversion.get("original_currency", invoice.get("currency"))
    gbp_amount = currency_conversion.get("gbp_amount")
    exchange_rate = currency_conversion.get("exchange_rate")
    if gbp_amount is None: gbp_amount = invoice.get("total_amount")
    if exchange_rate is None: exchange_rate = 1 if invoice.get("currency") == "GBP" else None
    unique_key = f"{invoice.get('vendor_name', '')}{invoice.get('invoice_number', '')}{invoice.get('total_amount', '')}{result.get('processed_at', '')}"
    record_id = hashlib.md5(unique_key.encode()).hexdigest()
    record = {
        "id": record_id,
        "vendor_name": invoice.get("vendor_name", "unknown"),
        "invoice_number": invoice.get("invoice_number"),
        "invoice_date": invoice.get("invoice_date"),
        "total_amount": invoice.get("total_amount"),
        "currency": invoice.get("currency"),
        "original_amount": original_amount,
        "original_currency": original_currency,
        "gbp_amount": gbp_amount,
        "exchange_rate": exchange_rate,
        "category": result["classification"]["classification"].get("category"),
        "risk_level": result["fraud"].get("risk_level"),
        "fraud_score": result["fraud"].get("fraud_score"),
        "approval_status": approval.get("approval_status"),
        "approval_type": approval.get("approval_type"),
        "approval_reason": approval.get("reason"),
        "processed_at": result["processed_at"],
        "full_result": result
    }
    container.upsert_item(record)
    print("✅ Full processed invoice saved to Cosmos DB")
    print(f"   Original: {original_currency} {original_amount}")
    print(f"   GBP: £{gbp_amount}")
    print(f"   Approval: {approval.get('approval_status')}")

def process_invoice(file_path: str) -> dict:
    print("\n🚀 Starting 6-Agent Smart Invoice Processor")
    print(f"📄 File: {file_path}\n")
    invoice_data = extract_invoice(file_path)
    validation_data = validate_invoice(invoice_data)
    classification_data = classify_invoice(invoice_data)
    fraud_data = detect_fraud(invoice_data, validation_data, classification_data)
    report_data = generate_report(invoice_data, validation_data, classification_data, fraud_data)
    approval_data = approve_invoice(invoice_data, validation_data, classification_data, fraud_data)
    final_output = {"processed_at": datetime.now().isoformat(), "source_file": file_path, "invoice_data": invoice_data, "validation": validation_data, "classification": classification_data, "fraud": fraud_data, "report": report_data, "approval": approval_data}
    save_processed_invoice(final_output)
    return final_output

if __name__ == "__main__":
    file_path = "data/Invoice1.pdf"
    result = process_invoice(file_path)
    print("\n===== FINAL 6-AGENT OUTPUT =====")
    print(json.dumps(result, indent=2))
    Path("outputs").mkdir(exist_ok=True)
    with open("outputs/final_invoice_result.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n✅ Final result saved to outputs/final_invoice_result.json")
