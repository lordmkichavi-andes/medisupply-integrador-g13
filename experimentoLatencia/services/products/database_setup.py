# database_setup.py
import psycopg2
import os
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS


def connect_master(host, port, user, password, autocommit=False):
    """
    Conecta a la base de datos maestra 'postgres' y permite forzar autocommit.
    """
    conn = psycopg2.connect(
        host=host,
        port=port,
        database='postgres',
        user=user,
        password=password,
        connect_timeout=15
    )
    return conn

def connect_app_db(host, port, db_name, user, password):
    """Conecta a la base de datos de la aplicación (productosdb)."""
    return psycopg2.connect(
        host=host,
        port=port,
        database=db_name,
        user=user,
        password=password,
        connect_timeout=15
    )

def create_database_if_not_exists(master_conn, db_name):
    """Ejecuta CREATE DATABASE de forma segura."""
    # Deshabilitar las transacciones para comandos CREATE DATABASE
    try:
        with master_conn.cursor() as cursor:
            # Comando SQL para crear la BD si no existe
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
            if not cursor.fetchone():
                print(f"Creando base de datos: {db_name}")
                cursor.execute(f"CREATE DATABASE {db_name} TEMPLATE template0 ENCODING 'UTF8'")
            else:
                print(f"La base de datos {db_name} ya existe. Continuando.")

    except psycopg2.Error as e:
        # Esto captura errores no relacionados con "ya existe" que son críticos
        raise e
    finally:
        master_conn.autocommit = False

def setup_database():
    """Crea la base de datos, tablas, y las puebla."""
    master_conn = None
    app_conn = None

    # 1. PASO CLAVE: CONECTAR Y CREAR LA BD
    try:
        master_conn = connect_master(DB_HOST, DB_PORT, DB_USER, DB_PASS)
        master_conn.autocommit = True
        create_database_if_not_exists(master_conn, DB_NAME)
    except psycopg2.Error as e:
        print(f"Error fatal al crear o conectar a la BD maestra: {e}")
        if master_conn: master_conn.close()
        return # Salir si la creación de la BD falla

    if master_conn: master_conn.close()

    # 2. CONECTARSE A LA NUEVA BD Y CREAR TABLAS
    try:
        app_conn = connect_app_db(DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS)
        cursor = app_conn.cursor()

        # Script DDL (Definición de Tablas)
        ddl_script = """
        -- 💡 Asegurar que las tablas se crean ANTES de las FOREIGN KEYS
        
        -- Tabla Category
        CREATE TABLE IF NOT EXISTS Category (
            category_id INT PRIMARY KEY,
            name VARCHAR(50) NOT NULL
        );

        -- Tabla Provider
        CREATE TABLE IF NOT EXISTS Provider (
            provider_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(100) NOT NULL
        );

        -- Tabla Product
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

        -- Tabla ProductStock
        CREATE TABLE IF NOT EXISTS ProductStock (
            stock_id VARCHAR(50) PRIMARY KEY,
            product_id VARCHAR(50) NOT NULL,
            quantity INT NOT NULL,
            lote VARCHAR(50) NOT NULL,
            warehouse_id VARCHAR(50) NOT NULL,
            country VARCHAR(50) NOT NULL,
            FOREIGN KEY (product_id) REFERENCES Product(product_id)
        );
        """

        # Ejecución del DDL (usando un solo execute en este caso ya que es una cadena larga)
        # Nota: Psycopg2 puede manejar múltiples comandos separados por ; en una sola llamada si no contienen código de control.
        cursor.execute(ddl_script)


        # 3. Llenado de datos (Asume que 'insert_data.sql' existe en el código de la Lambda)
        cursor.execute("SELECT COUNT(*) FROM Product")
        if cursor.fetchone()[0] == 0:
            print("Creando registros de base de datos...")

            # Cargar el script de inserción de datos (ASUME ACCESO AL ARCHIVO 'insert_data.sql')
            # En una Lambda, necesitarías que este archivo esté empaquetado junto al código.
            with open('insert_data.sql', 'r') as f:
                sql_script = f.read()

            for statement in sql_script.split(';'):
                if statement.strip():
                    cursor.execute(statement)

            print("Registros creados exitosamente.")

        # Confirmar todos los cambios
        app_conn.commit()

    except psycopg2.Error as e:
        print(f"Error de PostgreSQL durante la creación de tablas/inserción de datos: {e}")
        if app_conn:
            app_conn.rollback()

    finally:
        if app_conn:
            app_conn.close()


# if __name__ == '__main__':
#     # Esta parte solo sería usada para pruebas locales
#     setup_database(os.environ['DB_HOST'], 5432, 'productosdb', 'postgres', os.environ['DB_PASS'])
