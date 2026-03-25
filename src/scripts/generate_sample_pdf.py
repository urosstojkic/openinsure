"""Generate a realistic synthetic cyber insurance submission PDF.

Creates a professional-looking insurance application form that can be
used to test the document upload API and OCR quality.
"""

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def create_submission_pdf(output_path: str = "test-data/sample-submission.pdf") -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(output_path, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.5 * inch)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("Title2", parent=styles["Title"], fontSize=16, spaceAfter=6)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=12, textColor=colors.HexColor("#1e3a5f"), spaceBefore=14, spaceAfter=6)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    normal = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14)
    small = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8, textColor=colors.grey)

    elements: list = []

    # Header
    elements.append(Paragraph("CYBER LIABILITY INSURANCE APPLICATION", title_style))
    elements.append(Paragraph("Commercial Lines — New Business Submission", normal))
    elements.append(Spacer(1, 0.15 * inch))

    # Submission metadata
    meta = [
        ["Submission Date:", "March 25, 2026", "Submission #:", "SUB-2026-SYNTH-001"],
        ["Broker:", "Marsh & McLennan Companies", "Broker Code:", "MMC-00847"],
        ["Line of Business:", "Cyber Liability", "Policy Period:", "07/01/2026 – 07/01/2027"],
    ]
    t = Table(meta, colWidths=[1.4 * inch, 2.3 * inch, 1.4 * inch, 2.3 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, -1), (-1, -1), 1, colors.HexColor("#1e3a5f")),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.2 * inch))

    # Section 1: Applicant Information
    elements.append(Paragraph("SECTION 1: APPLICANT INFORMATION", heading_style))
    applicant = [
        ["Legal Name:", "Meridian Health Technologies, Inc."],
        ["DBA / Trade Name:", "MeridianTech"],
        ["Street Address:", "4200 Innovation Drive, Suite 300"],
        ["City, State, ZIP:", "Austin, TX 78759"],
        ["Website:", "www.meridiantech.com"],
        ["Year Established:", "2019"],
        ["State of Incorporation:", "Delaware"],
        ["NAICS Code:", "621511 — Medical Laboratories"],
        ["SIC Code:", "8071 — Health Services"],
        ["Tax ID (EIN):", "84-2937651"],
        ["Primary Contact:", "Dr. Sarah Mitchell, Chief Information Security Officer"],
        ["Phone:", "(512) 555-0184"],
        ["Email:", "s.mitchell@meridiantech.com"],
    ]
    t = Table(applicant, colWidths=[2.0 * inch, 5.4 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.15 * inch))

    # Section 2: Business Profile
    elements.append(Paragraph("SECTION 2: BUSINESS PROFILE", heading_style))
    elements.append(Paragraph(
        "Meridian Health Technologies provides cloud-based electronic health record (EHR) systems, "
        "telehealth platforms, and health data analytics to hospitals, clinics, and physician groups "
        "across 14 states. The company processes approximately 2.3 million patient records annually "
        "and maintains integrations with major insurance carriers for claims processing.",
        normal,
    ))
    elements.append(Spacer(1, 0.1 * inch))

    business = [
        ["Annual Revenue:", "$28,500,000 (FY 2025)"],
        ["Total Employees:", "215 (180 full-time, 35 contractors)"],
        ["Number of Locations:", "3 (Austin TX HQ, Denver CO, Boston MA)"],
        ["Industry Sector:", "Healthcare IT / Health Information Technology"],
        ["Records Under Management:", "2,300,000 patient records (PHI)"],
        ["PCI-DSS Compliant:", "Yes — Level 2 Service Provider"],
        ["HIPAA Compliant:", "Yes — Business Associate Agreements with all clients"],
        ["SOC 2 Type II:", "Yes — Last audit: November 2025 (no findings)"],
    ]
    t = Table(business, colWidths=[2.2 * inch, 5.2 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.15 * inch))

    # Section 3: IT Security Posture
    elements.append(Paragraph("SECTION 3: INFORMATION SECURITY POSTURE", heading_style))
    security = [
        ["Multi-Factor Authentication (MFA):", "Yes — All employees, all remote access, all admin accounts"],
        ["Endpoint Detection & Response:", "Yes — CrowdStrike Falcon deployed on all endpoints"],
        ["Email Security:", "Yes — Microsoft Defender for Office 365 + Proofpoint"],
        ["Backup Strategy:", "Yes — 3-2-1 strategy, daily backups, tested quarterly"],
        ["Incident Response Plan:", "Yes — Last tabletop exercise: January 2026"],
        ["Security Awareness Training:", "Yes — Mandatory annual + monthly phishing simulations"],
        ["Patch Management:", "Yes — Critical patches within 72 hours, regular within 30 days"],
        ["Network Segmentation:", "Yes — VLAN isolation for PHI systems, DMZ for web services"],
        ["Penetration Testing:", "Yes — Annual third-party pentest (NCC Group, last: Oct 2025)"],
        ["Encryption at Rest:", "AES-256 for all databases containing PHI"],
        ["Encryption in Transit:", "TLS 1.3 for all external connections"],
        ["SIEM / SOC:", "Yes — Splunk SIEM with 24/7 managed SOC (Arctic Wolf)"],
        ["Vulnerability Scanning:", "Weekly Tenable.io scans, continuous for critical systems"],
        ["Security Maturity Score:", "7 out of 10 (self-assessed using NIST CSF)"],
    ]
    t = Table(security, colWidths=[2.8 * inch, 4.6 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.15 * inch))

    # Section 4: Loss History
    elements.append(Paragraph("SECTION 4: PRIOR LOSS HISTORY (PAST 5 YEARS)", heading_style))
    loss_header = ["Date", "Type", "Description", "Total Incurred"]
    loss_data = [
        loss_header,
        ["Sep 2024", "Phishing", "Business email compromise — CFO impersonation. Wire transfer of $42,000 to fraudulent account. $31,500 recovered.", "$18,200"],
        ["Mar 2023", "Ransomware", "LockBit 3.0 encrypted 3 file servers (non-PHI). Restored from backups within 18 hours. No ransom paid. Forensic investigation cost.", "$67,400"],
        ["—", "—", "No other incidents in the past 5 years.", "—"],
    ]
    t = Table(loss_data, colWidths=[0.8 * inch, 1.0 * inch, 4.2 * inch, 1.4 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.15 * inch))

    # Section 5: Coverage Requested
    elements.append(Paragraph("SECTION 5: COVERAGE REQUESTED", heading_style))
    coverage = [
        ["Coverage", "Limit Requested", "Retention/Deductible"],
        ["First-Party Breach Response", "$2,000,000", "$25,000"],
        ["Business Interruption", "$1,000,000", "$50,000 / 12-hour waiting period"],
        ["Cyber Extortion / Ransomware", "$1,000,000", "$25,000"],
        ["Third-Party Liability", "$2,000,000", "$25,000"],
        ["Regulatory Defense & Fines", "$1,000,000", "$25,000"],
        ["Media Liability", "$500,000", "$10,000"],
        ["Social Engineering Fraud", "$250,000", "$15,000"],
        ["Aggregate Limit", "$5,000,000", "—"],
    ]
    t = Table(coverage, colWidths=[2.8 * inch, 1.8 * inch, 2.8 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("ALIGN", (1, 1), (2, -1), "RIGHT"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.15 * inch))

    # Section 6: Prior Insurance
    elements.append(Paragraph("SECTION 6: PRIOR INSURANCE", heading_style))
    prior = [
        ["Current Carrier:", "Coalition, Inc."],
        ["Policy Number:", "CCI-2025-78432"],
        ["Annual Premium:", "$34,200"],
        ["Aggregate Limit:", "$3,000,000"],
        ["Policy Period:", "07/01/2025 – 07/01/2026"],
        ["Reason for Shopping:", "Seeking higher limits and broader coverage for regulatory defense"],
        ["Claims in Current Term:", "None"],
        ["Non-Renewal Notice:", "No"],
    ]
    t = Table(prior, colWidths=[2.0 * inch, 5.4 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.2 * inch))

    # Signature block
    elements.append(Paragraph("APPLICANT CERTIFICATION", heading_style))
    elements.append(Paragraph(
        "I hereby certify that the information provided in this application is true, accurate, and complete "
        "to the best of my knowledge. I understand that any material misrepresentation or omission may void "
        "coverage. I authorize the insurer to obtain additional information as needed to evaluate this application.",
        normal,
    ))
    elements.append(Spacer(1, 0.3 * inch))

    sig = [
        ["Signature: ____________________________", "Date: March 25, 2026"],
        ["Name: Dr. Sarah Mitchell", "Title: CISO"],
        ["Company: Meridian Health Technologies, Inc.", ""],
    ]
    t = Table(sig, colWidths=[4.0 * inch, 3.4 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)

    # Footer
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(
        "CONFIDENTIAL — This application and all attachments contain proprietary information. "
        f"Generated: {date.today().isoformat()} | Form: CYBER-APP-2026-v2.1",
        small,
    ))

    doc.build(elements)
    return output_path


if __name__ == "__main__":
    path = create_submission_pdf()
    print(f"PDF created: {path}")
