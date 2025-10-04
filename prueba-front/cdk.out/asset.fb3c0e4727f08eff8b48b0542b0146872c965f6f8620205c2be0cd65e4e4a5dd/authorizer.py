#!/usr/bin/env python3
"""
🔐 Lambda Autorizadora 
====================================================

"""

import json
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Definicion de Handler 
    """
    try:
        logger.info(f"Authorization request received: {event}")
        
        # 1. Obtener método HTTP para logging
        http_method = event.get('httpMethod', '')
        logger.info(f"Processing {http_method} request")
        
        # 2. Permitir peticiones OPTIONS (CORS preflight) sin autenticación
        if http_method == 'OPTIONS':
            logger.info("Allowing OPTIONS request for CORS preflight")
            return generate_policy_with_cors('cors-preflight', 'Allow', event['methodArn'])
        
        # 3. Obtener token del header Authorization (compatible con TOKEN y REQUEST authorizer)
        if event.get('type') == 'TOKEN':
            # Formato TOKEN authorizer
            token = event.get('authorizationToken', '')
            headers = {}
        else:
            # Formato REQUEST authorizer
            headers = event.get('headers', {})
            token = headers.get('Authorization', '')
        
        if not token.startswith('Bearer '):
            logger.warning("Missing or invalid Bearer token")
            return generate_policy('user', 'Deny', event['methodArn'])
        
        jwt_token = token[7:]  # Remover 'Bearer '
        
        # 3. Obtener IP del usuario desde headers personalizados
        # Priorizar X-Test-IP para pruebas, luego otros headers
        user_ip_raw = headers.get('X-Test-IP') or \
                      headers.get('X-Forwarded-For') or \
                      headers.get('X-Real-IP') or \
                      headers.get('X-Client-IP') or \
                      event.get('requestContext', {}).get('identity', {}).get('sourceIp')
        
        # Limpiar IP (tomar solo la primera si hay múltiples)
        user_ip = user_ip_raw.split(',')[0].strip() if user_ip_raw else None
        logger.info(f"User IP: {user_ip}")
        
        # 4. Para la prueba E2E, simular verificación exitosa
        # En producción real, aquí verificarías el token JWT
        logger.info(f"Token received: {jwt_token[:20]}...")
        
        # 5. Validar formato del token JWT
        if len(jwt_token.split('.')) != 3:
            logger.warning("Access DENIED - Invalid JWT format")
            return generate_policy('test-user', 'Deny', event['methodArn'])
        
        # 6. Decodificar JWT para obtener atributos reales
        try:
            import base64
            import json
            
            # Decodificar payload del JWT (sin verificar firma)
            payload_part = jwt_token.split('.')[1]
            # Agregar padding si es necesario (Base64 URL-safe)
            missing = (-len(payload_part)) % 4
            if missing:
                payload_part += '=' * missing
            payload = json.loads(base64.urlsafe_b64decode(payload_part))
            
            logger.info(f"JWT payload decoded: {payload}")
            
        except Exception as e:
            logger.warning(f"Error decoding JWT: {e}")
            return generate_policy('test-user', 'Deny', event['methodArn'])
        
        # 7. Aplicar validaciones de seguridad con atributos reales
        validation_result = perform_security_validations(payload, user_ip)
        
        if validation_result['allowed']:
            logger.info(f"Access ALLOWED - {validation_result['reason']}")
            return generate_policy_with_cors(payload['sub'], 'Allow', event['methodArn'])
        else:
            logger.warning(f"Access DENIED - {validation_result['reason']}")
            return generate_policy_with_cors(payload['sub'], 'Deny', event['methodArn'])
            
    except Exception as e:
        logger.error(f"Error in authorizer: {str(e)}")
        return generate_policy('error-user', 'Deny', event['methodArn'])

def perform_security_validations(payload, user_ip=None):
    """
    Valida acceso basado en grupos de Cognito con políticas de país/horario/IP
    """
    current_time = datetime.now()
    current_hour = current_time.hour
    
    # 1. Validar ventana de acceso (mantenimiento)
    if current_hour == 4:
        return {'allowed': False, 'reason': 'Maintenance window: 4:00-5:00 AM'}
    
    # 2. Obtener grupos de Cognito
    cognito_groups = payload.get('cognito:groups', [])
    logger.info(f"Cognito groups: {cognito_groups}")
    
    # 3. Si no hay grupos, rechazar acceso
    if not cognito_groups:
        logger.warning("Access DENIED - No valid groups found")
        return {'allowed': False, 'reason': 'No valid groups found - access denied'}
    
    # 4. Validar acceso por grupos con políticas de seguridad
    return validate_cognito_groups_access_with_policies(cognito_groups, current_hour, user_ip)

def get_country_from_ip(ip_address):
    """
    Obtiene el país de origen de una IP usando servicio gratuito IP-API
    """
    try:
        import urllib.request
        import urllib.parse
        
        # Limpiar IP para evitar caracteres inválidos en URL
        clean_ip = ip_address.strip()
        if not clean_ip or ' ' in clean_ip:
            logger.warning(f"Invalid IP address: {ip_address}")
            return 'UNKNOWN'
        
        url = f"http://ip-api.com/json/{clean_ip}"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
            country = data.get('countryCode', 'UNKNOWN')
            logger.info(f"IP {clean_ip} resolved to country: {country}")
            return country
            
    except Exception as e:
        logger.warning(f"Error getting country for IP {ip_address}: {e}")
        return 'UNKNOWN'

def validate_geographic_access(user_ip, allowed_countries):
    """
    Valida si la IP del usuario está en los países permitidos
    """
    if not allowed_countries or 'UNKNOWN' in allowed_countries:
        return {'allowed': True, 'reason': 'No geographic restrictions'}
    
    user_country = get_country_from_ip(user_ip)
    
    if user_country in allowed_countries:
        return {
            'allowed': True, 
            'reason': f'Geographic access allowed from {user_country}'
        }
    else:
        return {
            'allowed': False, 
            'reason': f'Geographic access denied from {user_country}. Allowed countries: {allowed_countries}'
        }

def validate_ip_whitelist(user_ip, ip_whitelist):
    """
    Valida si la IP del usuario está en la whitelist de IPs permitidas
    """
    if not ip_whitelist:
        return {'allowed': True, 'reason': 'No IP restrictions'}
    
    import ipaddress
    
    try:
        user_ip_obj = ipaddress.ip_address(user_ip)
        
        for allowed_network in ip_whitelist:
            if user_ip_obj in ipaddress.ip_network(allowed_network):
                return {
                    'allowed': True, 
                    'reason': f'IP {user_ip} allowed in network {allowed_network}'
                }
        
        return {
            'allowed': False, 
            'reason': f'IP {user_ip} not in whitelist. Allowed networks: {ip_whitelist}'
        }
        
    except Exception as e:
        logger.warning(f"Error validating IP whitelist: {e}")
        return {
            'allowed': False, 
            'reason': f'Invalid IP format: {user_ip}'
        }

def validate_cognito_groups_access_with_policies(cognito_groups, current_hour, user_ip=None):
    """
    Valida acceso basado en grupos de Cognito con políticas de seguridad por grupo
    """
    # Políticas de seguridad por grupo de MediSupply
    GROUP_POLICIES = {
        'admin': {
            'countries': ['CO', 'PE', 'EC', 'MX'],  # Todos los países
            'hours': {'start': 0, 'end': 23},       # 24/7
            'ip_whitelist': None,                   # Sin restricción IP
            'description': 'Acceso completo 24/7',
            'permissions': ['read_all', 'write_all', 'delete_all', 'audit_all'],
            'apis': ['*']
        },
        'compras': {
            'countries': ['CO', 'PE', 'EC', 'MX'],
            'hours': {'start': 6, 'end': 22},       # Horario laboral
            'ip_whitelist': ['10.0.0.0/8'],        # Solo red corporativa
            'description': 'Horario laboral, red corporativa',
            'permissions': ['read_purchases', 'write_purchases', 'manage_suppliers'],
            'apis': ['/purchases/*', '/suppliers/*', '/products/*']
        },
        'logistica': {
            'countries': ['CO', 'PE', 'EC', 'MX'],
            'hours': {'start': 5, 'end': 23},       # Horario extendido
            'ip_whitelist': None,
            'description': 'Horario extendido para logística',
            'permissions': ['read_logistics', 'write_inventory', 'manage_routes'],
            'apis': ['/logistics/*', '/inventory/*', '/routes/*', '/vehicles/*']
        },
        'ventas': {
            'countries': ['CO', 'PE', 'EC', 'MX'],
            'hours': {'start': 5, 'end': 23},       # Horario extendido
            'ip_whitelist': None,
            'description': 'Horario extendido para ventas',
            'permissions': ['read_sales', 'write_orders', 'manage_clients'],
            'apis': ['/sales/*', '/clients/*', '/orders/*', '/visits/*']
        },
        'clientes': {
            'countries': ['CO'],                    # Solo Colombia inicialmente
            'hours': {'start': 6, 'end': 22},       # Horario comercial
            'ip_whitelist': None,                   # Sin restricción IP
            'description': 'Horario comercial, solo Colombia',
            'permissions': ['read_products', 'create_orders', 'track_deliveries'],
            'apis': ['/products/available', '/orders/create', '/deliveries/track']
        }
    }
    
    # Verificar si el usuario está en algún grupo válido
    for group in cognito_groups:
        if group in GROUP_POLICIES:
            group_policy = GROUP_POLICIES[group]
            
            # Validar horario
            if not (group_policy['hours']['start'] <= current_hour <= group_policy['hours']['end']):
                return {
                    'allowed': False, 
                    'reason': f'Access denied for {group} group: outside allowed hours ({group_policy["hours"]["start"]}:00-{group_policy["hours"]["end"]}:59). Current hour: {current_hour}'
                }
            
            # Validar IP whitelist PRIMERO si se proporciona IP
            if user_ip and group_policy['ip_whitelist']:
                ip_validation = validate_ip_whitelist(user_ip, group_policy['ip_whitelist'])
                if not ip_validation['allowed']:
                    return ip_validation
            
            # Validar geografía si se proporciona IP (solo para IPs públicas)
            if user_ip and group_policy['countries']:
                # Solo validar geografía si la IP no está en whitelist (IPs privadas)
                skip_geo_validation = False
                if group_policy['ip_whitelist']:
                    # Verificar si la IP está en la whitelist usando la misma lógica
                    import ipaddress
                    try:
                        user_ip_obj = ipaddress.ip_address(user_ip)
                        for allowed_network in group_policy['ip_whitelist']:
                            if user_ip_obj in ipaddress.ip_network(allowed_network):
                                skip_geo_validation = True
                                break
                    except:
                        pass
                
                if not skip_geo_validation:
                    geo_validation = validate_geographic_access(user_ip, group_policy['countries'])
                    if not geo_validation['allowed']:
                        return geo_validation
            
            logger.info(f"User authorized by group: {group} - {group_policy['description']}")
            return {
                'allowed': True, 
                'reason': f"Access granted by {group} group - {group_policy['description']}"
            }
    
    # Si no está en ningún grupo válido
    return {'allowed': False, 'reason': f'User not in any valid MediSupply group. Current groups: {cognito_groups}'}

def generate_policy(principal_id, effect, resource):
    """Genera la política de autorización para API Gateway"""
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [{
                'Action': 'execute-api:Invoke',
                'Effect': effect,
                'Resource': resource
            }]
        }
    }
    
    logger.info(f"Generated policy: {policy}")
    return policy

def generate_policy_with_cors(principal_id, effect, resource):
    """
    Genera una política IAM con headers CORS para el autorizador
    """
    policy = {
        'principalId': principal_id,
        'policyDocument': {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'execute-api:Invoke',
                    'Effect': effect,
                    'Resource': resource
                }
            ]
        },
        'context': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        }
    }
    
    logger.info(f"Generated policy with CORS: {policy}")
    return policy
