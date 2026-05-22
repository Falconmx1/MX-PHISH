from flask import Flask, render_template, request, redirect, url_for, jsonify
from database import db, Victim, Campaign
from smtp_sender import send_phishing_email
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///phish_sim.db'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db.init_app(app)

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
    
    # Actualizar contador de clics en campaña activa
    campaign = Campaign.query.first()
    if campaign:
        campaign.click_count += 1
        db.session.commit()
    
    return render_template('training.html', email=email)

# DASHBOARD - Estadísticas
@app.route('/dashboard')
def dashboard():
    victims = Victim.query.all()
    campaigns = Campaign.query.all()
    
    stats = {
        'total_victims': len(victims),
        'total_campaigns': len(campaigns),
        'total_clicks': sum(c.click_count for c in campaigns),
        'recent_victims': victims[-10:][::-1]  # últimos 10
    }
    return render_template('dashboard.html', stats=stats, victims=victims)

# API para datos en JSON
@app.route('/api/stats')
def api_stats():
    victims_count = Victim.query.count()
    return jsonify({
        'total_caidos': victims_count,
        'total_envios': Campaign.query.first().sent_count if Campaign.query.first() else 0,
        'tasa_conversion': round(victims_count / (Campaign.query.first().sent_count or 1) * 100, 2)
    })

# Formulario para crear campaña
@app.route('/campaign/new', methods=['GET', 'POST'])
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
        # Registrar clic educativo
        print(f"🔍 [TRACK] Usuario {email} hizo clic en el enlace falso")
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
