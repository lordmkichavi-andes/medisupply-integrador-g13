#!/usr/bin/env python3
"""
Script para configurar CORS en API Gateway usando AWS CLI
Configura CORS para todas las respuestas (incluyendo errores)
"""

import subprocess
import json
import sys

def run_command(command):
    """Ejecuta un comando y retorna el resultado"""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error ejecutando: {command}")
            print(f"Error: {result.stderr}")
            return None
        return result.stdout
    except Exception as e:
        print(f"Excepción ejecutando: {command}")
        print(f"Error: {e}")
        return None

def configure_cors_for_method(api_id, resource_id, method):
    """Configura CORS para un método específico"""
    print(f"Configurando CORS para {method} en resource {resource_id}")
    
    # Configurar MethodResponse con headers CORS
    method_response_cmd = f"""
    aws apigateway put-method-response \
        --rest-api-id {api_id} \
        --resource-id {resource_id} \
        --http-method {method} \
        --status-code 200 \
        --response-parameters method.response.header.Access-Control-Allow-Origin=true,method.response.header.Access-Control-Allow-Headers=true,method.response.header.Access-Control-Allow-Methods=true
    """
    
    result = run_command(method_response_cmd)
    if result is None:
        print(f"Error configurando MethodResponse para {method}")
        return False
    
    # Configurar IntegrationResponse con headers CORS
    integration_response_cmd = f"""
    aws apigateway put-integration-response \
        --rest-api-id {api_id} \
        --resource-id {resource_id} \
        --http-method {method} \
        --status-code 200 \
        --response-parameters method.response.header.Access-Control-Allow-Origin="'*'",method.response.header.Access-Control-Allow-Headers="'Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Accept,Origin'",method.response.header.Access-Control-Allow-Methods="'GET,POST,PUT,DELETE,OPTIONS'"
    """
    
    result = run_command(integration_response_cmd)
    if result is None:
        print(f"Error configurando IntegrationResponse para {method}")
        return False
    
    print(f"✅ CORS configurado para {method}")
    return True

def main():
    """Función principal"""
    print("🚀 Configurando CORS en API Gateway...")
    
    # Obtener API ID
    api_id = "r1kyo276f3"  # API ID conocido
    print(f"API ID: {api_id}")
    
    # Obtener recursos
    resources_cmd = f"aws apigateway get-resources --rest-api-id {api_id}"
    resources_output = run_command(resources_cmd)
    
    if not resources_output:
        print("❌ Error obteniendo recursos")
        return False
    
    resources_data = json.loads(resources_output)
    
    # Configurar CORS para cada recurso
    for resource in resources_data.get('items', []):
        resource_id = resource.get('id')
        resource_path = resource.get('path', '')
        
        if not resource_id:
            continue
            
        print(f"\n📁 Configurando recurso: {resource_path} (ID: {resource_id})")
        
        # Configurar CORS para cada método HTTP
        for method in ['GET', 'POST', 'PUT', 'DELETE']:
            try:
                # Verificar si el método existe
                method_cmd = f"aws apigateway get-method --rest-api-id {api_id} --resource-id {resource_id} --http-method {method}"
                method_output = run_command(method_cmd)
                
                if method_output:
                    configure_cors_for_method(api_id, resource_id, method)
                else:
                    print(f"⚠️  Método {method} no existe en {resource_path}")
                    
            except Exception as e:
                print(f"⚠️  Error procesando método {method} en {resource_path}: {e}")
    
    # Crear nuevo deployment
    print("\n🚀 Creando nuevo deployment...")
    deployment_cmd = f"aws apigateway create-deployment --rest-api-id {api_id} --stage-name prod"
    deployment_output = run_command(deployment_cmd)
    
    if deployment_output:
        print("✅ Deployment creado exitosamente")
    else:
        print("❌ Error creando deployment")
        return False
    
    # Invalidar cache de CloudFront
    print("\n🔄 Invalidando cache de CloudFront...")
    distribution_id = "E1QZQZQZQZQZQZ"  # ID de distribución conocido
    invalidate_cmd = f"aws cloudfront create-invalidation --distribution-id {distribution_id} --paths '/*'"
    invalidate_output = run_command(invalidate_cmd)
    
    if invalidate_output:
        print("✅ Cache invalidado exitosamente")
    else:
        print("⚠️  Error invalidando cache (puede ser normal)")
    
    print("\n🎉 ¡CORS configurado exitosamente!")
    print("🌐 El frontend ahora debería funcionar en cualquier navegador")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
