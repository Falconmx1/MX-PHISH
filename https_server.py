from app import app
import ssl

if __name__ == '__main__':
    # Generar certificados autofirmados (solo pruebas)
    # openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('cert.pem', 'key.pem')
    
    app.run(host='0.0.0.0', port=443, ssl_context=context, debug=False)
