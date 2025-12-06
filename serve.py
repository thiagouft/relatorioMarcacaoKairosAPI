from waitress import serve
from app import app
import socket

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    host = '0.0.0.0'
    port = 8080
    
    ip_address = get_ip_address()
    
    print(f"Starting server on {host}:{port}")
    print(f"Access locally at: http://localhost:{port}")
    print(f"Access from network at: http://{ip_address}:{port}")
    
    serve(app, host=host, port=port)
