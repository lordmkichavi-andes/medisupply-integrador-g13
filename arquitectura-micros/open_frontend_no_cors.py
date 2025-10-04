#!/usr/bin/env python3
"""
Script para abrir el frontend con CORS deshabilitado (solo para testing)
"""

import subprocess
import sys
import os

def open_chrome_no_cors():
    """Abrir Chrome con CORS deshabilitado"""
    
    frontend_url = "https://dl8uc6ciglyo6.cloudfront.net"
    
    # Comando para abrir Chrome con CORS deshabilitado
    chrome_cmd = [
        "open", "-a", "Google Chrome",
        "--args",
        "--disable-web-security",
        "--disable-features=VizDisplayCompositor",
        "--user-data-dir=/tmp/chrome_dev_test",
        frontend_url
    ]
    
    try:
        print("🚀 Abriendo Chrome con CORS deshabilitado...")
        print(f"📱 Frontend: {frontend_url}")
        print("⚠️  IMPORTANTE: Solo para testing. Cierra esta ventana cuando termines.")
        
        subprocess.run(chrome_cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error abriendo Chrome: {e}")
        print("\n🔧 Alternativa manual:")
        print("1. Abre Chrome")
        print("2. Ve a: chrome://flags/#disable-web-security")
        print("3. Habilita 'Disable web security'")
        print("4. Reinicia Chrome")
        print(f"5. Ve a: {frontend_url}")

if __name__ == "__main__":
    open_chrome_no_cors()
