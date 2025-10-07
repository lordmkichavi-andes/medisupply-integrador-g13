# app.py
from flask import Flask, jsonify, make_response, request
from adapters.sql_adapter import SQLiteProductAdapter
from services.product_service import ProductService
from database_setup import setup_database
from flask_caching import Cache
from functools import wraps

config = {
    "CACHE_TYPE": "SimpleCache",  # Usamos un caché en memoria
    "CACHE_DEFAULT_TIMEOUT": 300  # 5 minutos de duración del caché
}

app = Flask(__name__)
app.config.from_mapping(config)
cache = Cache(app)


def cache_control_header(timeout=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Obtiene la clave de la URL para usarla en la caché.
            cache_key = request.full_path

            # Intenta obtener la respuesta del caché
            cached_response = cache.get(cache_key)

            if cached_response is not None:
                # Si la respuesta está en caché, la devolvemos con el encabezado HIT
                response = make_response(cached_response)
                response.headers['X-Cache'] = 'HIT'
                return response
            else:
                # Si no está en caché, generamos la respuesta
                response = make_response(f(*args, **kwargs))
                response.headers['X-Cache'] = 'MISS'

                # Guardamos la respuesta en la caché antes de devolverla
                cache.set(cache_key, response.data, timeout=timeout)

                return response

        return decorated_function

    return decorator

# Dependencia: inyección del repositorio en el servicio
product_repository = SQLiteProductAdapter()
product_service = ProductService(repository=product_repository)
setup_database()


@app.route('/products/available', methods=['GET'])
@cache_control_header(timeout=60)
def get_products():
    """Endpoint para listar productos disponibles."""
    products = product_service.list_available_products()
    # Convertir la lista de objetos Product en un formato serializable (dict)
    products_list = [p.__dict__ for p in products]
    return jsonify(products_list)

@app.route('/products/update/<product_id>', methods=['PUT'])
def update_product(product_id):
    """
    Endpoint para actualizar un producto y forzar la invalidación de la caché.
    """
    data = request.get_json()
    price = data.get('price')
    stock = data.get('stock')

    if price is None or stock is None:
        return jsonify({"error": "Price and stock are required"}), 400

    # Actualiza el producto en la base de datos
    product_service.update_product(product_id, price=price, stock=stock)

    # ⚠️ Invalida la caché del endpoint de productos disponibles
    cache_key_to_invalidate = '/products/available'
    cache.delete(cache_key_to_invalidate)

    return jsonify({"status": "Product updated and cache invalidated"}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
