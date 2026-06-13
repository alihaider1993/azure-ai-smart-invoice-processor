# Agent 5 — Reporter
# Author: Syed Ali Haider

import json
from datetime import datetime

def generate_report(invoice_data: dict, validation_data: dict, classification_data: dict, fraud_data: dict) -> dict:
    print("📝 Agent 5: Generating final report...")
    classification = classification_data.get("classification", classification_data)
    vendor_name = invoice_data.get("vendor_name", "Unknown Vendor")
    total_amount = invoice_data.get("total_amount", 0)
    currency = invoice_data.get("currency", "Unknown")
    invoice_number = invoice_data.get("invoice_number", "N/A")
    report = {
        "report_generated_at": datetime.now().isoformat(),
        "invoice_summary": {"vendor_name": vendor_name, "invoice_number": invoice_number, "invoice_date": invoice_data.get("invoice_date"), "currency": currency, "total_amount": total_amount, "category": classification.get("category"), "fraud_risk": fraud_data.get("risk_level"), "fraud_score": fraud_data.get("fraud_score")},
        "validation_summary": {"is_valid": validation_data.get("is_valid"), "warnings": validation_data.get("warnings", []), "errors": validation_data.get("errors", []), "duplicate_check": validation_data.get("duplicate_check", {})},
        "classification_summary": {"category": classification.get("category"), "subcategory": classification.get("subcategory"), "confidence": classification.get("confidence"), "is_reimbursable": classification.get("is_reimbursable"), "requires_approval": classification.get("requires_approval")},
        "fraud_summary": {"risk_level": fraud_data.get("risk_level"), "fraud_score": fraud_data.get("fraud_score"), "fraud_flags": fraud_data.get("fraud_flags", []), "recommendation": fraud_data.get("recommendation")},
        "executive_summary": create_executive_summary(invoice_data, validation_data, classification, fraud_data),
        "action_items": create_action_items(validation_data, fraud_data, classification)
    }
    print("   ✅ Report generated successfully")
    return report

def create_executive_summary(invoice_data: dict, validation_data: dict, classification: dict, fraud_data: dict) -> str:
    vendor = invoice_data.get("vendor_name", "Unknown Vendor")
    amount = invoice_data.get("total_amount", 0)
    currency = invoice_data.get("currency", "")
    category = classification.get("category", "Unclassified")
    risk = fraud_data.get("risk_level", "Unknown")
    duplicate = validation_data.get("duplicate_check", {}).get("is_duplicate", False)
    duplicate_text = "A duplicate invoice was detected." if duplicate else "No duplicate invoice was detected."
    return f"Invoice from {vendor} for {currency} {amount} was classified as {category}. The fraud risk level is {risk}. {duplicate_text}"

def create_action_items(validation_data: dict, fraud_data: dict, classification: dict) -> list:
    action_items = []
    if validation_data.get("errors"): action_items.append("Resolve validation errors before approval.")
    if validation_data.get("warnings"): action_items.append("Review validation warnings.")
    if fraud_data.get("risk_level") == "High": action_items.append("Send invoice for manual fraud review.")
    if fraud_data.get("risk_level") == "Medium": action_items.append("Finance team should verify invoice details.")
    if classification.get("requires_approval"): action_items.append("Manager approval required before reimbursement.")
    if not action_items: action_items.append("Invoice can proceed to normal processing.")
    return action_items
