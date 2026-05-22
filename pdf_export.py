from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from datetime import datetime
import io

def generate_report_pdf(stats, victims):
    """Genera un PDF con el reporte completo"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []
    
    # Título
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#0052cc'),
        alignment=1
    )
    elements.append(Paragraph("MX-PHISH Security Report", title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # Fecha
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        alignment=1
    )
    elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", date_style))
    elements.append(Spacer(1, 0.3*inch))
    
    # Estadísticas
    elements.append(Paragraph("Executive Summary", styles['Heading2']))
    stats_data = [
        ['Metric', 'Value'],
        ['Total Victims', str(stats['total_victims'])],
        ['Total Campaigns', str(stats['total_campaigns'])],
        ['Total Clicks', str(stats['total_clicks'])],
        ['Conversion Rate', f"{stats['total_clicks'] / (stats['total_victims'] + 0.001) * 100:.1f}%"]
    ]
    
    stats_table = Table(stats_data)
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#0052cc')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(stats_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Lista de víctimas
    elements.append(Paragraph("Victims Details", styles['Heading2']))
    
    victims_data = [['Email', 'IP', 'Date', 'User Agent']]
    for v in victims[:50]:  # límite de 50 para el PDF
        victims_data.append([
            v.email,
            v.ip,
            v.timestamp.strftime('%Y-%m-%d %H:%M'),
            v.user_agent[:30] + '...' if len(v.user_agent or '') > 30 else (v.user_agent or 'N/A')
        ])
    
    victims_table = Table(victims_data, repeatRows=1)
    victims_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0052cc')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))
    elements.append(victims_table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer
