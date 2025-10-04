#!/usr/bin/env python3
"""
Script para configurar CORS en API Gateway para respuestas de error
Configura CORS para todas las respuestas (incluyendo errores 403, 401, 500, etc.)
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

def configure_cors_for_error_responses(api_id, resource_id, method):
    """Configura CORS para respuestas de error"""
    print(f"Configurando CORS para respuestas de error en {method} en resource {resource_id}")
    
    # Configurar MethodResponse para respuestas de error
    error_codes = ['403', '401', '500', '400', '404']
    
    for status_code in error_codes:
        print(f"  Configurando MethodResponse para {status_code}")
        
        method_response_cmd = f"""
        aws apigateway put-method-response \
            --rest-api-id {api_id} \
            --resource-id {resource_id} \
            --http-method {method} \
            --status-code {status_code} \
            --response-parameters method.response.header.Access-Control-Allow-Origin=true
        """
        
        result = run_command(method_response_cmd)
        if result is None:
            print(f"    ⚠️  Error configurando MethodResponse para {status_code}")
        else:
            print(f"    ✅ MethodResponse configurado para {status_code}")
    
    # Configurar IntegrationResponse para respuestas de error
    for status_code in error_codes:
        print(f"  Configurando IntegrationResponse para {status_code}")
        
        integration_response_cmd = f"""
        aws apigateway put-integration-response \
            --rest-api-id {api_id} \
            --resource-id {resource_id} \
            --http-method {method} \
            --status-code {status_code} \
            --response-parameters method.response.header.Access-Control-Allow-Origin="'*'" \
            --selection-pattern "{status_code[0]}\\d{{2}}"
        """
        
        result = run_command(integration_response_cmd)
        if result is None:
            print(f"    ⚠️  Error configurando IntegrationResponse para {status_code}")
        else:
            print(f"    ✅ IntegrationResponse configurado para {status_code}")
    
    return True

def main():
    """Función principal"""
    print("🚀 Configurando CORS para respuestas de error en API Gateway...")
    
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
                    configure_cors_for_error_responses(api_id, resource_id, method)
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
    distribution_id = "E31ZNDPOLDZPSV"  # ID de distribución conocido
    invalidate_cmd = f"aws cloudfront create-invalidation --distribution-id {distribution_id} --paths '/*'"
    invalidate_output = run_command(invalidate_cmd)
    
    if invalidate_output:
        print("✅ Cache invalidado exitosamente")
    else:
        print("⚠️  Error invalidando cache (puede ser normal)")
    
    print("\n🎉 ¡CORS configurado para respuestas de error!")
    print("🌐 El frontend ahora debería funcionar en cualquier navegador")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
