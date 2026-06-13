# Agent 2 — Invoice Validator
# Author: Syed Ali Haider

import json
import hashlib
import os
from datetime import datetime
from services.exchange_rates import convert_to_gbp
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient
from dotenv import load_dotenv

load_dotenv()
COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
DATABASE_NAME = "invoice-db"
CONTAINER_NAME = "invoices"

def get_cosmos_client():
    credential = DefaultAzureCredential()
    return CosmosClient(url=COSMOS_ENDPOINT, credential=credential)

def get_container():
    client = get_cosmos_client()
    database = client.get_database_client(DATABASE_NAME)
    return database.get_container_client(CONTAINER_NAME)

def generate_invoice_hash(invoice_data: dict) -> str:
    key = f"{invoice_data.get('vendor_name','')}{invoice_data.get('invoice_number','')}{invoice_data.get('total_amount','')}{invoice_data.get('invoice_date','')}"
    return hashlib.md5(key.encode()).hexdigest()

def check_duplicate(invoice_data: dict, container) -> dict:
    invoice_hash = generate_invoice_hash(invoice_data)
    query = "SELECT * FROM c WHERE c.invoice_hash = @invoice_hash"
    parameters = [{"name": "@invoice_hash", "value": invoice_hash}]
    items = list(container.query_items(query=query, parameters=parameters, enable_cross_partition_query=True))
    if items:
        return {"is_duplicate": True, "duplicate_of": items[0].get("id"), "first_seen": items[0].get("processed_date"), "invoice_hash": invoice_hash}
    return {"is_duplicate": False, "invoice_hash": invoice_hash}

def save_invoice_record(invoice_data: dict, invoice_hash: str, container):
    record = {"id": invoice_hash, "invoice_hash": invoice_hash, "vendor_name": invoice_data.get("vendor_name", "unknown"), "invoice_number": invoice_data.get("invoice_number"), "invoice_date": invoice_data.get("invoice_date"), "total_amount": invoice_data.get("total_amount"), "currency": invoice_data.get("currency"), "processed_date": datetime.now().isoformat()}
    container.upsert_item(record)

def validate_invoice(extracted_data: dict) -> dict:
    print("🔍 Agent 2: Validating invoice...")
    validation_results = {"is_valid": True, "warnings": [], "errors": [], "duplicate_check": {}, "currency_conversion": {}}
    for field in ["vendor_name", "total_amount", "invoice_date"]:
        if not extracted_data.get(field):
            validation_results["errors"].append(f"Missing required field: {field}")
            validation_results["is_valid"] = False
    invoice_date = extracted_data.get("invoice_date")
    if invoice_date:
        try:
            date_obj = datetime.strptime(invoice_date, "%Y-%m-%d")
            if date_obj > datetime.now(): validation_results["warnings"].append(f"⚠️ Invoice date {invoice_date} is in the future")
            if (datetime.now() - date_obj).days > 730: validation_results["warnings"].append(f"⚠️ Invoice date {invoice_date} is more than 2 years old")
        except ValueError:
            validation_results["errors"].append(f"Invalid date format: {invoice_date}")
    subtotal = extracted_data.get("subtotal") or 0
    vat_amount = extracted_data.get("vat_amount") or 0
    total = extracted_data.get("total_amount") or 0
    if subtotal and vat_amount and total:
        expected = round(subtotal + vat_amount, 2)
        if abs(expected - total) > 1:
            validation_results["warnings"].append(f"⚠️ Amount mismatch: {subtotal} + {vat_amount} = {expected} but total is {total}")
    currency_result = convert_to_gbp(total, extracted_data.get("currency", "GBP"))
    validation_results["currency_conversion"] = currency_result
    if currency_result.get("currency_warning"): validation_results["warnings"].append(currency_result["currency_warning"])
    if not extracted_data.get("vendor_vat_number"): validation_results["warnings"].append("ℹ️ No VAT/Tax number found — verify if required")
    if not extracted_data.get("invoice_number"): validation_results["warnings"].append("ℹ️ No invoice number found — may be a receipt")
    if not extracted_data.get("payment_method"): validation_results["warnings"].append("ℹ️ Payment method not specified")
    try:
        container = get_container()
        duplicate_result = check_duplicate(extracted_data, container)
        validation_results["duplicate_check"] = duplicate_result
        if duplicate_result["is_duplicate"]:
            validation_results["warnings"].append(f"🔴 DUPLICATE DETECTED — matches invoice from {duplicate_result.get('first_seen', 'unknown date')}")
        else:
            save_invoice_record(extracted_data, duplicate_result["invoice_hash"], container)
    except Exception as e:
        validation_results["warnings"].append(f"Duplicate check unavailable: {e}")
    if validation_results["errors"]:
        validation_results["is_valid"] = False
        print(f"   ❌ {len(validation_results['errors'])} errors found")
    elif validation_results["warnings"]:
        print(f"   ⚠️ Passed with {len(validation_results['warnings'])} warnings")
    else:
        print("   ✅ Validation passed — no issues found")
    return validation_results
