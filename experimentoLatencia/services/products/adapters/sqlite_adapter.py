# adapters/sqlite_adapter.py
import sqlite3
from typing import List
from repositories.product_repository import ProductRepository
from domain.models import Product
from config import DB_NAME


class SQLiteProductAdapter(ProductRepository):
    """Implementación del repositorio de productos para SQLite."""

    def get_available_products(self) -> List[Product]:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

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
            p.product_id
        ORDER BY
            p.sku;
        '''

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

        conn.close()
        return products