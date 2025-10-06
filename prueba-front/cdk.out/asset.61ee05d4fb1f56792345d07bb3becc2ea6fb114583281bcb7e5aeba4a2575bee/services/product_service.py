# services/product_service.py
from typing import List
from repositories.product_repository import ProductRepository
from domain.models import Product

class ProductService:
    def __init__(self, repository: ProductRepository):
        self.repository = repository

    def list_available_products(self) -> List[Product]:
        """Caso de uso: listar todos los productos disponibles."""
        return self.repository.get_available_products()

    def update_product(self, product_id: str, price: float, stock: int) -> None:
        """Caso de uso: actualizar un producto existente."""
        self.repository.update_product(product_id=product_id, price=price, stock=stock)