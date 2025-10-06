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
            # Agregar padding si es necesario (Base64 URL-safe)
            missing = (-len(payload_part)) % 4
            if missing:
                payload_part += '=' * missing
            payload = json.loads(base64.urlsafe_b64decode(payload_part))
            
            logger.info(f"JWT payload decoded: {payload}")
            
        except Exception as e:
            logger.warning(f"Error decoding JWT: {e}")
            return generate_policy('test-user', 'Deny', event['methodArn'])
        
        # 5. Aplicar validaciones de seguridad con atributos reales
        validation_result = perform_security_validations(payload)
        
        if validation_result['allowed']:
            logger.info(f"Access ALLOWED - {validation_result['reason']}")
            return generate_policy('test-user', 'Allow', event['methodArn'])
        else:
            logger.warning(f"Access DENIED - {validation_result['reason']}")
            return generate_policy('test-user', 'Deny', event['methodArn'])
            
    except Exception as e:
        logger.error(f"Error in authorizer: {str(e)}")
        return generate_policy('user', 'Deny', event['methodArn'])

def perform_security_validations(payload):
    """
    Valida acceso basado SOLO en grupos de Cognito 
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
    
    # 4. Validar acceso por grupos
    return validate_cognito_groups_access(cognito_groups, None, None)

def validate_cognito_groups_access(cognito_groups, user_department, user_role):
    """
    Valida acceso basado en grupos de Cognito de MediSupply
    """
    # Grupos de MediSupply con sus permisos
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
    
    # Verificar si el usuario está en algún grupo válido
    for group in cognito_groups:
        if group in mediSupply_groups:
            group_info = mediSupply_groups[group]
            logger.info(f"User authorized by group: {group} - {group_info['description']}")
            return {
                'allowed': True, 
                'reason': f"Access granted by {group} group - {group_info['description']}"
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
