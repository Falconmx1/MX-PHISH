import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io

load_dotenv()

class EmailReporter:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT'))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.report_recipients = os.getenv('REPORT_EMAILS', '').split(',')
        
    def generate_html_report(self, stats, victims, period="daily"):
        """Genera reporte HTML bonito"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; padding: 20px; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #0052cc, #003d99); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 10px 0 0; opacity: 0.9; }}
                .content {{ padding: 30px; }}
                .stats {{ display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
                .stat-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; flex: 1; text-align: center; border-left: 4px solid #0052cc; }}
                .stat-box h3 {{ margin: 0; color: #666; font-size: 14px; }}
                .stat-box .number {{ font-size: 32px; font-weight: bold; color: #0052cc; margin: 10px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #0052cc; color: white; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; color: #666; font-size: 12px; }}
                .alert {{ background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .alert-critical {{ background: #f8d7da; border-left-color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎣 MX-PHISH Security Report</h1>
                    <p>{period.upper()} Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                <div class="content">
                    <div class="stats">
                        <div class="stat-box">
                            <h3>🎯 Total Víctimas</h3>
                            <div class="number">{stats['total_victims']}</div>
                        </div>
                        <div class="stat-box">
                            <h3>📧 Campañas</h3>
                            <div class="number">{stats['total_campaigns']}</div>
                        </div>
                        <div class="stat-box">
                            <h3>👆 Clics</h3>
                            <div class="number">{stats['total_clicks']}</div>
                        </div>
                        <div class="stat-box">
                            <h3>📈 Tasa Conversión</h3>
                            <div class="number">{stats.get('conversion_rate', 0)}%</div>
                        </div>
                    </div>
                    
                    <div class="alert {'alert-critical' if stats['total_victims'] > 10 else ''}">
                        <strong>⚠️ Resumen ejecutivo:</strong><br>
                        En el último período se detectaron <strong>{stats['new_victims']}</strong> nuevas víctimas.
                        {'Se recomienda refuerzo inmediato de capacitación.' if stats['new_victims'] > 5 else 'Continuar con campañas de concienciación.'}
                    </div>
                    
                    <h3>📋 Últimas víctimas capturadas</h3>
                    <table>
                        <thead>
                            <tr><th>Email</th><th>IP</th><th>Fecha</th><th>User Agent</th></tr>
                        </thead>
                        <tbody>
        """
        
        for v in victims[:15]:
            html += f"""
                            <tr>
                                <td>{v.email}</td>
                                <td>{v.ip}</td>
                                <td>{v.timestamp.strftime('%Y-%m-%d %H:%M')}</td>
                                <td>{v.user_agent[:30] if v.user_agent else 'N/A'}...</td>
                            </tr>
            """
        
        html += f"""
                        </tbody>
                    </table>
                </div>
                <div class="footer">
                    <p>Este es un reporte automático de MX-PHISH - Simulador de phishing educativo</p>
                    <p>Generado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    def generate_pdf_attachment(self, stats, victims):
        """Genera PDF adjunto para el reporte"""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor('#0052cc'))
        elements.append(Paragraph("MX-PHISH Security Report", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        # Fecha
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        # Estadísticas
        stats_data = [['Metric', 'Value'], ['Total Victims', str(stats['total_victims'])], 
                      ['New Victims', str(stats['new_victims'])], ['Campaigns', str(stats['total_campaigns'])],
                      ['Total Clicks', str(stats['total_clicks'])], ['Conversion Rate', f"{stats.get('conversion_rate', 0)}%"]]
        
        table = Table(stats_data)
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#0052cc')), 
                                   ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                                   ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
        elements.append(table)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    def send_report(self, stats, victims, period="daily"):
        """Envía reporte por email a todos los destinatarios configurados"""
        if not self.report_recipients or self.report_recipients == ['']:
            print("⚠️ No hay destinatarios configurados en REPORT_EMAILS")
            return False
        
        subject = f"[MX-PHISH] {period.upper()} Report - {stats['new_victims']} new victims detected"
        
        # Crear HTML del reporte
        html_content = self.generate_html_report(stats, victims, period)
        pdf_attachment = self.generate_pdf_attachment(stats, victims)
        
        msg = MIMEMultipart()
        msg['From'] = self.smtp_user
        msg['To'] = ', '.join(self.report_recipients)
        msg['Subject'] = subject
        
        # Adjuntar HTML
        msg.attach(MIMEText(html_content, 'html'))
        
        # Adjuntar PDF
        pdf_part = MIMEApplication(pdf_attachment.read(), _subtype='pdf')
        pdf_part.add_header('Content-Disposition', 'attachment', filename=f'mxphish_report_{datetime.now().strftime("%Y%m%d")}.pdf')
        msg.attach(pdf_part)
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            print(f"✅ Reporte enviado a {len(self.report_recipients)} destinatarios")
            return True
        except Exception as e:
            print(f"❌ Error enviando reporte: {e}")
            return False

# Función para uso rápido
def send_quick_report(stats, victims, period="daily"):
    reporter = EmailReporter()
    return reporter.send_report(stats, victims, period)
