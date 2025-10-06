import json
import requests
import os

def lambda_handler(event, context):
    """
    Lambda proxy para agregar headers CORS a las respuestas del API Gateway
    """
    
    # Headers CORS
    cors_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }
    
    # Si es OPTIONS (preflight), responder directamente
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({'message': 'CORS preflight'})
        }
    
    # Obtener la URL del backend desde variables de entorno
    backend_url = os.environ.get('BACKEND_URL')
    if not backend_url:
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': 'Backend URL not configured'})
        }
    
    try:
        # Hacer la petición al backend
        headers = {}
        if 'Authorization' in event.get('headers', {}):
            headers['Authorization'] = event['headers']['Authorization']
        
        response = requests.get(backend_url, headers=headers, timeout=30)
        
        return {
            'statusCode': response.status_code,
            'headers': {
                **cors_headers,
                'Content-Type': 'application/json'
            },
            'body': response.text
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        }
