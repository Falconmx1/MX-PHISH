# 🎣 MX-PHISH – Simulador de phishing ético

MX-PHISH es una herramienta educativa diseñada para ayudar a organizaciones y equipos de ciberseguridad a realizar campañas controladas de simulación de phishing. Su objetivo es medir la vulnerabilidad del factor humano frente a ataques de ingeniería social y mejorar la concienciación en seguridad.

⚠️ **Uso exclusivo para fines educativos y autorizados**. No me hago responsable del mal uso de esta herramienta.

## 🧠 Características
- 📧 Plantillas personalizables de correos de phishing.
- 🎯 Seguimiento de clics, aperturas y datos ingresados (en entorno controlado).
- 📊 Reportes descargables en PDF/CSV.
- 🧪 Modo "training" con retroalimentación para el usuario final.
- 🌐 Interfaz web sencilla para lanzar campañas.

## 🛠️ Tecnologías sugeridas
- Backend: Python (Flask) o Node.js.
- Frontend: HTML, CSS, JS.
- Base de datos: SQLite (para entornos pequeños).
- Envío de correos: SMTP con soporte para alias.

## 📦 Instalación rápida
```bash
git clone https://github.com/Falconmx1/MX-PHISH.git
cd MX-PHISH
pip install -r requirements.txt
python app.py
