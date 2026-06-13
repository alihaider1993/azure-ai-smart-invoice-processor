# Agent 6 — Approval Workflow Agent
# Author: Syed Ali Haider


def approve_invoice(invoice_data: dict, validation_data: dict, classification_data: dict, fraud_data: dict) -> dict:
    print("✅ Agent 6: Checking approval workflow...")

    currency_conversion = validation_data.get("currency_conversion", {})
    gbp_amount = currency_conversion.get("gbp_amount")

    if gbp_amount is None:
        gbp_amount = invoice_data.get("total_amount", 0)

    duplicate = validation_data.get("duplicate_check", {}).get("is_duplicate", False)
    fraud_score = fraud_data.get("fraud_score", 0)
    risk_level = fraud_data.get("risk_level", "Low")
    classification = classification_data.get("classification", classification_data)
    requires_approval = classification.get("requires_approval", False)

    if duplicate:
        approval_status = "Rejected"
        approval_type = "Auto-Rejected"
        reason = "Duplicate invoice detected."
    elif fraud_score >= 70 or risk_level == "High":
        approval_status = "Pending"
        approval_type = "Finance Approval"
        reason = "High fraud risk detected."
    elif gbp_amount > 1000:
        approval_status = "Pending"
        approval_type = "Manager Approval"
        reason = "Invoice amount exceeds £1,000."
    elif requires_approval:
        approval_status = "Pending"
        approval_type = "Manager Approval"
        reason = classification.get("approval_reason", "Expense category requires approval.")
    elif validation_data.get("errors"):
        approval_status = "Rejected"
        approval_type = "Validation Failed"
        reason = "Invoice has validation errors."
    else:
        approval_status = "Approved"
        approval_type = "Auto-Approved"
        reason = "Invoice passed validation and risk checks."

    result = {
        "approval_status": approval_status,
        "approval_type": approval_type,
        "reason": reason,
        "gbp_amount": gbp_amount,
        "fraud_score": fraud_score,
        "risk_level": risk_level,
        "duplicate": duplicate
    }

    print(f"   ✅ Approval Status: {approval_status}")
    print(f"   ✅ Approval Type: {approval_type}")

    return result
