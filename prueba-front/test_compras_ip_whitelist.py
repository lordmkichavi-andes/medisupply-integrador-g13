#!/usr/bin/env python3
"""
🏢 Pruebas de Validación de IP Whitelist para Grupo Compras
===========================================================
Prueba las restricciones de IP whitelist para el grupo 'compras'
"""

import base64
import json
import subprocess
import time
import urllib.request
from datetime import datetime

def get_api_url():
    """Obtiene la URL del API Gateway"""
    try:
        output = subprocess.check_output([
            "aws", "cloudformation", "describe-stacks",
            "--stack-name", "MediSupplyStack",
            "--query", "Stacks[0].Outputs[?starts_with(OutputKey,'MediSupplyAPIEndpoint')].OutputValue",
            "--output", "text"
        ]).decode('utf-8').strip()
        return output.rstrip('/') + '/products'
    except Exception as e:
        print(f"Error getting API URL: {e}")
        return None

def b64url(payload_dict):
    """Genera JWT con algoritmo 'none' para pruebas"""
    header = {"alg": "none", "typ": "JWT"}
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip('=')
    return f"{enc(header)}.{enc(payload_dict)}."

def test_with_ip_simulation(token, simulated_ip, expected_status, description):
    """Realiza una petición HTTP simulando una IP específica"""
    api_url = get_api_url()
    if not api_url:
        return False
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Test-IP": simulated_ip,  # Header personalizado para pruebas
        "X-Forwarded-For": simulated_ip,
        "X-Real-IP": simulated_ip,
        "X-Client-IP": simulated_ip
    }
    
    try:
        req = urllib.request.Request(api_url, method='GET', headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.getcode()
            print(f"✅ {description}: HTTP {status_code} (esperado {expected_status})")
            return status_code == expected_status
    except urllib.error.HTTPError as e:
        status_code = e.code
        print(f"✅ {description}: HTTP {status_code} (esperado {expected_status})")
        return status_code == expected_status
    except Exception as e:
        print(f"❌ {description}: Error - {e}")
        return False

def main():
    """Ejecuta las pruebas de validación de IP whitelist para compras"""
    print("🏢 Pruebas de Validación de IP Whitelist - Grupo Compras")
    print("=" * 60)
    print("📝 Política del grupo 'compras':")
    print("   • Países: CO, PE, EC, MX")
    print("   • Horario: 6:00-22:00")
    print("   • IP Whitelist: 10.0.0.0/8 (solo red corporativa)")
    print()
    
    # Generar token para grupo 'compras'
    now = int(time.time())
    token_compras = b64url({
        "cognito:groups": ["compras"], 
        "sub": f"test-compras-{now}", 
        "iat": now
    })
    
    # IPs de prueba
    test_ips = {
        "Red Corporativa (10.0.1.1)": "10.0.1.1",      # ✅ Permitida
        "Red Corporativa (10.255.255.1)": "10.255.255.1", # ✅ Permitida
        "IP Pública (8.8.8.8)": "8.8.8.8",             # ❌ No permitida
        "IP Pública (190.14.255.110)": "190.14.255.110", # ❌ No permitida
        "IP Local (192.168.1.1)": "192.168.1.1",       # ❌ No permitida
        "IP Pública (1.1.1.1)": "1.1.1.1"              # ❌ No permitida
    }
    
    print("🧪 Pruebas de IP Whitelist para Grupo Compras:")
    print()
    
    tests_passed = 0
    total_tests = 0
    
    for description, ip in test_ips.items():
        total_tests += 1
        
        # Determinar resultado esperado
        if ip.startswith("10."):
            expected_status = 200  # IPs de red corporativa deben ser permitidas
        else:
            expected_status = 403  # IPs públicas deben ser denegadas
        
        if test_with_ip_simulation(token_compras, ip, expected_status, f"  {description}"):
            tests_passed += 1
    
    print()
    print("📊 Resumen:")
    print(f"  ✅ Pruebas exitosas: {tests_passed}/{total_tests}")
    print(f"  ❌ Pruebas fallidas: {total_tests - tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 ¡Todas las pruebas de IP whitelist pasaron!")
        print("✅ La validación de IP whitelist está funcionando correctamente.")
        return 0
    else:
        print("⚠️  Algunas pruebas fallaron.")
        print("🔍 Revisar logs del authorizer para más detalles.")
        return 1

if __name__ == "__main__":
    exit(main())
