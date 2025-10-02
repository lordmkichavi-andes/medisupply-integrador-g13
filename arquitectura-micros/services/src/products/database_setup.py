# database_setup.py
import sqlite3
import os
from config import DB_NAME

def setup_database():
    """Crea la base de datos y las tablas si no existen, y las puebla con datos."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    with open('insert_data.sql', 'r') as f:
        sql_script = f.read()

    # Creación de tablas
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS Category (
                          category_id INT PRIMARY KEY,
                          name VARCHAR(50) NOT NULL
        );
         CREATE TABLE IF NOT EXISTS Provider (
                                  provider_id VARCHAR(50) PRIMARY KEY,
                                  name VARCHAR(100) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS Product (
                                 product_id VARCHAR(50) PRIMARY KEY,
                                 sku VARCHAR(50) NOT NULL UNIQUE,
                                 value FLOAT NOT NULL,
                                 provider_id VARCHAR(50) NOT NULL,
                                 category_id INT NOT NULL,
                                 objective_profile VARCHAR(255) NOT NULL,
                                 FOREIGN KEY (provider_id) REFERENCES Provider(provider_id),
                                 FOREIGN KEY (category_id) REFERENCES Category(category_id)
        );
         CREATE TABLE IF NOT EXISTS ProductStock (
                              stock_id VARCHAR(50) PRIMARY KEY,
                              product_id VARCHAR(50) NOT NULL,
                              quantity INT NOT NULL,
                              lote VARCHAR(50) NOT NULL,
                              warehouse_id VARCHAR(50) NOT NULL,
                              country VARCHAR(50) NOT NULL,
                              FOREIGN KEY (product_id) REFERENCES Product(product_id)
                              );
    ''')

    # Para este ejemplo, omitimos las DDLs para no repetirlas
    # y asumimos que ya existen. En un entorno real, estarían aquí.

    # Llenado de datos solo si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM Product")
    if cursor.fetchone()[0] == 0:
        print("Creando registros de base de datos...")
        cursor.executescript(sql_script)
        print("Registros creados exitosamente.")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    setup_database()