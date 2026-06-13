from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def generate_pdf_report(report_data: dict, output_file: str):
    """Generate an executive PDF report for one invoice."""
    doc = SimpleDocTemplate(output_file)
    styles = getSampleStyleSheet()
    content = []

    content.append(Paragraph("Smart Invoice Processor Report", styles["Title"]))
    content.append(Spacer(1, 12))

    report = report_data["report"]
    content.append(Paragraph(f"<b>Executive Summary</b><br/>{report['executive_summary']}", styles["BodyText"]))
    content.append(Spacer(1, 12))

    fraud = report["fraud_summary"]
    content.append(Paragraph(f"<b>Fraud Risk:</b> {fraud['risk_level']}<br/><b>Fraud Score:</b> {fraud['fraud_score']}", styles["BodyText"]))
    content.append(Spacer(1, 12))

    content.append(Paragraph("<b>Action Items</b>", styles["Heading2"]))
    for item in report["action_items"]:
        content.append(Paragraph(f"• {item}", styles["BodyText"]))

    doc.build(content)
    return output_file
