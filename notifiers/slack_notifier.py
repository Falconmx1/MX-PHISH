import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class SlackNotifier:
    def __init__(self):
        self.webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.channel = os.getenv('SLACK_CHANNEL', '#security-alerts')
        
    def send_message(self, message, color="good"):
        """Envía un mensaje simple a Slack"""
        if not self.webhook_url:
            print("⚠️ SLACK_WEBHOOK_URL no configurado")
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
            response = requests.post(self.webhook_url, json=payload)
            if response.status_code == 200:
                print("✅ Mensaje enviado a Slack")
                return True
            else:
                print(f"❌ Error Slack: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error conectando con Slack: {e}")
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
        color = "good" if stats['new_victims'] < 5 else "warning" if stats['new_victims'] < 20 else "danger"
        
        message = f"""
        *📊 MX-PHISH Daily Summary*
        • Víctimas hoy: *{stats['new_victims']}* ({stats.get('trend', 'estable')})
        • Total acumulado: *{stats['total_victims']}*
        • Campañas activas: *{stats['total_campaigns']}*
        • Tasa de clics: *{stats.get('conversion_rate', 0)}%*
        
        {'⚠️ Alerta: Alta tasa de caídas detectada' if stats['new_victims'] > 10 else '✅ Sin anomalías significativas'}
        """
        return self.send_message(message, color=color)
    
    def send_campaign_report(self, campaign_name, results):
        """Reporte de campaña completada"""
        message = f"""
        *🎣 Campaña completada: {campaign_name}*
        • Envíos: *{results.get('sent', 0)}*
        • Entregados: *{results.get('delivered', 0)}*
        • Clics: *{results.get('clicks', 0)}*
        • Víctimas: *{results.get('victims', 0)}*
        • Tasa éxito: *{results.get('success_rate', 0)}%*
        """
        return self.send_message(message, color="info")

# Instancia global para usar en toda la app
slack = SlackNotifier()

def send_slack_alert(victim):
    """Función rápida para enviar alerta de nueva víctima"""
    return slack.send_new_victim_alert(victim)

def send_slack_summary(stats):
    """Función rápida para enviar resumen diario"""
    return slack.send_daily_summary(stats)
