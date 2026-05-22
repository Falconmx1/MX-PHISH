from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Límites específicos para envío de correos
email_limits = {
    "per_minute": 10,    # máximo 10 correos por minuto
    "per_hour": 100,     # máximo 100 por hora
    "per_day": 500       # máximo 500 por día
}

class EmailRateLimiter:
    def __init__(self):
        self.sent_counts = {
            'minute': [],
            'hour': [],
            'day': []
        }
    
    def can_send(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        
        # Limpiar registros antiguos
        self.sent_counts['minute'] = [t for t in self.sent_counts['minute'] if t > now - timedelta(minutes=1)]
        self.sent_counts['hour'] = [t for t in self.sent_counts['hour'] if t > now - timedelta(hours=1)]
        self.sent_counts['day'] = [t for t in self.sent_counts['day'] if t > now - timedelta(days=1)]
        
        # Verificar límites
        if len(self.sent_counts['minute']) >= email_limits['per_minute']:
            return False, "Límite por minuto alcanzado"
        if len(self.sent_counts['hour']) >= email_limits['per_hour']:
            return False, "Límite por hora alcanzado"
        if len(self.sent_counts['day']) >= email_limits['per_day']:
            return False, "Límite por día alcanzado"
        
        return True, "OK"
    
    def record_send(self):
        from datetime import datetime
        now = datetime.now()
        self.sent_counts['minute'].append(now)
        self.sent_counts['hour'].append(now)
        self.sent_counts['day'].append(now)

email_rate_limiter = EmailRateLimiter()
