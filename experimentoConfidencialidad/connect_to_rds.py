#!/usr/bin/env python3
"""
Script para conectarse a la base de datos RDS PostgreSQL de MediSupply
Obtiene las credenciales desde AWS Secrets Manager y permite conexión directa
"""

import boto3
import json
import subprocess
import sys
import os
from typing import Dict, Optional

# Configuración de la base de datos
DB_CONFIG = {
    'host': 'experimentostackv5-experimentodb51b2d812-dglotery5nfh.c67kuumsib0c.us-east-1.rds.amazonaws.com',
    'port': '5432',
    'database': 'postgres',
    'secret_arn': 'arn:aws:secretsmanager:us-east-1:120569610818:secret:ExperimentoStackV5Experimen-eXovkwKoUgm9-E1eP4g'
}

def get_credentials() -> Dict[str, str]:
    """Obtener credenciales desde AWS Secrets Manager"""
    try:
        print("🔐 Obteniendo credenciales desde AWS Secrets Manager...")
        sm = boto3.client('secretsmanager')
        secret_value = sm.get_secret_value(SecretId=DB_CONFIG['secret_arn'])
        secret_dict = json.loads(secret_value['SecretString'])
        
        return {
            'username': secret_dict['username'],
            'password': secret_dict['password']
        }
    except Exception as e:
        print(f"❌ Error obteniendo credenciales: {e}")
        sys.exit(1)

def generate_psql_command(credentials: Dict[str, str], custom_query: Optional[str] = None) -> str:
    """Generar comando psql para conexión"""
    # Configurar variable de entorno para la contraseña
    env_setup = f"export PGPASSWORD='{credentials['password']}'"
    
    # Comando base de conexión
    psql_cmd = f"psql -h {DB_CONFIG['host']} -p {DB_CONFIG['port']} -d {DB_CONFIG['database']} -U {credentials['username']}"
    
    if custom_query:
        psql_cmd += f" -c \"{custom_query}\""
    
    return f"{env_setup} && {psql_cmd}"

def connect_interactive():
    """Conectar de forma interactiva a la base de datos"""
    credentials = get_credentials()
    print("🔌 Conectando a la base de datos PostgreSQL...")
    print(f"📍 Host: {DB_CONFIG['host']}")
    print(f"🗄️  Base de datos: {DB_CONFIG['database']}")
    print(f"👤 Usuario: {credentials['username']}")
    print()
    
    # Ejecutar conexión interactiva
    cmd = generate_psql_command(credentials)
    subprocess.run(cmd, shell=True)

def run_query(query: str):
    """Ejecutar una consulta específica"""
    credentials = get_credentials()
    print(f"🔍 Ejecutando consulta: {query}")
    print()
    
    cmd = generate_psql_command(credentials, query)
    subprocess.run(cmd, shell=True)

def show_help():
    """Mostrar ayuda del script"""
    print("""
🚀 Script de Conexión a RDS PostgreSQL - MediSupply

Uso:
    python3 connect_to_rds.py [comando] [opciones]

Comandos:
    interactive, i     Conectar de forma interactiva (por defecto)
    query, q          Ejecutar una consulta específica
    help, h           Mostrar esta ayuda

Ejemplos:
    python3 connect_to_rds.py
    python3 connect_to_rds.py interactive
    python3 connect_to_rds.py query "SELECT COUNT(*) FROM reports;"
    python3 connect_to_rds.py query "SELECT * FROM reports LIMIT 5;"

Consultas útiles:
    - SELECT COUNT(*) FROM reports;
    - SELECT owner_username, COUNT(*) FROM reports GROUP BY owner_username;
    - SELECT * FROM reports WHERE owner_username = 'user.ny@medisupply.com' LIMIT 10;
    """)

def main():
    """Función principal"""
    if len(sys.argv) == 1:
        # Sin argumentos, conectar de forma interactiva
        connect_interactive()
    elif len(sys.argv) == 2:
        command = sys.argv[1].lower()
        if command in ['interactive', 'i']:
            connect_interactive()
        elif command in ['help', 'h']:
            show_help()
        else:
            print(f"❌ Comando desconocido: {command}")
            show_help()
    elif len(sys.argv) == 3:
        command = sys.argv[1].lower()
        if command in ['query', 'q']:
            query = sys.argv[2]
            run_query(query)
        else:
            print(f"❌ Comando desconocido: {command}")
            show_help()
    else:
        print("❌ Demasiados argumentos")
        show_help()

if __name__ == "__main__":
    main()


