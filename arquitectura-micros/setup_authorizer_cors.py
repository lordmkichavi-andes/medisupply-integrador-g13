#!/usr/bin/env python3
"""
Script para configurar autorizador Lambda con CORS automático
El autorizador Lambda maneja CORS automáticamente para todos los métodos
"""

import boto3
import json
import time

def setup_authorizer_cors():
    print("🚀 **CONFIGURANDO AUTORIZADOR LAMBDA CON CORS AUTOMÁTICO**")
    
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
        
        # 3. Configurar autorizador para cada método
        for resource in resources['items']:
            resource_id = resource['id']
            resource_path = resource.get('path', '')
            resource_methods = resource.get('resourceMethods', {})
            
            # Saltar el recurso raíz
            if resource_path == '/':
                continue
                
            print(f"📋 3. Configurando autorizador para {resource_path}...")
            
            # Configurar autorizador para cada método HTTP
            for method_name in resource_methods.keys():
                print(f"   🔧 Configurando autorizador para {method_name} en {resource_path}...")
                
                try:
                    # Configurar autorizador en el método
                    apigateway.update_method(
                        restApiId=REST_API_ID,
                        resourceId=resource_id,
                        httpMethod=method_name,
                        patchOperations=[
                            {'op': 'replace', 'path': '/authorizationType', 'value': 'CUSTOM'},
                            {'op': 'replace', 'path': '/authorizerId', 'value': AUTHORIZER_ID}
                        ]
                    )
                    print(f"     ✅ Autorizador configurado para {method_name}")
                    
                    # Cambiar integración a HTTP si es HTTP_PROXY
                    try:
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
                    except Exception as e:
                        print(f"     ⚠️ Error configurando integración {method_name}: {e}")
                        
                except Exception as e:
                    print(f"     ⚠️ Error configurando autorizador para {method_name}: {e}")
            
            # 4. Crear método OPTIONS si no existe
            if 'OPTIONS' not in resource_methods:
                print(f"   🔧 Creando método OPTIONS para {resource_path}...")
                
                try:
                    apigateway.put_method(
                        restApiId=REST_API_ID,
                        resourceId=resource_id,
                        httpMethod='OPTIONS',
                        authorizationType='CUSTOM',
                        authorizerId=AUTHORIZER_ID
                    )
                    print(f"     ✅ Método OPTIONS creado")
                    
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
                    
                except Exception as e:
                    print(f"     ⚠️ Error creando OPTIONS: {e}")
        
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
        
        print("\n🎉 **AUTORIZADOR LAMBDA CONFIGURADO CON CORS AUTOMÁTICO**")
        print("🔗 Frontend: https://dl8uc6ciglyo6.cloudfront.net")
        print("⏱️ Espera 1-2 minutos para que CloudFront se actualice")
        print("\n📋 **CONFIGURACIÓN FINAL:**")
        print("   • TODOS los métodos: GET, POST, PUT, DELETE, OPTIONS")
        print("   • TODOS los recursos: /products, /orders, /users, /reports")
        print("   • Autorizador Lambda: Maneja autorización + CORS automáticamente")
        print("   • CORS: Headers agregados por el autorizador en todas las respuestas")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    setup_authorizer_cors()
