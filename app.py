from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import json
import threading
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Cargar variables de entorno
load_dotenv()

# ============ INICIALIZACIÓN DE LA APP ============
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///phish_sim.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mx-phish-secret-key-2024')
CORS(app)

# ============ BASE DE DATOS ============
db = SQLAlchemy(app)

# Modelos
class Victim(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    ip = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_agent = db.Column(db.String(500))
    campaign_id = db.Column(db.Integer, db.ForeignKey('campaign.id'))

class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subject = db.Column(db.String(200))
    template = db.Column(db.Text)
    sent_count = db.Column(db.Integer, default=0)
    click_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Crear tablas
with app.app_context():
    db.create_all()

# ============ AUTENTICACIÓN ============
auth = HTTPBasicAuth()

# Usuarios autorizados
users = {
    "admin": generate_password_hash(os.getenv('DASHBOARD_PASSWORD', 'MX-PHISH2024')),
    "security": generate_password_hash(os.getenv('SECURITY_PASSWORD', 'SecurePass123'))
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None

# ============ RATE LIMITING ============
limiter = Limiter(
    get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)
limiter.init_app(app)

class EmailRateLimiter:
    def __init__(self):
        self.sent_counts = {
            'minute': [],
            'hour': [],
            'day': []
        }
    
    def can_send(self):
        now = datetime.now()
        
        # Limpiar registros antiguos
        self.sent_counts['minute'] = [t for t in self.sent_counts['minute'] if t > now - timedelta(minutes=1)]
        self.sent_counts['hour'] = [t for t in self.sent_counts['hour'] if t > now - timedelta(hours=1)]
        self.sent_counts['day'] = [t for t in self.sent_counts['day'] if t > now - timedelta(days=1)]
        
        # Verificar límites
        if len(self.sent_counts['minute']) >= 10:
            return False, "Límite por minuto alcanzado (10/min)"
        if len(self.sent_counts['hour']) >= 100:
            return False, "Límite por hora alcanzado (100/hora)"
        if len(self.sent_counts['day']) >= 500:
            return False, "Límite por día alcanzado (500/día)"
        
        return True, "OK"
    
    def record_send(self):
        now = datetime.now()
        self.sent_counts['minute'].append(now)
        self.sent_counts['hour'].append(now)
        self.sent_counts['day'].append(now)

email_rate_limiter = EmailRateLimiter()

# ============ WEBHOOK CONFIGURACIÓN ============
WEBHOOK_CONFIG_FILE = 'webhook_config.json'

def load_webhook_config():
    """Carga configuración del webhook"""
    try:
        with open(WEBHOOK_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_webhook_config(config):
    """Guarda configuración del webhook"""
    with open(WEBHOOK_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def send_webhook(event_type, data):
    """Envía notificación a webhook configurado"""
    config = load_webhook_config()
    if not config or not config.get('url'):
        return False
    
    # Verificar si el evento está habilitado
    events = config.get('events', {})
    if not events.get(event_type, False):
        return False
    
    payload = {
        'event': event_type,
        'timestamp': datetime.now().isoformat(),
        'data': data,
        'source': 'MX-PHISH'
    }
    
    try:
        headers = config.get('headers', {})
        method = config.get('method', 'POST')
        timeout = config.get('timeout', 5)
        
        if method == 'POST':
            response = requests.post(config['url'], json=payload, headers=headers, timeout=timeout)
        else:
            response = requests.get(config['url'], params=payload, headers=headers, timeout=timeout)
        
        return response.status_code in [200, 201, 202, 204]
    except Exception as e:
        print(f"Error enviando webhook: {e}")
        return False

# ============ NOTIFICACIONES ============
class SlackNotifier:
    def __init__(self):
        self.webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.channel = os.getenv('SLACK_CHANNEL', '#security-alerts')
    
    def send_message(self, message, color="good"):
        """Envía un mensaje simple a Slack"""
        if not self.webhook_url:
            return False
        
        payload = {
            "channel": self.channel,
            "username": "MX-PHISH Bot",
            "icon_emoji": ":fishing_pole_and_fish:",
            "attachments": [{
                "color": color,
                "text": message,
                "footer": "MX-PHISH Security Simulator",
                "ts": int(datetime.now().timestamp())
            }]
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"Error Slack: {e}")
            return False
    
    def send_new_victim_alert(self, victim):
        """Alerta cuando alguien cae en el phishing"""
        message = f"""
        *🔴 NUEVA VÍCTIMA DETECTADA*
        *Email:* {victim.email}
        *IP:* {victim.ip}
        *Hora:* {victim.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
        *User Agent:* {victim.user_agent[:50] if victim.user_agent else 'N/A'}...
        """
        return self.send_message(message, color="danger")
    
    def send_daily_summary(self, stats):
        """Reporte diario resumido"""
        color = "good" if stats.get('new_victims', 0) < 5 else "warning" if stats.get('new_victims', 0) < 20 else "danger"
        
        message = f"""
        *📊 MX-PHISH Daily Summary*
        • Víctimas hoy: *{stats.get('new_victims', 0)}*
        • Total acumulado: *{stats.get('total_victims', 0)}*
        • Campañas activas: *{stats.get('total_campaigns', 0)}*
        • Tasa de clics: *{stats.get('conversion_rate', 0)}%*
        """
        return self.send_message(message, color=color)

slack = SlackNotifier()

class EmailReporter:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.smtp_user = os.getenv('SMTP_USER')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.report_recipients = os.getenv('REPORT_EMAILS', '').split(',')
    
    def send_report(self, stats, victims, period="daily", extra_emails=None):
        """Envía reporte por email"""
        if not self.smtp_user or not self.smtp_password:
            print("⚠️ SMTP no configurado")
            return False
        
        recipients = self.report_recipients
        if extra_emails:
            recipients.extend([e.strip() for e in extra_emails.split(',') if e.strip()])
        
        if not recipients:
            return False
        
        subject = f"[MX-PHISH] {period.upper()} Report - {stats.get('new_victims', 0)} new victims"
        
        html_content = self.generate_html_report(stats, victims, period)
        
        msg = MIMEMultipart()
        msg['From'] = self.smtp_user
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            print(f"✅ Reporte enviado a {len(recipients)} destinatarios")
            return True
        except Exception as e:
            print(f"❌ Error enviando reporte: {e}")
            return False
    
    def generate_html_report(self, stats, victims, period):
        """Genera HTML del reporte"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f0f2f5; padding: 20px; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden; }}
                .header {{ background: linear-gradient(135deg, #0052cc, #003d99); color: white; padding: 30px; text-align: center; }}
                .header h1 {{ margin: 0; }}
                .content {{ padding: 30px; }}
                .stats {{ display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }}
                .stat-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; flex: 1; text-align: center; }}
                .stat-box .number {{ font-size: 32px; font-weight: bold; color: #0052cc; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #0052cc; color: white; }}
                .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; }}
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
                            <div class="number">{stats.get('total_victims', 0)}</div>
                            <div>Total Víctimas</div>
                        </div>
                        <div class="stat-box">
                            <div class="number">{stats.get('new_victims', 0)}</div>
                            <div>Nuevas Víctimas</div>
                        </div>
                        <div class="stat-box">
                            <div class="number">{stats.get('conversion_rate', 0)}%</div>
                            <div>Tasa Conversión</div>
                        </div>
                    </div>
                    <h3>Últimas víctimas</h3>
                    <table>
                        <thead><tr><th>Email</th><th>IP</th><th>Fecha</th></tr></thead>
                        <tbody>
                            {''.join([f'<tr><td>{v.email}</td><td>{v.ip}</td><td>{v.timestamp.strftime("%Y-%m-%d %H:%M")}</td></tr>' for v in victims[:15]])}
                        </tbody>
                    </table>
                </div>
                <div class="footer">
                    <p>Reporte automático de MX-PHISH - Simulador de phishing educativo</p>
                </div>
            </div>
        </body>
        </html>
        """

reporter = EmailReporter()

# ============ ENVÍO DE CORREOS SMTP ============
def send_phishing_email(target_email, name, tracking_url):
    """Envía correo de phishing simulado"""
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    if not smtp_user or not smtp_password:
        print("⚠️ SMTP no configurado en .env")
        return False
    
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>⚠️ Acción requerida: Tu contraseña expira hoy</h2>
        <p>Hola {name},</p>
        <p>El sistema ha detectado que tu contraseña <strong>expirará en 24 horas</strong>.</p>
        <p>Para evitar la pérdida de acceso, haz clic en el siguiente enlace:</p>
        <p><a href="{tracking_url}" style="background-color: #0052cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Mantener mi contraseña</a></p>
        <hr>
        <p style="color: gray; font-size: 12px;">🔐 Simulación de phishing educativo</p>
    </body>
    </html>
    """
    
    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = target_email
    msg['Subject'] = "🔐 Tu cuenta requiere atención urgente"
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Error enviando a {target_email}: {e}")
        return False

# ============ FUNCIONES DE REPORTES ============
def generate_report_pdf(stats, victims):
    """Genera PDF con el reporte completo"""
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
    stats_data = [
        ['Metric', 'Value'],
        ['Total Victims', str(stats.get('total_victims', 0))],
        ['Total Campaigns', str(stats.get('total_campaigns', 0))],
        ['Total Clicks', str(stats.get('total_clicks', 0))],
        ['Conversion Rate', f"{stats.get('conversion_rate', 0)}%"]
    ]
    
    table = Table(stats_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#0052cc')),
        ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# ============ RUTAS PRINCIPALES ============

# Ruta principal (login falso)
@app.route('/')
def index():
    return render_template('login.html')

# Captura de credenciales
@app.route('/login', methods=['POST'])
def fake_login():
    email = request.form['email']
    password = request.form['password']
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    campaign = Campaign.query.first()
    
    victim = Victim(
        email=email,
        password=password,
        ip=ip,
        user_agent=user_agent,
        campaign_id=campaign.id if campaign else None
    )
    db.session.add(victim)
    db.session.commit()
    
    if campaign:
        campaign.click_count += 1
        db.session.commit()
    
    # Enviar notificaciones en hilos separados
    threading.Thread(target=slack.send_new_victim_alert, args=(victim,)).start()
    threading.Thread(target=send_webhook, args=('new_victim', {
        'email': victim.email,
        'ip': victim.ip,
        'timestamp': victim.timestamp.isoformat()
    })).start()
    
    return render_template('training.html', email=email)

# Dashboard
@app.route('/dashboard')
@auth.login_required
def dashboard():
    victims = Victim.query.all()
    campaigns = Campaign.query.all()
    
    # Datos para gráficas
    daily_data = {}
    for v in victims:
        date_str = v.timestamp.strftime('%Y-%m-%d')
        daily_data[date_str] = daily_data.get(date_str, 0) + 1
    
    today = datetime.now().date()
    new_victims_today = sum(1 for v in victims if v.timestamp.date() == today)
    
    stats = {
        'total_victims': len(victims),
        'total_campaigns': len(campaigns),
        'total_clicks': sum(c.click_count for c in campaigns),
        'new_victims_today': new_victims_today,
        'daily_data': daily_data
    }
    
    return render_template('dashboard.html', stats=stats, victims=victims)

# API para estadísticas
@app.route('/api/stats')
@auth.login_required
def api_stats():
    victims_count = Victim.query.count()
    today = datetime.now().date()
    new_today = Victim.query.filter(Victim.timestamp >= today).count()
    campaign = Campaign.query.first()
    
    return jsonify({
        'total_caidos': victims_count,
        'nuevos_hoy': new_today,
        'total_envios': campaign.sent_count if campaign else 0,
        'tasa_conversion': round(victims_count / (campaign.sent_count or 1) * 100, 2) if campaign else 0,
        'timestamp': datetime.now().isoformat()
    })

# Nueva campaña
@app.route('/campaign/new', methods=['GET', 'POST'])
@auth.login_required
def new_campaign():
    if request.method == 'POST':
        campaign = Campaign(
            name=request.form['name'],
            subject=request.form.get('subject', ''),
            template=request.form.get('template', '')
        )
        db.session.add(campaign)
        db.session.commit()
        return redirect('/dashboard')
    return render_template('campaign_form.html')

# Rastreador de clics
@app.route('/track')
def track_click():
    email = request.args.get('email')
    if email:
        print(f"🔍 [TRACK] Usuario {email} hizo clic")
    return redirect('/')

# Envío de campaña
@app.route('/send_campaign', methods=['POST'])
@auth.login_required
@limiter.limit("10 per minute")
def send_campaign():
    data = request.json
    targets = data.get('targets', [])
    
    results = {'sent': 0, 'failed': 0, 'errors': []}
    
    campaign = Campaign.query.first()
    if campaign:
        campaign.sent_count += len(targets)
        db.session.commit()
    
    for target in targets[:100]:
        can_send, message = email_rate_limiter.can_send()
        if not can_send:
            results['errors'].append(message)
            break
        
        success = send_phishing_email(target['email'], target.get('name', 'Usuario'), "http://localhost:5000/track")
        if success:
            results['sent'] += 1
            email_rate_limiter.record_send()
        else:
            results['failed'] += 1
    
    threading.Thread(target=send_webhook, args=('campaign', {
        'campaign_name': data.get('campaign_name', 'Sin nombre'),
        'results': results
    })).start()
    
    return jsonify(results)

# Exportar PDF
@app.route('/export/pdf')
@auth.login_required
def export_pdf():
    victims = Victim.query.all()
    campaigns = Campaign.query.all()
    
    stats = {
        'total_victims': len(victims),
        'total_campaigns': len(campaigns),
        'total_clicks': sum(c.click_count for c in campaigns),
        'conversion_rate': round(len(victims) / (campaigns[0].sent_count or 1) * 100, 2) if campaigns else 0
    }
    
    pdf_buffer = generate_report_pdf(stats, victims)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"mxphish_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype='application/pdf'
    )

# Enviar reporte por email
@app.route('/send_report', methods=['POST'])
@auth.login_required
def send_report_route():
    period = request.json.get('period', 'daily')
    extra_emails = request.json.get('extra_emails')
    
    victims = Victim.query.all()
    campaigns = Campaign.query.all()
    
    today = datetime.now().date()
    new_victims = sum(1 for v in victims if v.timestamp.date() == today)
    
    stats = {
        'total_victims': len(victims),
        'new_victims': new_victims,
        'total_campaigns': len(campaigns),
        'total_clicks': sum(c.click_count for c in campaigns),
        'conversion_rate': round(len(victims) / (campaigns[0].sent_count or 1) * 100, 2) if campaigns else 0
    }
    
    success = reporter.send_report(stats, victims[-30:], period, extra_emails)
    
    # Enviar webhook de reporte diario
    if period == 'daily':
        threading.Thread(target=send_webhook, args=('daily_report', stats)).start()
    
    return jsonify({'success': success, 'message': 'Reporte enviado' if success else 'Error al enviar'})

# Probar Slack
@app.route('/test_slack', methods=['GET'])
@auth.login_required
def test_slack():
    success = slack.send_message("🧪 *Test de conexión MX-PHISH* - La integración con Slack funciona correctamente!", color="good")
    return jsonify({'success': success, 'message': 'Test enviado a Slack' if success else 'Error de conexión'})

# Configuración de Webhook
@app.route('/api/webhook/config', methods=['GET', 'POST'])
@auth.login_required
def webhook_config():
    if request.method == 'POST':
        config = request.json
        save_webhook_config(config)
        return jsonify({'success': True, 'message': 'Configuración guardada'})
    else:
        config = load_webhook_config()
        return jsonify(config or {})

# Probar Webhook
@app.route('/api/webhook/test', methods=['POST'])
@auth.login_required
def webhook_test():
    url = request.json.get('url')
    if not url:
        return jsonify({'success': False, 'message': 'URL requerida'})
    
    test_payload = {
        'event': 'test',
        'message': 'Prueba de conexión MX-PHISH',
        'timestamp': datetime.now().isoformat()
    }
    
    try:
        response = requests.post(url, json=test_payload, timeout=5)
        return jsonify({'success': True, 'status_code': response.status_code})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Programar reportes automáticos
@app.route('/schedule_reports', methods=['POST'])
@auth.login_required
def schedule_reports():
    def daily_report_job():
        victims = Victim.query.all()
        campaigns = Campaign.query.all()
        today = datetime.now().date()
        new_victims = sum(1 for v in victims if v.timestamp.date() == today)
        
        stats = {
            'total_victims': len(victims),
            'new_victims': new_victims,
            'total_campaigns': len(campaigns),
            'total_clicks': sum(c.click_count for c in campaigns),
            'conversion_rate': round(len(victims) / (campaigns[0].sent_count or 1) * 100, 2) if campaigns else 0
        }
        
        reporter.send_report(stats, victims[-30:], "daily")
        slack.send_daily_summary(stats)
        send_webhook('daily_report', stats)
    
    # Ejecutar en hilo separado (simplificado, en producción usar APScheduler)
    import schedule
    schedule.every().day.at("09:00").do(daily_report_job)
    
    def run_scheduler():
        while True:
            schedule.run_pending()
            import time
            time.sleep(60)
    
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    return jsonify({'success': True, 'message': 'Reportes programados para las 9:00 AM'})

# Página de login del dashboard
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login_page():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users.get(username), password):
            # En producción usar sesiones, aquí simplificado
            return redirect('/dashboard')
        return render_template('admin_login.html', error="Credenciales inválidas")
    return render_template('admin_login.html')

# ============ MAIN ============
if __name__ == '__main__':
    # Para desarrollo
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    # Para producción con HTTPS (descomentar y usar)
    # app.run(debug=False, host='0.0.0.0', port=443, ssl_context=('cert.pem', 'key.pem'))
