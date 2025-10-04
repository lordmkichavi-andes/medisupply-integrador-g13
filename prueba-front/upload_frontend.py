#!/usr/bin/env python3
"""
Script para subir archivos del frontend al bucket S3
"""

import boto3
import os
import sys

def upload_frontend_files():
    """Subir archivos del frontend al bucket S3"""
    
    # Obtener nombre del bucket desde CloudFormation
    try:
        import subprocess
        result = subprocess.run([
            "aws", "cloudformation", "describe-stacks",
            "--stack-name", "MediSupplyStack",
            "--query", "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue",
            "--output", "text"
        ], capture_output=True, text=True, check=True)
        
        bucket_name = result.stdout.strip()
        if not bucket_name or bucket_name == "None":
            print("❌ No se pudo obtener el nombre del bucket del frontend")
            return False
            
    except Exception as e:
        print(f"❌ Error obteniendo nombre del bucket: {e}")
        return False
    
    print(f"📦 Subiendo archivos al bucket: {bucket_name}")
    
    # Inicializar cliente S3
    s3 = boto3.client('s3')
    
    # Archivos a subir
    files_to_upload = [
        ('frontend/index.html', 'index.html'),
        ('frontend/error.html', 'error.html')
    ]
    
    try:
        for local_path, s3_key in files_to_upload:
            if os.path.exists(local_path):
                print(f"⬆️  Subiendo {local_path} -> {s3_key}")
                s3.upload_file(
                    local_path, 
                    bucket_name, 
                    s3_key,
                    ExtraArgs={
                        'ContentType': 'text/html',
                        'CacheControl': 'max-age=300'  # 5 minutos de cache
                    }
                )
                print(f"✅ {s3_key} subido exitosamente")
            else:
                print(f"❌ Archivo no encontrado: {local_path}")
                return False
                
        print("🎉 Todos los archivos subidos exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error subiendo archivos: {e}")
        return False

def get_frontend_url():
    """Obtener URL del frontend desde CloudFormation"""
    try:
        import subprocess
        result = subprocess.run([
            "aws", "cloudformation", "describe-stacks",
            "--stack-name", "MediSupplyStack",
            "--query", "Stacks[0].Outputs[?OutputKey=='FrontendURL'].OutputValue",
            "--output", "text"
        ], capture_output=True, text=True, check=True)
        
        frontend_url = result.stdout.strip()
        if frontend_url and frontend_url != "None":
            return frontend_url
        else:
            return None
            
    except Exception as e:
        print(f"❌ Error obteniendo URL del frontend: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Subiendo archivos del frontend a S3...")
    
    if upload_frontend_files():
        frontend_url = get_frontend_url()
        if frontend_url:
            print(f"\n🌐 Frontend disponible en: {frontend_url}")
            print("⏳ CloudFront puede tardar 5-10 minutos en propagar los cambios")
        else:
            print("\n⚠️  No se pudo obtener la URL del frontend")
        sys.exit(0)
    else:
        print("\n❌ Error subiendo archivos del frontend")
        sys.exit(1)
