# Agent 1 — Invoice Extractor
# Author: Syed Ali Haider
# Extracts all fields from invoice images and PDFs using GPT-4o Vision
# Uses Managed Identity — no API keys

import base64
import json
import os
from pathlib import Path
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.ai.formrecognizer import DocumentAnalysisClient
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
DOC_INTEL_ENDPOINT    = os.getenv("DOC_INTEL_ENDPOINT")
DEPLOYMENT_NAME       = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")


def get_openai_client():
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version="2024-05-01-preview"
    )


def get_doc_intel_client():
    credential = DefaultAzureCredential()
    return DocumentAnalysisClient(
        endpoint=DOC_INTEL_ENDPOINT,
        credential=credential
    )


def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_from_image(image_path: str) -> dict:
    print(f"🔍 Agent 1: Extracting from image — {image_path}")
    client = get_openai_client()
    base64_image = encode_image_to_base64(image_path)
    ext = Path(image_path).suffix.lower()
    media_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png"
    prompt = """You are an expert invoice data extractor. 
Extract ALL information from this invoice or receipt image.
Return ONLY a valid JSON object with these exact fields:
{
    "vendor_name": "company name",
    "vendor_address": "full address or null",
    "vendor_vat_number": "VAT number or NTN number or null",
    "invoice_number": "invoice/receipt number or null",
    "invoice_date": "date in YYYY-MM-DD format or null",
    "due_date": "due date in YYYY-MM-DD format or null",
    "currency": "currency code — detect from symbol or context. £ or GBP = GBP, $ or USD = USD. Default to GBP if unclear",
    "currency_symbol": "£, $, €, Rs etc",
    "subtotal": numeric value or null,
    "vat_amount": numeric value or null,
    "vat_rate": "e.g. 20% or null",
    "total_amount": numeric value,
    "line_items": [{"description": "item description", "quantity": numeric or null, "unit_price": numeric or null, "total": numeric}],
    "payment_method": "cash/card/bank transfer or null",
    "notes": "any additional notes or null",
    "is_handwritten": true or false,
    "confidence": "High/Medium/Low",
    "confidence_notes": "any fields that were unclear"
}
If a field cannot be found, use null.
Return ONLY the JSON — no explanation, no markdown."""
    response = client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=[{"role":"user","content":[{"type":"image_url","image_url":{"url":f"data:{media_type};base64,{base64_image}"}}, {"type":"text","text":prompt}]}],
        max_tokens=2000,
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    extracted = json.loads(raw)
    extracted["source_file"] = image_path
    extracted["extraction_method"] = "gpt4o_vision"
    print(f"✅ Agent 1: Extraction complete — {extracted.get('vendor_name', 'Unknown vendor')}")
    print(f"   Total: {extracted.get('currency_symbol', '£')}{extracted.get('total_amount', 0)}")
    print(f"   Confidence: {extracted.get('confidence', 'Unknown')}")
    return extracted


def extract_from_pdf(pdf_path: str) -> dict:
    print(f"🔍 Agent 1: Extracting from PDF — {pdf_path}")
    doc_client = get_doc_intel_client()
    with open(pdf_path, "rb") as f:
        poller = doc_client.begin_analyze_document("prebuilt-invoice", document=f)
    result = poller.result()
    raw_text = ""
    for doc in result.documents:
        for field_name, field in doc.fields.items():
            if field.value:
                raw_text += f"{field_name}: {field.value}\n"
    gpt_client = get_openai_client()
    prompt = f"""You are an expert invoice data extractor.
Based on this extracted invoice text, return a structured JSON object.
Extracted text:
{raw_text}
Return ONLY a valid JSON object with these exact fields:
{{
    "vendor_name": "company name",
    "vendor_address": "full address or null",
    "vendor_vat_number": "VAT number or NTN number or null",
    "invoice_number": "invoice number or null",
    "invoice_date": "date in YYYY-MM-DD format or null",
    "due_date": "due date in YYYY-MM-DD format or null",
    "currency": "currency code — detect from symbol or context. £ or GBP = GBP, $ or USD = USD. Default to GBP if unclear",
    "currency_symbol": "£, $, €, Rs etc",
    "subtotal": numeric value or null,
    "vat_amount": numeric value or null,
    "vat_rate": "e.g. 20% or null",
    "total_amount": numeric value,
    "line_items": [{{"description": "item description", "quantity": numeric or null, "unit_price": numeric or null, "total": numeric}}],
    "payment_method": "cash/card/bank transfer or null",
    "notes": "any additional notes or null",
    "is_handwritten": false,
    "confidence": "High/Medium/Low",
    "confidence_notes": "any fields that were unclear"
}}
Return ONLY the JSON — no explanation, no markdown."""
    response = gpt_client.chat.completions.create(
        model=DEPLOYMENT_NAME,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    extracted = json.loads(raw)
    extracted["source_file"] = pdf_path
    extracted["extraction_method"] = "doc_intelligence_gpt4o"
    print(f"✅ Agent 1: Extraction complete — {extracted.get('vendor_name', 'Unknown vendor')}")
    print(f"   Total: {extracted.get('currency_symbol', '£')}{extracted.get('total_amount', 0)}")
    print(f"   Confidence: {extracted.get('confidence', 'Unknown')}")
    return extracted


def extract_invoice(file_path: str) -> dict:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return extract_from_pdf(file_path)
    elif ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return extract_from_image(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")
