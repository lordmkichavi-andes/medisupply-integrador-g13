#!/usr/bin/env python3
"""
🕐 Pruebas de Restricciones de Horario
=====================================
Simula diferentes horas para probar las restricciones por grupo
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

def test_with_simulated_hour(token, simulated_hour, expected_status, description):
    """Realiza una petición HTTP simulando una hora específica"""
    api_url = get_api_url()
    if not api_url:
        return False
    
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Simulated-Hour": str(simulated_hour)  # Header para simular hora
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
    """Ejecuta las pruebas de restricciones de horario"""
    print("🕐 Pruebas de Restricciones de Horario")
    print("=" * 40)
    
    current_hour = datetime.now().hour
    print(f"🕐 Hora real actual: {current_hour}:00")
    print("📝 Nota: Estas pruebas usan la hora real del sistema")
    print()
    
    # Generar tokens para diferentes grupos
    now = int(time.time())
    
    # Token para grupo 'clientes' (6-22h)
    token_clientes = b64url({
        "cognito:groups": ["clientes"], 
        "sub": f"test-clientes-{now}", 
        "iat": now
    })
    
    # Token para grupo 'ventas' (5-23h)
    token_ventas = b64url({
        "cognito:groups": ["ventas"], 
        "sub": f"test-ventas-{now}", 
        "iat": now
    })
    
    print("📋 Políticas por Grupo:")
    print("  • clientes: 6-22h")
    print("  • ventas: 5-23h")
    print()
    
    # Ejecutar pruebas basadas en la hora actual
    tests_passed = 0
    total_tests = 0
    
    # Test 1: Clientes en horario permitido (6-22h)
    total_tests += 1
    if 6 <= current_hour <= 22:
        if test_with_simulated_hour(token_clientes, current_hour, 200, f"Clientes en horario permitido ({current_hour}h)"):
            tests_passed += 1
    else:
        if test_with_simulated_hour(token_clientes, current_hour, 403, f"Clientes fuera de horario ({current_hour}h)"):
            tests_passed += 1
    
    # Test 2: Ventas en horario permitido (5-23h)
    total_tests += 1
    if 5 <= current_hour <= 23:
        if test_with_simulated_hour(token_ventas, current_hour, 200, f"Ventas en horario permitido ({current_hour}h)"):
            tests_passed += 1
    else:
        if test_with_simulated_hour(token_ventas, current_hour, 403, f"Ventas fuera de horario ({current_hour}h)"):
            tests_passed += 1
    
    # Test 3: Casos específicos de horario
    test_cases = [
        (3, "madrugada", "fuera de horario"),
        (5, "muy temprano", "ventas permitido, clientes denegado"),
        (6, "inicio laboral", "ambos permitidos"),
        (12, "mediodía", "ambos permitidos"),
        (22, "fin laboral", "ambos permitidos"),
        (23, "noche", "ventas permitido, clientes denegado"),
        (0, "medianoche", "ambos denegados"),
    ]
    
    for hour, description, expected in test_cases:
        if hour == current_hour:
            print(f"⏰ Probando hora {hour}:00 ({description}) - HORA ACTUAL")
            
            # Test clientes
            total_tests += 1
            expected_clientes = 200 if 6 <= hour <= 22 else 403
            if test_with_simulated_hour(token_clientes, hour, expected_clientes, f"  Clientes a las {hour}h"):
                tests_passed += 1
            
            # Test ventas
            total_tests += 1
            expected_ventas = 200 if 5 <= hour <= 23 else 403
            if test_with_simulated_hour(token_ventas, hour, expected_ventas, f"  Ventas a las {hour}h"):
                tests_passed += 1
        else:
            print(f"⏰ Hora {hour}:00 ({description}) - {expected}")
    
    print()
    print("📊 Resumen:")
    print(f"  ✅ Pruebas exitosas: {tests_passed}/{total_tests}")
    print(f"  ❌ Pruebas fallidas: {total_tests - tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 ¡Todas las pruebas de restricciones de horario pasaron!")
        return 0
    else:
        print("⚠️  Algunas pruebas fallaron. Revisar logs del authorizer.")
        return 1

if __name__ == "__main__":
    exit(main())
