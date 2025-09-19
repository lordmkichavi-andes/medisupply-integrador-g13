# app.py
from flask import Flask, jsonify, request, make_response
from adapters.sqlite_adapter import SQLiteProductAdapter
from services.product_service import ProductService
from database_setup import setup_database
from flask_caching import Cache
import os
import json

REDIS_HOST = os.environ.get('CACHE_HOST')
REDIS_PORT = os.environ.get('CACHE_PORT', '6379')
REDIS_DB = os.environ.get('CACHE_DB', '0')

config = {
    "CACHE_TYPE": "RedisCache",
    "CACHE_REDIS_HOST": REDIS_HOST,
    "CACHE_REDIS_PORT": REDIS_PORT,
    "CACHE_REDIS_DB": REDIS_DB
}

app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)

# Dependencia: inyección del repositorio en el servicio
product_repository = SQLiteProductAdapter()
product_service = ProductService(repository=product_repository)
setup_database()


@app.route('/products/available', methods=['GET'])
def get_products():
    """
    Endpoint para listar productos disponibles, con lógica de caché manual
    para verificar si la respuesta proviene de la caché.
    """
    # 1. Crea una clave de caché única para esta solicitud
    cache_key = request.full_path

    # 2. Intenta obtener la respuesta de la caché
    cached_data = cache.get(cache_key)

    if cached_data is not None:
        # ✅ Éxito: Los datos están en caché (Cache HIT)
        response = make_response(cached_data)
        response.headers['X-Cache'] = 'HIT'
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        # ❌ Fallo: Los datos no están en caché (Cache MISS)
        products = product_service.list_available_products()
        products_list = [p.__dict__ for p in products]

        # Convierte el diccionario a una cadena JSON para almacenarlo
        json_data = jsonify(products_list).data

        # Almacena la respuesta en la caché por 60 segundos
        cache.set(cache_key, json_data, timeout=60)

        response = make_response(json_data)
        response.headers['X-Cache'] = 'MISS'
        response.headers['Content-Type'] = 'application/json'
        return response


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)