# Agent 4 — Fraud Detector
# Author: Syed Ali Haider

import json
from datetime import datetime

def detect_fraud(invoice_data: dict, validation_data: dict, classification_data: dict) -> dict:
    print("🔍 Agent 4: Detecting fraud risk...")
    fraud_score = 0
    fraud_flags = []
    total_amount = invoice_data.get("total_amount") or 0
    vat_amount = invoice_data.get("vat_amount")
    invoice_date = invoice_data.get("invoice_date")
    invoice_number = invoice_data.get("invoice_number")
    vendor_name = invoice_data.get("vendor_name", "Unknown Vendor")
    duplicate_check = validation_data.get("duplicate_check", {})
    if duplicate_check.get("is_duplicate"):
        fraud_score += 40; fraud_flags.append("Duplicate invoice detected")
    if total_amount > 5000:
        fraud_score += 20; fraud_flags.append("High value invoice")
    if not invoice_data.get("vendor_vat_number"):
        fraud_score += 10; fraud_flags.append("Missing vendor VAT/tax number")
    if not invoice_number:
        fraud_score += 15; fraud_flags.append("Missing invoice number")
    if total_amount and total_amount % 100 == 0:
        fraud_score += 10; fraud_flags.append("Round number invoice amount")
    if invoice_date:
        try:
            date_obj = datetime.strptime(invoice_date, "%Y-%m-%d")
            if date_obj.weekday() >= 5:
                fraud_score += 10; fraud_flags.append("Invoice dated on weekend")
        except ValueError:
            fraud_score += 10; fraud_flags.append("Invalid invoice date format")
    if total_amount > 1000 and not vat_amount:
        fraud_score += 15; fraud_flags.append("High value invoice with missing VAT")
    classification = classification_data.get("classification", classification_data)
    if classification.get("requires_approval"):
        fraud_score += 10; fraud_flags.append("Expense requires approval")
    fraud_score = min(fraud_score, 100)
    risk_level = "High" if fraud_score >= 70 else "Medium" if fraud_score >= 35 else "Low"
    result = {"vendor_name": vendor_name, "fraud_score": fraud_score, "risk_level": risk_level, "fraud_flags": fraud_flags, "recommendation": get_recommendation(risk_level)}
    print(f"   ✅ Fraud Risk: {risk_level}")
    print(f"   ✅ Score: {fraud_score}/100")
    return result

def get_recommendation(risk_level: str) -> str:
    if risk_level == "High": return "Manual review required before payment."
    if risk_level == "Medium": return "Finance team should verify before approval."
    return "No major fraud risk detected."
