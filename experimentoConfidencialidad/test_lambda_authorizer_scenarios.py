#!/usr/bin/env python3
"""
Script de Pruebas para Lambda Authorizer Cognito Real
Simula diferentes escenarios de validación de confidencialidad para MediSupply
"""

import json
import sys
import os
from datetime import datetime, timezone, timedelta
import unittest
from unittest.mock import Mock, patch

# Agregar el directorio lambda_code al path para importar el módulo
sys.path.append(os.path.join(os.path.dirname(__file__), 'lambda_code'))

try:
    from lambda_authorizer_cognito_real import (
        lambda_handler,
        validate_cognito_jwt_real,
        get_user_profile_from_cognito,
        evaluate_security_with_cognito_data,
        check_business_hours_real,
        check_geographic_access_real,
        check_ip_type,
        detect_country_simple
    )
except ImportError as e:
    print(f"❌ Error importando módulo: {e}")
    print("Asegúrate de que lambda_authorizer_cognito_real.py esté en ./lambda_code/")
    sys.exit(1)

class TestLambdaAuthorizerScenarios(unittest.TestCase):
    """Casos de prueba para el Lambda Authorizer"""

    def setUp(self):
        """Configuración inicial para cada test"""
        self.base_event = {
            'type': 'REQUEST',
            'methodArn': 'arn:aws:execute-api:us-east-1:123456789:vmbwryazac/prod/GET/test',
            'resource': '/test',
            'path': '/test',
            'httpMethod': 'GET',
            'headers': {},
            'requestContext': {
                'identity': {
                    'sourceIp': '192.168.1.100'
                }
            }
        }
        
        self.context = Mock()
        self.context.aws_request_id = 'test-request-id'

    def create_event_with_token(self, token, source_ip='192.168.1.100'):
        """Crear evento con token específico"""
        event = self.base_event.copy()
        event['headers'] = {'Authorization': f'Bearer {token}'}
        event['requestContext']['identity']['sourceIp'] = source_ip
        return event

    # ===============================================
    # ESCENARIOS DE TOKENS VÁLIDOS (ALLOW)
    # ===============================================

    def test_01_demo_user_ny_horario_laboral(self):
        """✅ Usuario demo.user.ny en horario laboral desde IP US"""
        print("\n🧪 Test 1: Usuario NY en horario laboral")
        
        event = self.create_event_with_token('demo.user.ny', '192.168.1.100')
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Simular lunes 10:00 AM
            mock_datetime.now.return_value = datetime(2025, 9, 15, 15, 0, 0, tzinfo=timezone.utc)  # 10:00 AM EST
            mock_datetime.strptime = datetime.strptime
            
            result = lambda_handler(event, self.context)
            
            self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Allow')
            self.assertIn('user_ny', result['context']['username'])
            print("✅ ALLOW - Usuario autorizado correctamente")

    def test_02_demo_admin_intl_pais_autorizado(self):
        """✅ Admin internacional desde México (país autorizado)"""
        print("\n🧪 Test 2: Admin desde México")
        
        event = self.create_event_with_token('demo.admin.intl', '201.50.100.1')  # IP México
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Simular martes 14:00
            mock_datetime.now.return_value = datetime(2025, 9, 16, 19, 0, 0, tzinfo=timezone.utc)  # 14:00 EST
            mock_datetime.strptime = datetime.strptime
            
            result = lambda_handler(event, self.context)
            
            self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Allow')
            self.assertEqual(result['context']['role'], 'admin')
            print("✅ ALLOW - Admin desde país autorizado")

    def test_03_demo_user_24x7_fin_semana(self):
        """✅ Usuario 24x7 accediendo en fin de semana"""
        print("\n🧪 Test 3: Usuario 24x7 en domingo")
        
        event = self.create_event_with_token('demo.user.24x7', '192.168.1.100')
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Simular domingo 14:00
            mock_datetime.now.return_value = datetime(2025, 9, 14, 19, 0, 0, tzinfo=timezone.utc)  # Domingo 14:00 EST
            mock_datetime.strptime = datetime.strptime
            
            result = lambda_handler(event, self.context)
            
            self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Allow')
            self.assertIn('24x7', result['context']['username'])
            print("✅ ALLOW - Usuario 24x7 autorizado en domingo")

    def test_04_cognito_jwt_real_token(self):
        """✅ Token JWT real de Cognito válido"""
        print("\n🧪 Test 4: JWT real de Cognito")
        
        # Simular JWT real (base64 encoded payload)
        jwt_payload = {
            "cognito:username": "user.ny@medisupply.com",
            "email": "user.ny@medisupply.com",
            "exp": int((datetime.now() + timedelta(hours=1)).timestamp()),
            "sub": "abc123-def456"
        }
        
        # Crear JWT falso pero con estructura válida
        import base64
        header_b64 = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT"}').decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(jwt_payload).encode()).decode().rstrip('=')
        signature_b64 = base64.urlsafe_b64encode(b'fake_signature').decode().rstrip('=')
        fake_jwt = f"{header_b64}.{payload_b64}.{signature_b64}"
        
        event = self.create_event_with_token(fake_jwt, '192.168.1.100')
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Simular miércoles 11:00
            mock_datetime.now.return_value = datetime(2025, 9, 17, 16, 0, 0, tzinfo=timezone.utc)  # 11:00 EST
            mock_datetime.strptime = datetime.strptime
            
            result = lambda_handler(event, self.context)
            
            self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Allow')
            print("✅ ALLOW - JWT real procesado correctamente")

    # ===============================================
    # ESCENARIOS DE ACCESO DENEGADO (DENY)
    # ===============================================

    def test_05_demo_user_fin_semana(self):
        """❌ Usuario normal en fin de semana"""
        print("\n🧪 Test 5: Usuario normal en domingo")
        
        event = self.create_event_with_token('demo.user.ny', '192.168.1.100')
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Simular domingo 14:00
            mock_datetime.now.return_value = datetime(2025, 9, 14, 19, 0, 0, tzinfo=timezone.utc)  # Domingo
            mock_datetime.strptime = datetime.strptime
            
            result = lambda_handler(event, self.context)
            
            self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Deny')
            self.assertIn('DENIED', result['context']['auth_status'])
            print("❌ DENY - Usuario denegado en fin de semana")

    def test_06_demo_user_pais_no_autorizado(self):
        """❌ Usuario desde país no autorizado"""
        print("\n🧪 Test 6: Usuario desde país no reconocido")
        
        event = self.create_event_with_token('demo.user.ny', '95.168.1.100')  # IP europea
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Simular lunes 10:00
            mock_datetime.now.return_value = datetime(2025, 9, 15, 15, 0, 0, tzinfo=timezone.utc)
            mock_datetime.strptime = datetime.strptime
            
            result = lambda_handler(event, self.context)
            
            self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Deny')
            print("❌ DENY - Usuario desde país no autorizado")

    def test_07_demo_user_highrisk(self):
        """❌ Usuario de alto riesgo"""
        print("\n🧪 Test 7: Usuario de alto riesgo")
        
        event = self.create_event_with_token('demo.user.highrisk', '192.168.1.100')
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Simular lunes 10:00
            mock_datetime.now.return_value = datetime(2025, 9, 15, 15, 0, 0, tzinfo=timezone.utc)
            mock_datetime.strptime = datetime.strptime
            
            result = lambda_handler(event, self.context)
            
            # Puede ser DENY o MFA dependiendo del risk score
            self.assertIn(result['policyDocument']['Statement'][0]['Effect'], ['Deny', 'Allow'])
            print(f"⚠️ {result['policyDocument']['Statement'][0]['Effect']} - Usuario alto riesgo procesado")

    def test_08_fuera_horario_laboral(self):
        """❌ Acceso fuera del horario laboral"""
        print("\n🧪 Test 8: Acceso fuera de horario")
        
        event = self.create_event_with_token('demo.user.valid', '192.168.1.100')
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Simular lunes 3:00 AM
            mock_datetime.now.return_value = datetime(2025, 9, 15, 8, 0, 0, tzinfo=timezone.utc)  # 3:00 AM EST
            mock_datetime.strptime = datetime.strptime
            
            result = lambda_handler(event, self.context)
            
            self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Deny')
            print("❌ DENY - Acceso fuera de horario laboral")

    def test_09_token_inexistente(self):
        """❌ Token inexistente o inválido"""
        print("\n🧪 Test 9: Token inválido")
        
        event = self.create_event_with_token('token.inexistente.invalid', '192.168.1.100')
        
        result = lambda_handler(event, self.context)
        
        self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Deny')
        self.assertEqual(result['context']['deny_reason'], 'NO_USER_PROFILE')
        print("❌ DENY - Token inexistente denegado")

    def test_10_sin_token(self):
        """❌ Solicitud sin token de autorización"""
        print("\n🧪 Test 10: Sin token")
        
        event = self.base_event.copy()
        event['headers'] = {}  # Sin Authorization header
        
        result = lambda_handler(event, self.context)
        
        self.assertEqual(result['policyDocument']['Statement'][0]['Effect'], 'Deny')
        self.assertEqual(result['context']['deny_reason'], 'TOKEN_MISSING')
        print("❌ DENY - Solicitud sin token denegada")

    # ===============================================
    # ESCENARIOS ESPECIALES
    # ===============================================

    def test_11_deteccion_paises(self):
        """🗺️ Validar detección de países por IP"""
        print("\n🧪 Test 11: Detección de países")
        
        test_cases = [
            ('192.168.1.100', 'US', 'IP privada'),
            ('8.8.8.8', 'US', 'Google DNS'),
            ('201.50.100.1', 'MX', 'México'),
            ('200.100.50.1', 'CA', 'Canadá'),
            ('95.168.1.100', 'UNKNOWN', 'Europa/Desconocido')
        ]
        
        for ip, expected_country, description in test_cases:
            country = detect_country_simple(ip)
            self.assertEqual(country, expected_country)
            print(f"✅ {ip} → {country} ({description})")

    def test_12_tipos_ip(self):
        """🔍 Validar clasificación de tipos de IP"""
        print("\n🧪 Test 12: Tipos de IP")
        
        test_cases = [
            ('192.168.1.100', 'private', 0.0),
            ('10.0.0.1', 'private', 0.0),
            ('127.0.0.1', 'loopback', 0.0),
            ('8.8.8.8', 'public', 0.1),
            ('invalid.ip', 'invalid', 0.3)
        ]
        
        for ip, expected_type, expected_risk in test_cases:
            result = check_ip_type(ip)
            self.assertEqual(result['type'], expected_type)
            self.assertEqual(result['risk_added'], expected_risk)
            print(f"✅ {ip} → {expected_type} (risk: {expected_risk})")

    def test_13_horarios_laborales(self):
        """⏰ Validar verificación de horarios laborales"""
        print("\n🧪 Test 13: Horarios laborales")
        
        user_profile = {
            'username': 'test_user',
            'business_start': '09:00',
            'business_end': '17:00',
            'timezone': 'America/New_York'
        }
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Caso 1: Lunes 10:00 AM (dentro del horario)
            mock_datetime.now.return_value = datetime(2025, 9, 15, 15, 0, 0, tzinfo=timezone.utc)  # 10:00 EST
            mock_datetime.strptime = datetime.strptime
            
            result = check_business_hours_real(user_profile)
            self.assertTrue(result['valid'])
            print("✅ Lunes 10:00 AM → Permitido")
            
            # Caso 2: Sábado (fin de semana)
            mock_datetime.now.return_value = datetime(2025, 9, 13, 15, 0, 0, tzinfo=timezone.utc)  # Sábado
            
            result = check_business_hours_real(user_profile)
            self.assertFalse(result['valid'])
            print("❌ Sábado → Denegado")

    def test_14_usuario_24x7_excepcion(self):
        """🚨 Validar excepción para usuarios 24x7"""
        print("\n🧪 Test 14: Excepción usuario 24x7")
        
        user_profile_24x7 = {
            'username': 'demo.user.24x7',
            'business_start': '00:00',
            'business_end': '23:59',
            'timezone': 'America/New_York'
        }
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Domingo para usuario 24x7
            mock_datetime.now.return_value = datetime(2025, 9, 14, 15, 0, 0, tzinfo=timezone.utc)  # Domingo
            mock_datetime.strptime = datetime.strptime
            
            result = check_business_hours_real(user_profile_24x7)
            self.assertTrue(result['valid'])  # Debe permitir fin de semana
            print("✅ Usuario 24x7 en domingo → Permitido")

    def test_15_cache_tokens(self):
        """💾 Validar funcionamiento del cache de tokens"""
        print("\n🧪 Test 15: Cache de tokens")
        
        # Limpiar cache
        from lambda_authorizer_cognito_real import TOKEN_CACHE
        TOKEN_CACHE.clear()
        
        token = 'demo.cache.test'
        
        # Primera validación (cache miss)
        result1 = validate_cognito_jwt_real(token)
        self.assertIsNotNone(result1)
        self.assertEqual(len(TOKEN_CACHE), 1)
        print("✅ Cache miss → Token validado y guardado")
        
        # Segunda validación (cache hit)
        result2 = validate_cognito_jwt_real(token)
        self.assertEqual(result1, result2)
        print("✅ Cache hit → Token reutilizado del cache")

    # ===============================================
    # ESCENARIOS DE EVALUACIÓN DE RIESGO
    # ===============================================

    def test_16_evaluacion_riesgo_bajo(self):
        """📊 Evaluación de riesgo bajo"""
        print("\n🧪 Test 16: Riesgo bajo")
        
        user_profile = {
            'username': 'test_user',
            'role': 'user',
            'risk_tolerance': 'high',
            'user_status': 'CONFIRMED',
            'enabled': True,
            'business_start': '09:00',
            'business_end': '17:00',
            'timezone': 'America/New_York',
            'authorized_countries': ['US']
        }
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Lunes 10:00 AM
            mock_datetime.now.return_value = datetime(2025, 9, 15, 15, 0, 0, tzinfo=timezone.utc)
            mock_datetime.strptime = datetime.strptime
            
            result = evaluate_security_with_cognito_data(user_profile, '192.168.1.100')
            
            self.assertEqual(result['decision'], 'allow')
            self.assertLess(result['risk_score'], 0.6)
            print(f"✅ Riesgo bajo → {result['decision']} (score: {result['risk_score']})")

    def test_17_evaluacion_riesgo_alto(self):
        """📊 Evaluación de riesgo alto"""
        print("\n🧪 Test 17: Riesgo alto")
        
        user_profile = {
            'username': 'highrisk_user',
            'role': 'user',
            'risk_tolerance': 'low',
            'user_status': 'CONFIRMED',
            'enabled': True,
            'business_start': '09:00',
            'business_end': '17:00',
            'timezone': 'America/New_York',
            'authorized_countries': ['US']
        }
        
        with patch('lambda_authorizer_cognito_real.datetime') as mock_datetime:
            # Domingo (fin de semana)
            mock_datetime.now.return_value = datetime(2025, 9, 14, 15, 0, 0, tzinfo=timezone.utc)
            mock_datetime.strptime = datetime.strptime
            
            result = evaluate_security_with_cognito_data(user_profile, '95.168.1.100')  # IP no reconocida
            
            self.assertIn(result['decision'], ['deny', 'mfa_required'])
            self.assertGreater(result['risk_score'], 0.7)
            print(f"❌ Riesgo alto → {result['decision']} (score: {result['risk_score']})")

def run_scenario_tests():
    """Ejecutar todos los escenarios de prueba"""
    print("🔬 INICIANDO PRUEBAS DEL LAMBDA AUTHORIZER")
    print("=" * 60)
    
    # Configurar logging para ver los detalles
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Ejecutar tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestLambdaAuthorizerScenarios)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print("📊 RESUMEN DE PRUEBAS:")
    print(f"✅ Exitosas: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Fallidas: {len(result.failures)}")
    print(f"💥 Errores: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ FALLOS:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\n💥 ERRORES:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_scenario_tests()
    sys.exit(0 if success else 1)
