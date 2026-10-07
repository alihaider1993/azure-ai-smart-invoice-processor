# Agent 3 — Invoice Classifier
# Author: Syed Ali Haider

import json
from datetime import datetime
from services.azure_clients import get_container, get_deployment_name, get_openai_client

VENDOR_CONTAINER = "vendors"

EXPENSE_CATEGORIES = ["Travel & Transport", "Meals & Entertainment", "Office Supplies & Equipment", "Software & Subscriptions", "Professional Services", "Marketing & Advertising", "Utilities & Facilities", "Healthcare & Medical", "Training & Education", "Raw Materials & Inventory", "Maintenance & Repairs", "Other"]

def get_vendor_container():
    return get_container(VENDOR_CONTAINER)

def clean_vendor_id(vendor_name: str) -> str:
    if not vendor_name: return "Unknown"
    return vendor_name.replace("/", "-").replace("\\", "-").replace("#", "-").replace("?", "-")

def get_vendor_record(vendor_name: str):
    container = get_vendor_container()
    vendor_id = clean_vendor_id(vendor_name)
    try:
        return container.read_item(item=vendor_id, partition_key=vendor_id)
    except Exception:
        return None

def update_vendor_history(invoice_data: dict, category: str):
    vendor = invoice_data.get("vendor_name", "Unknown")
    vendor_id = clean_vendor_id(vendor)
    total = invoice_data.get("total_amount", 0)
    month = datetime.now().strftime("%Y-%m")
    container = get_vendor_container()
    record = get_vendor_record(vendor)
    if not record:
        record = {"id": vendor_id, "vendor_name": vendor, "total_invoices": 0, "total_spend": 0, "category": category, "monthly_spend": {}}
    record["total_invoices"] += 1
    record["total_spend"] += total
    record["category"] = category
    if month not in record["monthly_spend"]: record["monthly_spend"][month] = 0
    record["monthly_spend"][month] += total
    container.upsert_item(record)
    return record

def get_vendor_insights(vendor_name: str) -> dict:
    record = get_vendor_record(vendor_name)
    if not record: return {"known_vendor": False}
    current_month = datetime.now().strftime("%Y-%m")
    return {"known_vendor": True, "total_invoices": record.get("total_invoices", 0), "total_spend": record.get("total_spend", 0), "this_month_spend": record.get("monthly_spend", {}).get(current_month, 0), "category": record.get("category"), "insight": f"This is invoice #{record.get('total_invoices', 0) + 1} from {vendor_name}. Total historical spend: {record.get('total_spend', 0)}"}

def classify_invoice(extracted_data: dict) -> dict:
    print("🔍 Agent 3: Classifying invoice...")
    client = get_openai_client()
    vendor = extracted_data.get("vendor_name", "Unknown")
    line_items = extracted_data.get("line_items", [])
    total = extracted_data.get("total_amount", 0)
    currency = extracted_data.get("currency", "GBP")
    items_text = ""
    if line_items:
        for item in line_items:
            items_text += f"- {item.get('description', 'N/A')}: {item.get('total', 0)}\n"
    else:
        items_text = "No line items available"
    prompt = f"""You are an expert business expense classifier.

Classify this invoice into ONE of these categories:
{chr(10).join(f"- {cat}" for cat in EXPENSE_CATEGORIES)}

Approval policy: set requires_approval to true only when the purchase itself needs pre-approval
under typical company expense policy (e.g. entertainment, alcohol, gifts, personal items, travel upgrades).
Do NOT require approval because of the amount; amount thresholds are applied separately.

Invoice details:
- Vendor: {vendor}
- Total: {currency} {total}
- Line items:
{items_text}

Return ONLY a valid JSON object:
{{
    "category": "exact category name from the list",
    "confidence": "High/Medium/Low",
    "reasoning": "brief one sentence explanation",
    "subcategory": "more specific description e.g. 'Air Travel' under Travel & Transport",
    "is_reimbursable": true or false,
    "requires_approval": true or false,
    "approval_reason": "reason if approval required, else null"
}}

Return ONLY the JSON — no explanation, no markdown."""
    response = client.chat.completions.create(model=get_deployment_name(), messages=[{"role": "user", "content": prompt}], max_tokens=500, temperature=0.1)
    raw = response.choices[0].message.content.strip()
    if "```json" in raw: raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw: raw = raw.split("```")[1].split("```")[0].strip()
    classification = json.loads(raw)
    vendor_insights = get_vendor_insights(vendor)
    vendor_history = update_vendor_history(extracted_data, classification["category"])
    result = {"classification": classification, "vendor_insights": vendor_insights, "vendor_history": {"total_invoices": vendor_history["total_invoices"], "total_spend": vendor_history["total_spend"], "this_month": vendor_history["monthly_spend"].get(datetime.now().strftime("%Y-%m"), 0)}}
    print(f"   ✅ Category: {classification['category']}")
    print(f"   ✅ Confidence: {classification['confidence']}")
    print(f"   ✅ Vendor invoices tracked: {vendor_history['total_invoices']}")
    return result
