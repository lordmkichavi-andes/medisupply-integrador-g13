import psycopg2
from psycopg2.extras import RealDictCursor, register_uuid
from typing import List, Optional
from repositories.product_repository import ProductRepository
from domain.models import Product
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS

class PostgreSQLProductAdapter(ProductRepository):
    """Implementación del repositorio de productos para PostgreSQL (RDS)."""

    def _get_connection(self):
        """Método helper para establecer la conexión a PostgreSQL y devolver un cursor de diccionario."""
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        # Usamos RealDictCursor para obtener resultados como diccionarios (nombre de columna: valor),
        # similar a sqlite3.Row.
        return conn, conn.cursor(cursor_factory=RealDictCursor)

    # -------------------------------------------------------------
    # Implementación de get_available_products
    # -------------------------------------------------------------
    def get_available_products(self) -> List[Product]:
        conn, cursor = self._get_connection()

        query = '''
        SELECT 
            p.product_id,
            p.sku,
            p.value,
            c.name AS category_name,
            SUM(ps.quantity) AS total_quantity
        FROM 
            Product p
        JOIN 
            Category c ON p.category_id = c.category_id
        JOIN 
            ProductStock ps ON p.product_id = ps.product_id
        WHERE
            ps.quantity > 0
        GROUP BY
            p.product_id, p.sku, p.value, c.name -- PostgreSQL requiere agrupar por todas las columnas no agregadas
        ORDER BY
            p.sku;
        '''

        try:
            cursor.execute(query)
            results = cursor.fetchall()

            products = [
                Product(
                    product_id=row['product_id'],
                    sku=row['sku'],
                    value=row['value'],
                    category_name=row['category_name'],
                    total_quantity=row['total_quantity']
                ) for row in results
            ]

            return products

        finally:
            cursor.close()
            conn.close()

    # -------------------------------------------------------------
    # Implementación de get_product_by_id
    # -------------------------------------------------------------
    def get_product_by_id(self, product_id: str) -> Optional[Product]:
        """Obtiene un producto por su ID."""
        conn, cursor = self._get_connection()

        query = '''
        SELECT 
            p.product_id,
            p.sku,
            p.value,
            c.name AS category_name,
            SUM(ps.quantity) AS total_quantity
        FROM 
            Product p
        JOIN 
            Category c ON p.category_id = c.category_id
        JOIN 
            ProductStock ps ON p.product_id = ps.product_id
        WHERE
            p.product_id = %s -- 💡 Cambio de ? a %s para psycopg2
        GROUP BY
            p.product_id, p.sku, p.value, c.name
        ORDER BY
            p.sku;
        '''

        try:
            # 💡 Pasar los parámetros como una tupla (product_id,)
            cursor.execute(query, (product_id,))
            row = cursor.fetchone()

            if row:
                # 💡 Corregir mapeo de campos, usando nombres de columna (diccionario)
                return Product(
                    product_id=row['product_id'],
                    sku=row['sku'],
                    value=row['value'],
                    category_name=row['category_name'],
                    total_quantity=row['total_quantity']
                )
            return None

        finally:
            cursor.close()
            conn.close()

    # -------------------------------------------------------------
    # Implementación de update_product
    # -------------------------------------------------------------
    def update_product(self, product_id: str, price: float, stock: int) -> None:
        """
        Actualiza el precio y el stock de un producto por su ID.
        """
        conn, cursor = self._get_connection()

        query_product = '''
            UPDATE Product
            SET value = %s
            WHERE product_id = %s;
        '''
        query_stock = '''
            UPDATE ProductStock
            SET quantity = %s
            WHERE product_id = %s 
            AND warehouse_id = 'W-003';
        '''

        try:
            # 💡 Parámetros como tupla para psycopg2
            cursor.execute(query_product, (price, product_id))
            cursor.execute(query_stock, (stock, product_id))

            # Confirmar la transacción
            conn.commit()

        except Exception as e:
            # Revertir si hay un error en cualquier operación
            conn.rollback()
            raise e

        finally:
            cursor.close()
            conn.close()