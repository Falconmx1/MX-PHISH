from flask import Flask, request, render_template, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Base de datos para registrar víctimas educativas
def init_db():
    conn = sqlite3.connect('phish_sim.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS victims
                 (id INTEGER PRIMARY KEY, email TEXT, password TEXT, ip TEXT, timestamp TEXT)''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('login.html')  # Página falsa de login

@app.route('/login', methods=['POST'])
def fake_login():
    email = request.form['email']
    password = request.form['password']
    ip = request.remote_addr
    
    # Guardar en BD (solo para simulación)
    conn = sqlite3.connect('phish_sim.db')
    c = conn.cursor()
    c.execute("INSERT INTO victims (email, password, ip, timestamp) VALUES (?,?,?,?)",
              (email, password, ip, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    # Redirige a training con concienciación
    return render_template('training.html', email=email)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
