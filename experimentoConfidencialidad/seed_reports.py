#!/usr/bin/env python3
"""
Semilla de datos para la tabla reports en RDS PostgreSQL.

Variables de entorno requeridas:
  DB_HOST, DB_PORT=5432, DB_NAME=postgres, DB_USER=postgres, DB_PASSWORD
Opcionales:
  REPORTS_COUNT (por defecto 100)

Ejemplo:
  export DB_HOST=<endpoint_rds>
  export DB_PASSWORD=<password>
  python3 scripts/seed_reports.py
"""
import os
import sys
from datetime import datetime, timedelta
import random
import json

try:
    import boto3  # opcional, solo si usas SECRET_ARN
except Exception:
    boto3 = None

try:
    import pg8000
except Exception as e:
    print("ERROR: requiere la librería pg8000 (pip install pg8000)")
    sys.exit(1)


def get_env(var_name: str, default: str = None) -> str:
    value = os.getenv(var_name, default)
    if value is None:
        print(f"Falta variable de entorno: {var_name}")
        sys.exit(2)
    return value


def main():
    # Opción 1: Secrets Manager
    secret_arn = os.getenv("SECRET_ARN")
    if secret_arn:
        if boto3 is None:
            print("Falta boto3 para usar SECRET_ARN. Instala con: pip install boto3")
            sys.exit(2)
        sm = boto3.client("secretsmanager")
        sec = sm.get_secret_value(SecretId=secret_arn)
        secret_dict = json.loads(sec.get("SecretString", "{}"))
        host = secret_dict.get("host") or get_env("DB_HOST")
        port = int(secret_dict.get("port") or os.getenv("DB_PORT", "5432"))
        database = secret_dict.get("dbname") or os.getenv("DB_NAME", "postgres")
        user = secret_dict.get("username") or os.getenv("DB_USER", "postgres")
        password = secret_dict.get("password") or os.getenv("DB_PASSWORD")
    else:
        # Opción 2: variables de entorno
        host = get_env("DB_HOST")
        port = int(get_env("DB_PORT", "5432"))
        database = get_env("DB_NAME", "postgres")
        user = get_env("DB_USER", "postgres")
        password = get_env("DB_PASSWORD")

    reports_count = int(os.getenv("REPORTS_COUNT", "100"))

    print("Conectando a RDS...", host, port)
    conn = pg8000.connect(host=host, port=port, database=database, user=user, password=password)
    try:
        with conn.cursor() as cur:
            # Crear tabla e índices si no existen
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    report_id SERIAL PRIMARY KEY,
                    customer_id VARCHAR(50) NOT NULL,
                    customer_name VARCHAR(200) NOT NULL,
                    region VARCHAR(50) NOT NULL,
                    owner_username VARCHAR(150) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    total_amount NUMERIC(12,2) NOT NULL,
                    status VARCHAR(30) NOT NULL
                );
                """
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_owner ON reports(owner_username);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_reports_customer ON reports(customer_id);")

            # Insertar datos sintéticos
            regions = ["US-EAST", "US-WEST", "LATAM-N", "LATAM-S"]
            owners = [
                "user.ny@medisupply.com",
                "admin@medisupply.com",
                "user.la@medisupply.com",
                "user.bog@medisupply.com"
            ]
            statuses = ["APPROVED", "PENDING", "REJECTED"]
            base_date = datetime.utcnow() - timedelta(days=90)

            for i in range(reports_count):
                region = random.choice(regions)
                owner = random.choice(owners)
                cust_code = f"CUST-{region.split('-')[0]}-{i:03d}"
                cust_name = f"Cliente {region} #{i:03d}"
                created = base_date + timedelta(days=random.randint(0, 90), hours=random.randint(0, 23))
                amount = round(random.uniform(100.0, 25000.0), 2)
                status = random.choice(statuses)
                cur.execute(
                    """
                    INSERT INTO reports (customer_id, customer_name, region, owner_username, created_at, total_amount, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (cust_code, cust_name, region, owner, created, amount, status)
                )

        conn.commit()
        print(f"Semilla aplicada: {reports_count} reportes insertados (o ya existentes).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()


