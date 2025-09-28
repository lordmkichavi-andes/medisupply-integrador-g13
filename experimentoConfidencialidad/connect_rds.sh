#!/bin/bash

# Script para conectarse a la base de datos RDS PostgreSQL de MediSupply
# Obtiene credenciales desde AWS Secrets Manager y conecta con psql

set -e

# Configuración
SECRET_ARN="arn:aws:secretsmanager:us-east-1:120569610818:secret:ExperimentoStackV5Experimen-eXovkwKoUgm9-E1eP4g"
DB_HOST="experimentostackv5-experimentodb51b2d812-dglotery5nfh.c67kuumsib0c.us-east-1.rds.amazonaws.com"
DB_PORT="5432"
DB_NAME="postgres"

echo "🔐 Obteniendo credenciales desde AWS Secrets Manager..."

# Obtener credenciales
CREDENTIALS=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" --query SecretString --output text)
USERNAME=$(echo "$CREDENTIALS" | jq -r '.username')
PASSWORD=$(echo "$CREDENTIALS" | jq -r '.password')

echo "🔌 Conectando a la base de datos PostgreSQL..."
echo "📍 Host: $DB_HOST"
echo "🗄️  Base de datos: $DB_NAME"
echo "👤 Usuario: $USERNAME"
echo ""

# Configurar variable de entorno para la contraseña
export PGPASSWORD="$PASSWORD"

# Conectar con psql
psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -U "$USERNAME"


