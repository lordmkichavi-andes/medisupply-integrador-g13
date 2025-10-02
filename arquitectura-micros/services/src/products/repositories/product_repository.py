# repositories/product_repository.py
from abc import ABC, abstractmethod
from typing import List
from domain.models import Product

class ProductRepository(ABC):
    """Interfaz abstracta para el repositorio de productos."""
    @abstractmethod
    def get_available_products(self) -> List[Product]:
        pass

    @abstractmethod
    def get_product_by_id(self, product_id: str) -> List[Product]:
        """Obtiene un producto por su ID."""
        pass

    @abstractmethod
    def update_product(self, product_id: str, price: float, stock: int) -> None:
        """Actualiza un producto existente por su ID."""
        pass