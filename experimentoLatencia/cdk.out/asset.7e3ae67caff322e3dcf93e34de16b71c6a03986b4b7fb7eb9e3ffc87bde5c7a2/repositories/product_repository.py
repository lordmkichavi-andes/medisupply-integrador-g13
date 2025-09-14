# repositories/product_repository.py
from abc import ABC, abstractmethod
from typing import List
from domain.models import Product

class ProductRepository(ABC):
    """Interfaz abstracta para el repositorio de productos."""
    @abstractmethod
    def get_available_products(self) -> List[Product]:
        pass