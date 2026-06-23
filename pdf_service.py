from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER
from io import BytesIO
from datetime import datetime


def generate_report_pdf(tickets: list, summary: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=1.5*cm, leftMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Heading1'],
                                 alignment=TA_CENTER, fontSize=16)
    sub_style = ParagraphStyle('sub', parent=styles['Normal'],
                               alignment=TA_CENTER, fontSize=10, textColor=colors.grey)

    elements = []

    # Title
    elements.append(Paragraph("Support Ticket Report", title_style))
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%d %b %Y, %H:%M')}", sub_style))
    elements.append(Spacer(1, 0.5*cm))

    # Summary cards as a table
    summary_data = [
        ['Total Tickets', 'Open', 'In Progress', 'Resolved'],
        [
            str(summary['total'] or 0),
            str(summary['open_t'] or 0),
            str(summary['in_progress'] or 0),
            str(summary['resolved'] or 0)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[4*cm]*4)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0f4ff'), colors.white]),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.7*cm))

    # Ticket table header
    elements.append(Paragraph("Ticket Details", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))

    headers = ['Ticket No.', 'Title', 'Category', 'Priority', 'Status', 'Customer', 'Agent', 'Created']
    rows = [headers]

    for t in tickets:
        created = t['created_at'].strftime('%d/%m/%Y') if t['created_at'] else '-'
        rows.append([
            t['ticket_number'],
            t['title'][:30] + ('...' if len(t['title']) > 30 else ''),
            t['category'].capitalize(),
            t['priority'].upper(),
            t['status'].replace('_', ' ').capitalize(),
            t['customer'] or '-',
            t['agent'] or 'Unassigned',
            created
        ])

    col_widths = [2.5*cm, 4.5*cm, 2.5*cm, 2*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
    ticket_table = Table(rows, colWidths=col_widths, repeatRows=1)

    priority_colors = {
        'LOW': colors.HexColor('#198754'),
        'MEDIUM': colors.HexColor('#0d6efd'),
        'HIGH': colors.HexColor('#fd7e14'),
        'URGENT': colors.HexColor('#dc3545'),
    }

    ticket_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#212529')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#dee2e6')),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#dee2e6')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(ticket_table)

    doc.build(elements)
    return buffer.getvalue()
