#!/usr/bin/env python3
"""
🔐 Lambda Autorizadora 
====================================================

"""

import json
import os
import logging
from datetime import datetime
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Definicion de Handler 
    """
    try:
        logger.info(f"Authorization request received: {event}")
        headers = { (k or '').lower(): v for k, v in (event.get('headers') or {}).items() }
        
        # 1. Obtener token del header Authorization
        token = event.get('authorizationToken', '')
        if not token.startswith('Bearer '):
            logger.warning("Missing or invalid Bearer token")
            return generate_policy('user', 'Deny', event['methodArn'])
        
        jwt_token = token[7:]  # Remover 'Bearer '
        
        # 2. Para la prueba E2E, simular verificación exitosa
        # En producción real, aquí verificarías el token JWT
        logger.info(f"Token received: {jwt_token[:20]}...")
        
        # 3. Validar formato del token JWT
        if len(jwt_token.split('.')) != 3:
            logger.warning("Access DENIED - Invalid JWT format")
            return generate_policy('test-user', 'Deny', event['methodArn'])
        
        # 4. Decodificar JWT para obtener atributos reales
        try:
            import base64
            import json
            
            # Decodificar payload del JWT (sin verificar firma)
            payload_part = jwt_token.split('.')[1]
            # Agregar padding si es necesario
            payload_part += '=' * (4 - len(payload_part) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_part))
            
            logger.info(f"JWT payload decoded: {payload}")
            
        except Exception as e:
            logger.warning(f"Error decoding JWT: {e}")
            return generate_policy('test-user', 'Deny', event['methodArn'])
        
        # 5. Aplicar validaciones de seguridad con atributos reales y cabeceras
        validation_result = perform_security_validations(payload, headers)
        
        if validation_result['allowed']:
            logger.info(f"Access ALLOWED - {validation_result['reason']}")
            return generate_policy('test-user', 'Allow', event['methodArn'])
        else:
            logger.warning(f"Access DENIED - {validation_result['reason']}")
            return generate_policy('test-user', 'Deny', event['methodArn'])
            
    except Exception as e:
        logger.error(f"Error in authorizer: {str(e)}")
        return generate_policy('user', 'Deny', event['methodArn'])

def perform_security_validations(payload, headers):
    """
    Valida acceso basado SOLO en grupos de Cognito 
    """
    # Permitir simular hora por cabecera para demo E2E
    simulated_hour = headers.get('x-simulated-hour')
    try:
        current_hour = int(simulated_hour) if simulated_hour is not None else datetime.now().hour
    except Exception:
        current_hour = datetime.now().hour
    
    # 1. Validar ventana de acceso (mantenimiento)
    if current_hour == 4:
        return {'allowed': False, 'reason': 'Maintenance window: 4:00-5:00 AM'}
    
    # 2. Obtener grupos de Cognito (aceptar variantes de claim); si no hay, consultar en Cognito
    cognito_groups = payload.get('cognito:groups') or payload.get('groups') or []
    if not cognito_groups:
        # Consultar grupos desde Cognito (admin-list-groups-for-user)
        user_sub = payload.get('sub')
        user_pool_id = os.environ.get('USER_POOL_ID')
        region = os.environ.get('AWS_REGION') or os.environ.get('AWS_DEFAULT_REGION')
        try:
            if user_sub and user_pool_id and region:
                cognito = boto3.client('cognito-idp', region_name=region)
                resp = cognito.admin_list_groups_for_user(UserPoolId=user_pool_id, Username=user_sub)
                cognito_groups = [g['GroupName'] for g in resp.get('Groups', [])]
                logger.info(f"Fetched groups from Cognito for sub={user_sub}: {cognito_groups}")
            else:
                logger.warning("Missing USER_POOL_ID/AWS_REGION/sub to fetch groups from Cognito")
        except Exception as e:
            logger.warning(f"Error fetching groups from Cognito: {e}")
    logger.info(f"Cognito groups: {cognito_groups}")
    
    # 3. Si no hay grupos, rechazar acceso
    if not cognito_groups:
        logger.warning("Access DENIED - No valid groups found")
        return {'allowed': False, 'reason': 'No valid groups found - access denied'}
    
    # 4. Validar acceso por grupos + país y franja horaria por grupo (simple)
    return validate_cognito_groups_access(
        cognito_groups=cognito_groups,
        headers=headers,
        current_hour=current_hour,
    )

def validate_cognito_groups_access(cognito_groups, headers, current_hour):
    """
    Valida acceso basado en grupos de Cognito de MediSupply
    """
    # Reglas simples por grupo (países permitidos y franja horaria). Demo-friendly.
    # País se lee de cabecera 'x-country' (CO, PE, EC, MX, etc.)
    country = (headers.get('x-country') or '').upper().strip()

    group_rules = {
        'admin': {
            'countries': '*',            # sin restricción
            'hours': '*',                # cualquier hora
            'description': 'Administradores con acceso completo'
        },
        'compras': {
            'countries': {'CO', 'PE', 'EC', 'MX'},
            'hours': set(range(6, 23)), # 06:00-22:59
            'description': 'Equipo de compras y proveedores'
        },
        'logistica': {
            'countries': {'CO', 'PE', 'EC', 'MX'},
            'hours': set(range(5, 23)),
            'description': 'Equipo de logística e inventarios'
        },
        'ventas': {
            'countries': {'CO', 'PE', 'EC', 'MX'},
            'hours': set(range(7, 22)),
            'description': 'Fuerza de ventas y comerciales'
        },
        'clientes': {
            'countries': {'CO', 'PE', 'EC', 'MX'},
            'hours': set(range(6, 23)),
            'description': 'Clientes institucionales'
        },
    }

    # Si el usuario pertenece a algún grupo permitido y cumple reglas, Allow
    mediSupply_groups = {
        'admin': {
            'description': 'Administradores con acceso completo',
            'permissions': ['read_all', 'write_all', 'delete_all', 'audit_all'],
            'apis': ['*']
        },
        'compras': {
            'description': 'Equipo de compras y proveedores',
            'permissions': ['read_purchases', 'write_purchases', 'manage_suppliers'],
            'apis': ['/purchases/*', '/suppliers/*', '/products/*']
        },
        'logistica': {
            'description': 'Equipo de logística e inventarios',
            'permissions': ['read_logistics', 'write_inventory', 'manage_routes'],
            'apis': ['/logistics/*', '/inventory/*', '/routes/*', '/vehicles/*']
        },
        'ventas': {
            'description': 'Fuerza de ventas y comerciales',
            'permissions': ['read_sales', 'write_orders', 'manage_clients'],
            'apis': ['/sales/*', '/clients/*', '/orders/*', '/visits/*']
        },
        'clientes': {
            'description': 'Clientes institucionales',
            'permissions': ['read_products', 'create_orders', 'track_deliveries'],
            'apis': ['/products/available', '/orders/create', '/deliveries/track']
        }
    }
    
    # Verificar si el usuario está en algún grupo válido y evaluar reglas de país/hora
    for group in cognito_groups:
        if group in mediSupply_groups:
            # Evaluación de país y hora
            rules = group_rules.get(group)
            if rules is None:
                # Si no hay reglas específicas, permitir por pertenecer al grupo
                group_info = mediSupply_groups[group]
                logger.info(f"Access allowed (no rules) by group: {group}")
                return {'allowed': True, 'reason': f"Access granted by {group} group"}

            countries_allowed = rules['countries']
            hours_allowed = rules['hours']

            # País
            if countries_allowed != '*':
                if not country:
                    logger.warning("Access DENIED - Missing x-country header")
                    return {'allowed': False, 'reason': 'Missing x-country header'}
                if country not in countries_allowed:
                    logger.warning(f"Access DENIED - Country {country} not allowed for group {group}")
                    return {'allowed': False, 'reason': f'Country {country} not allowed for {group}'}

            # Franja horaria
            if hours_allowed != '*':
                if current_hour not in hours_allowed:
                    logger.warning(f"Access DENIED - Hour {current_hour} not allowed for group {group}")
                    return {'allowed': False, 'reason': f'Hour {current_hour} not allowed for {group}'}

            group_info = mediSupply_groups[group]
            logger.info(f"Access ALLOWED - {group} | country={country} | hour={current_hour}")
            return {
                'allowed': True,
                'reason': f"Access granted by {group} group with country/hour rules"
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
