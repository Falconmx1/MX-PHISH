from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv

load_dotenv()
auth = HTTPBasicAuth()

# Usuarios autorizados (puedes agregar más)
users = {
    "admin": generate_password_hash(os.getenv('DASHBOARD_PASSWORD', 'MX-PHISH2024')),
    "security_team": generate_password_hash(os.getenv('SECURITY_TEAM_PASSWORD', 'PhishSim2024'))
}

@auth.verify_password
def verify_password(username, password):
    if username in users and check_password_hash(users.get(username), password):
        return username
    return None
