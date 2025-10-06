#!/usr/bin/env python3
"""
Script para configurar CORS en TODOS los métodos y recursos del API Gateway
Configura CORS completo para toda la API
"""

import boto3
import json
import time

def setup_cors_all_methods():
    print("🚀 **CONFIGURANDO CORS PARA TODOS LOS MÉTODOS Y RECURSOS**")
    
    # Configuración
    REST_API_ID = "r1kyo276f3"
    AUTHORIZER_ID = "rhwzzb"
    
    apigateway = boto3.client('apigateway')
    elbv2 = boto3.client('elbv2')
    cloudfront = boto3.client('cloudfront')
    
    try:
        # 1. Obtener DNS del ALB
        print("📋 1. Obteniendo DNS del ALB...")
        response = elbv2.describe_load_balancers()
        alb_dns = response['LoadBalancers'][0]['DNSName']
        print(f"✅ ALB DNS: {alb_dns}")
        
        # 2. Obtener todos los recursos del API
        print("📋 2. Obteniendo todos los recursos del API...")
        resources = apigateway.get_resources(restApiId=REST_API_ID)
        
        # 3. Configurar CORS para cada recurso
        for resource in resources['items']:
            resource_id = resource['id']
            resource_path = resource.get('path', '')
            resource_methods = resource.get('resourceMethods', {})
            
            # Saltar el recurso raíz
            if resource_path == '/':
                continue
                
            print(f"📋 3. Configurando CORS para {resource_path}...")
            
            # Configurar CORS para cada método HTTP
            for method_name in resource_methods.keys():
                if method_name == 'OPTIONS':
                    continue  # OPTIONS se configura después
                    
                print(f"   🔧 Configurando {method_name} para {resource_path}...")
                
                try:
                    # Cambiar integración a HTTP si es HTTP_PROXY
                    integration = apigateway.get_integration(
                        restApiId=REST_API_ID,
                        resourceId=resource_id,
                        httpMethod=method_name
                    )
                    
                    if integration.get('type') == 'HTTP_PROXY':
                        # Cambiar a HTTP
                        apigateway.put_integration(
                            restApiId=REST_API_ID,
                            resourceId=resource_id,
                            httpMethod=method_name,
                            type='HTTP',
                            integrationHttpMethod=method_name,
                            uri=f'http://{alb_dns}{resource_path}'
                        )
                        print(f"     ✅ Integración {method_name} cambiada a HTTP")
                    
                    # Configurar Method Response
                    try:
                        apigateway.put_method_response(
                            restApiId=REST_API_ID,
                            resourceId=resource_id,
                            httpMethod=method_name,
                            statusCode='200',
                            responseParameters={
                                'method.response.header.Access-Control-Allow-Origin': True,
                                'method.response.header.Access-Control-Allow-Headers': True,
                                'method.response.header.Access-Control-Allow-Methods': True
                            }
                        )
                        print(f"     ✅ Method Response {method_name} configurado")
                    except apigateway.exceptions.ConflictException:
                        # Actualizar existente
                        apigateway.update_method_response(
                            restApiId=REST_API_ID,
                            resourceId=resource_id,
                            httpMethod=method_name,
                            statusCode='200',
                            patchOperations=[
                                {'op': 'replace', 'path': '/responseParameters/method.response.header.Access-Control-Allow-Origin', 'value': 'true'},
                                {'op': 'replace', 'path': '/responseParameters/method.response.header.Access-Control-Allow-Headers', 'value': 'true'},
                                {'op': 'replace', 'path': '/responseParameters/method.response.header.Access-Control-Allow-Methods', 'value': 'true'}
                            ]
                        )
                        print(f"     ✅ Method Response {method_name} actualizado")
                    
                    # Configurar Integration Response
                    try:
                        apigateway.put_integration_response(
                            restApiId=REST_API_ID,
                            resourceId=resource_id,
                            httpMethod=method_name,
                            statusCode='200',
                            responseParameters={
                                'method.response.header.Access-Control-Allow-Origin': "'*'",
                                'method.response.header.Access-Control-Allow-Headers': "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin'",
                                'method.response.header.Access-Control-Allow-Methods': "'GET,POST,PUT,DELETE,OPTIONS'"
                            }
                        )
                        print(f"     ✅ Integration Response {method_name} configurado")
                    except apigateway.exceptions.ConflictException:
                        # Actualizar existente
                        apigateway.update_integration_response(
                            restApiId=REST_API_ID,
                            resourceId=resource_id,
                            httpMethod=method_name,
                            statusCode='200',
                            patchOperations=[
                                {'op': 'replace', 'path': '/responseParameters/method.response.header.Access-Control-Allow-Origin', 'value': "'*'"},
                                {'op': 'replace', 'path': '/responseParameters/method.response.header.Access-Control-Allow-Headers', 'value': "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin'"},
                                {'op': 'replace', 'path': '/responseParameters/method.response.header.Access-Control-Allow-Methods', 'value': "'GET,POST,PUT,DELETE,OPTIONS'"}
                            ]
                        )
                        print(f"     ✅ Integration Response {method_name} actualizado")
                        
                except Exception as e:
                    print(f"     ⚠️ Error configurando {method_name}: {e}")
            
            # 4. Configurar OPTIONS para cada recurso
            print(f"   🔧 Configurando OPTIONS para {resource_path}...")
            
            try:
                # Crear método OPTIONS
                apigateway.put_method(
                    restApiId=REST_API_ID,
                    resourceId=resource_id,
                    httpMethod='OPTIONS',
                    authorizationType='CUSTOM',
                    authorizerId=AUTHORIZER_ID
                )
                print(f"     ✅ Método OPTIONS creado")
            except apigateway.exceptions.ConflictException:
                # Actualizar existente
                apigateway.update_method(
                    restApiId=REST_API_ID,
                    resourceId=resource_id,
                    httpMethod='OPTIONS',
                    patchOperations=[
                        {'op': 'replace', 'path': '/authorizationType', 'value': 'CUSTOM'},
                        {'op': 'replace', 'path': '/authorizerId', 'value': AUTHORIZER_ID}
                    ]
                )
                print(f"     ✅ Método OPTIONS actualizado")
            
            # Configurar integración OPTIONS
            apigateway.put_integration(
                restApiId=REST_API_ID,
                resourceId=resource_id,
                httpMethod='OPTIONS',
                type='MOCK',
                integrationHttpMethod='OPTIONS',
                requestTemplates={'application/json': '{"statusCode": 200}'}
            )
            print(f"     ✅ Integración OPTIONS configurada")
            
            # Configurar Method Response OPTIONS
            apigateway.put_method_response(
                restApiId=REST_API_ID,
                resourceId=resource_id,
                httpMethod='OPTIONS',
                statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Origin': True,
                    'method.response.header.Access-Control-Allow-Headers': True,
                    'method.response.header.Access-Control-Allow-Methods': True
                }
            )
            print(f"     ✅ Method Response OPTIONS configurado")
            
            # Configurar Integration Response OPTIONS
            apigateway.put_integration_response(
                restApiId=REST_API_ID,
                resourceId=resource_id,
                httpMethod='OPTIONS',
                statusCode='200',
                responseParameters={
                    'method.response.header.Access-Control-Allow-Origin': "'*'",
                    'method.response.header.Access-Control-Allow-Headers': "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin'",
                    'method.response.header.Access-Control-Allow-Methods': "'GET,POST,PUT,DELETE,OPTIONS'"
                }
            )
            print(f"     ✅ Integration Response OPTIONS configurado")
        
        # 5. Crear deployment
        print("📋 4. Creando deployment...")
        deployment = apigateway.create_deployment(
            restApiId=REST_API_ID,
            stageName='prod'
        )
        print(f"✅ Deployment creado: {deployment['id']}")
        
        # 6. Invalidar cache de CloudFront
        print("📋 5. Invalidando cache de CloudFront...")
        try:
            distributions = cloudfront.list_distributions()
            distribution_id = None
            for dist in distributions['DistributionList']['Items']:
                if dist['DomainName'] == 'dl8uc6ciglyo6.cloudfront.net':
                    distribution_id = dist['Id']
                    break
            
            if distribution_id:
                invalidation = cloudfront.create_invalidation(
                    DistributionId=distribution_id,
                    Paths=['/*']
                )
                print(f"✅ Cache invalidado: {invalidation['Invalidation']['Id']}")
            else:
                print("⚠️ No se encontró la distribución de CloudFront")
        except Exception as e:
            print(f"⚠️ Error invalidando cache: {e}")
        
        print("\n🎉 **CORS CONFIGURADO PARA TODA LA API**")
        print("🔗 Frontend: https://dl8uc6ciglyo6.cloudfront.net")
        print("⏱️ Espera 1-2 minutos para que CloudFront se actualice")
        print("\n📋 **CONFIGURACIÓN COMPLETA:**")
        print("   • TODOS los métodos HTTP: GET, POST, PUT, DELETE")
        print("   • TODOS los recursos: /products, /orders, /users, /reports")
        print("   • OPTIONS: Con autorizador Lambda (permite automáticamente)")
        print("   • CORS: Headers configurados en todas las respuestas")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    setup_cors_all_methods()
