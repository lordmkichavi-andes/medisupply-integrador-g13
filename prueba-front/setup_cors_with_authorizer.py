#!/usr/bin/env python3
"""
Script para configurar CORS con autorizador Lambda
OPTIONS también pasa por el autorizador pero se permite automáticamente
"""

import boto3
import json
import time

def setup_cors_with_authorizer():
    print("🚀 **CONFIGURANDO CORS CON AUTORIZADOR LAMBDA**")
    
    # Configuración
    REST_API_ID = "r1kyo276f3"
    RESOURCE_ID = "be2yw4"
    HTTP_METHOD = "GET"
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
        
        # 2. Cambiar integración GET de HTTP_PROXY a HTTP
        print("📋 2. Cambiando integración GET a HTTP...")
        apigateway.put_integration(
            restApiId=REST_API_ID,
            resourceId=RESOURCE_ID,
            httpMethod=HTTP_METHOD,
            type='HTTP',
            integrationHttpMethod='GET',
            uri=f'http://{alb_dns}/products/available'
        )
        print("✅ Integración GET cambiada a HTTP")
        
        # 3. Configurar Method Response para GET
        print("📋 3. Configurando Method Response para GET...")
        apigateway.put_method_response(
            restApiId=REST_API_ID,
            resourceId=RESOURCE_ID,
            httpMethod=HTTP_METHOD,
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Origin': True,
                'method.response.header.Access-Control-Allow-Headers': True,
                'method.response.header.Access-Control-Allow-Methods': True
            }
        )
        print("✅ Method Response GET configurado")
        
        # 4. Configurar Integration Response para GET
        print("📋 4. Configurando Integration Response para GET...")
        apigateway.put_integration_response(
            restApiId=REST_API_ID,
            resourceId=RESOURCE_ID,
            httpMethod=HTTP_METHOD,
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Origin': "'*'",
                'method.response.header.Access-Control-Allow-Headers': "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin'",
                'method.response.header.Access-Control-Allow-Methods': "'GET,POST,PUT,DELETE,OPTIONS'"
            }
        )
        print("✅ Integration Response GET configurado")
        
        # 5. Configurar OPTIONS con autorizador
        print("📋 5. Configurando OPTIONS con autorizador...")
        try:
            # Crear método OPTIONS si no existe
            apigateway.put_method(
                restApiId=REST_API_ID,
                resourceId=RESOURCE_ID,
                httpMethod='OPTIONS',
                authorizationType='CUSTOM',
                authorizerId=AUTHORIZER_ID
            )
            print("✅ Método OPTIONS creado con autorizador")
        except apigateway.exceptions.ConflictException:
            # Actualizar método existente
            apigateway.update_method(
                restApiId=REST_API_ID,
                resourceId=RESOURCE_ID,
                httpMethod='OPTIONS',
                patchOperations=[
                    {'op': 'replace', 'path': '/authorizationType', 'value': 'CUSTOM'},
                    {'op': 'replace', 'path': '/authorizerId', 'value': AUTHORIZER_ID}
                ]
            )
            print("✅ Método OPTIONS actualizado con autorizador")
        
        # 6. Configurar integración OPTIONS
        print("📋 6. Configurando integración OPTIONS...")
        apigateway.put_integration(
            restApiId=REST_API_ID,
            resourceId=RESOURCE_ID,
            httpMethod='OPTIONS',
            type='MOCK',
            integrationHttpMethod='OPTIONS',
            requestTemplates={'application/json': '{"statusCode": 200}'}
        )
        print("✅ Integración OPTIONS configurada")
        
        # 7. Configurar Method Response para OPTIONS
        print("📋 7. Configurando Method Response para OPTIONS...")
        apigateway.put_method_response(
            restApiId=REST_API_ID,
            resourceId=RESOURCE_ID,
            httpMethod='OPTIONS',
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Origin': True,
                'method.response.header.Access-Control-Allow-Headers': True,
                'method.response.header.Access-Control-Allow-Methods': True
            }
        )
        print("✅ Method Response OPTIONS configurado")
        
        # 8. Configurar Integration Response para OPTIONS
        print("📋 8. Configurando Integration Response para OPTIONS...")
        apigateway.put_integration_response(
            restApiId=REST_API_ID,
            resourceId=RESOURCE_ID,
            httpMethod='OPTIONS',
            statusCode='200',
            responseParameters={
                'method.response.header.Access-Control-Allow-Origin': "'*'",
                'method.response.header.Access-Control-Allow-Headers': "'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin'",
                'method.response.header.Access-Control-Allow-Methods': "'GET,POST,PUT,DELETE,OPTIONS'"
            }
        )
        print("✅ Integration Response OPTIONS configurado")
        
        # 9. Crear deployment
        print("📋 9. Creando deployment...")
        deployment = apigateway.create_deployment(
            restApiId=REST_API_ID,
            stageName='prod'
        )
        print(f"✅ Deployment creado: {deployment['id']}")
        
        # 10. Invalidar cache de CloudFront
        print("📋 10. Invalidando cache de CloudFront...")
        try:
            # Obtener distribution ID
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
        
        print("\n🎉 **CORS CONFIGURADO CON AUTORIZADOR LAMBDA**")
        print("🔗 Frontend: https://dl8uc6ciglyo6.cloudfront.net")
        print("⏱️ Espera 1-2 minutos para que CloudFront se actualice")
        print("\n📋 **CONFIGURACIÓN FINAL:**")
        print("   • GET: Con autorizador Lambda + CORS")
        print("   • OPTIONS: Con autorizador Lambda (permite automáticamente) + CORS")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    setup_cors_with_authorizer()
