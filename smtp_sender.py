import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv

load_dotenv()

def send_phishing_email(target_email, name, tracking_url):
    """Envía correo de phishing simulado"""
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT'))
    smtp_user = os.getenv('SMTP_USER')
    smtp_password = os.getenv('SMTP_PASSWORD')
    
    # Plantilla convincente
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif;">
        <h2>⚠️ Acción requerida: Tu contraseña expira hoy</h2>
        <p>Hola {name},</p>
        <p>El sistema ha detectado que tu contraseña <strong>expirará en 24 horas</strong>.</p>
        <p>Para evitar la pérdida de acceso, haz clic en el siguiente enlace:</p>
        <p><a href="{tracking_url}" style="background-color: #0052cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Mantener mi contraseña</a></p>
        <hr>
        <p style="color: gray; font-size: 12px;">🔐 Simulación de phishing educativo - No compartas tus credenciales</p>
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

# Lista de targets (ejemplo)
test_targets = [
    {"email": "empleado1@tuempresa.com", "name": "Carlos"},
    {"email": "empleado2@tuempresa.com", "name": "Ana"},
]

def run_campaign(tracking_base_url="http://localhost:5000/track"):
    for target in test_targets:
        tracking_url = f"{tracking_base_url}?email={target['email']}"
        send_phishing_email(target['email'], target['name'], tracking_url)
