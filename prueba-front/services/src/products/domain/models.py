# domain/models.py
from dataclasses import dataclass

@dataclass
class Product:
    product_id: str
    sku: str
    value: float
    category_name: str
    total_quantity: int