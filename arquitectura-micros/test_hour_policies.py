#!/usr/bin/env python3
"""
🧪 Pruebas de Políticas de Horario por Grupo
============================================
Prueba las restricciones de horario implementadas en el authorizer
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

def test_request(token, expected_status, description):
    """Realiza una petición HTTP y valida el resultado"""
    api_url = get_api_url()
    if not api_url:
        return False
    
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
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
    """Ejecuta las pruebas de políticas de horario"""
    print("🧪 Pruebas de Políticas de Horario por Grupo")
    print("=" * 50)
    
    current_hour = datetime.now().hour
    print(f"🕐 Hora actual: {current_hour}:00")
    print()
    
    # Generar tokens para diferentes grupos
    now = int(time.time())
    
    # Token para grupo 'admin' (24/7)
    token_admin = b64url({
        "cognito:groups": ["admin"], 
        "sub": f"test-admin-{now}", 
        "iat": now
    })
    
    # Token para grupo 'clientes' (6-22h)
    token_clientes = b64url({
        "cognito:groups": ["clientes"], 
        "sub": f"test-clientes-{now}", 
        "iat": now
    })
    
    # Token para grupo 'compras' (6-22h)
    token_compras = b64url({
        "cognito:groups": ["compras"], 
        "sub": f"test-compras-{now}", 
        "iat": now
    })
    
    # Token para grupo 'ventas' (5-23h)
    token_ventas = b64url({
        "cognito:groups": ["ventas"], 
        "sub": f"test-ventas-{now}", 
        "iat": now
    })
    
    # Token sin grupos (siempre denegado)
    token_no_groups = b64url({
        "cognito:groups": [], 
        "sub": f"test-no-groups-{now}", 
        "iat": now
    })
    
    print("📋 Políticas por Grupo:")
    print("  • admin: 24/7 (0-23h)")
    print("  • clientes: 6-22h")
    print("  • compras: 6-22h")
    print("  • ventas: 5-23h")
    print()
    
    # Ejecutar pruebas
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Admin (siempre debe pasar)
    total_tests += 1
    if test_request(token_admin, 200, "Admin (24/7)"):
        tests_passed += 1
    
    # Test 2: Clientes (depende de la hora)
    total_tests += 1
    expected_clientes = 200 if 6 <= current_hour <= 22 else 403
    if test_request(token_clientes, expected_clientes, f"Clientes (6-22h, actual: {current_hour}h)"):
        tests_passed += 1
    
    # Test 3: Compras (depende de la hora)
    total_tests += 1
    expected_compras = 200 if 6 <= current_hour <= 22 else 403
    if test_request(token_compras, expected_compras, f"Compras (6-22h, actual: {current_hour}h)"):
        tests_passed += 1
    
    # Test 4: Ventas (depende de la hora)
    total_tests += 1
    expected_ventas = 200 if 5 <= current_hour <= 23 else 403
    if test_request(token_ventas, expected_ventas, f"Ventas (5-23h, actual: {current_hour}h)"):
        tests_passed += 1
    
    # Test 5: Sin grupos (siempre denegado)
    total_tests += 1
    if test_request(token_no_groups, 403, "Sin grupos (siempre denegado)"):
        tests_passed += 1
    
    # Test 6: Sin token (401)
    total_tests += 1
    if test_request(None, 401, "Sin token"):
        tests_passed += 1
    
    print()
    print("📊 Resumen:")
    print(f"  ✅ Pruebas exitosas: {tests_passed}/{total_tests}")
    print(f"  ❌ Pruebas fallidas: {total_tests - tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 ¡Todas las pruebas de políticas de horario pasaron!")
        return 0
    else:
        print("⚠️  Algunas pruebas fallaron. Revisar logs del authorizer.")
        return 1

if __name__ == "__main__":
    exit(main())
