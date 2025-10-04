#!/usr/bin/env python3
"""
Script para configurar CORS correctamente en API Gateway
Cambia HTTP_PROXY a HTTP y configura CORS
"""

import boto3
import json

def fix_cors():
    # Configuración
    REST_API_ID = "r1kyo276f3"
    RESOURCE_ID = "be2yw4"
    HTTP_METHOD = "GET"
    ALB_DNS = "medisupply-alb-120569610818-us-east-1-1234567890.us-east-1.elb.amazonaws.com"
    
    apigateway = boto3.client('apigateway')
    elbv2 = boto3.client('elbv2')
    
    print("🔧 **CONFIGURANDO CORS CORRECTAMENTE**")
    
    # 1. Obtener DNS real del ALB
    try:
        response = elbv2.describe_load_balancers()
        alb_dns = response['LoadBalancers'][0]['DNSName']
        print(f"✅ ALB DNS: {alb_dns}")
    except Exception as e:
        print(f"❌ Error obteniendo ALB DNS: {e}")
        return
    
    # 2. Cambiar integración de HTTP_PROXY a HTTP
    try:
        apigateway.put_integration(
            restApiId=REST_API_ID,
            resourceId=RESOURCE_ID,
            httpMethod=HTTP_METHOD,
            type='HTTP',
            integrationHttpMethod='GET',
            uri=f'http://{alb_dns}/products/available'
        )
        print("✅ Integración cambiada a HTTP")
    except Exception as e:
        print(f"❌ Error cambiando integración: {e}")
        return
    
    # 3. Configurar Method Response
    try:
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
        print("✅ Method Response configurado")
    except Exception as e:
        print(f"❌ Error configurando Method Response: {e}")
        return
    
    # 4. Configurar Integration Response
    try:
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
        print("✅ Integration Response configurado")
    except Exception as e:
        print(f"❌ Error configurando Integration Response: {e}")
        return
    
    # 5. Crear deployment
    try:
        deployment = apigateway.create_deployment(
            restApiId=REST_API_ID,
            stageName='prod'
        )
        print(f"✅ Deployment creado: {deployment['id']}")
    except Exception as e:
        print(f"❌ Error creando deployment: {e}")
        return
    
    print("\n🎉 **CORS CONFIGURADO CORRECTAMENTE**")
    print("🔗 Prueba el frontend: https://dl8uc6ciglyo6.cloudfront.net")

if __name__ == "__main__":
    fix_cors()
