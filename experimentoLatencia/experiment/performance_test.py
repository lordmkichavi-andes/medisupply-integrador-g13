import os
import json
from locust import HttpUser, task, between, events
import time
import statistics

# Lee la URL base del servicio desde una variable de entorno.
# Se ha corregido para incluir el esquema https:// por defecto
BASE_URL = os.environ.get("BASE_URL", "https://localhost:8080")
global PRODCUCT_STOCK
global start_time_to_miss
global end_time_to_miss

class ProductsServiceUser(HttpUser):
    """
    Clase de usuario para simular el comportamiento de un cliente
    interactuando con el servicio de productos.
    """
    # Tiempo de espera entre tareas para simular un usuario real.
    # Los usuarios esperarán entre 1 y 3 segundos antes de la próxima tarea.
    wait_time = between(1, 3)
    host = BASE_URL

    # Un diccionario para llevar el conteo de los 'cache hits' y 'cache misses'.
    cache_metrics = {"hit": 0, "miss": 0, "time":0, "ttl":[]}

    # Lista para almacenar los resultados de latencia de propagación
    propagation_latencies = []

    # Lista para almacenar los resultados del test de TTL y consistencia
    ttl_results = []

    def on_start(self):
        """
        Esta función se ejecuta al inicio de la prueba para reestablecer las métricas.
        """
        self.cache_metrics["hit"] = 0
        self.cache_metrics["miss"] = 0
        global start_time_to_miss
        start_time_to_miss = time.time()

    @task(10)
    def get_products_load_test(self):
        """
        Escenario 1: Simula 400 usuarios concurrentes navegando por el catálogo.
        Esta tarea tiene un peso de 10, lo que significa que se ejecutará
        mucho más a menudo que las otras tareas para simular alta demanda de lectura.
        """
        start_time = time.time()

        with self.client.get("/products/available", catch_response=True) as response:
            global start_time_to_miss
            global end_time_to_miss
            end_time = time.time()
            # Verifica el encabezado X-Cache para saber si la respuesta vino de Redis.
            x_cache_header = response.headers.get('X-Cache', 'UNKNOWN')
            total_time = (end_time - start_time) * 1000  # en ms
            self.cache_metrics["time"] += total_time
            # Registra la métrica para el análisis posterior.
            if x_cache_header == 'HIT':
                self.cache_metrics["hit"] += 1
            elif x_cache_header == 'MISS':
                end_time_to_miss = time.time()
                self.cache_metrics["ttl"].append(end_time_to_miss-start_time_to_miss)
                start_time_to_miss = end_time_to_miss
                self.cache_metrics["miss"] += 1

            # Si la respuesta es exitosa (código 200), se marca como éxito.
            if response.status_code != 200:
                response.failure("Respuesta inesperada del servidor")

    @task(1)
    def update_and_verify_latency(self):
        """
        Escenario 2: Simula una actualización en tiempo real del catálogo.
        """
        # Suponiendo que el producto con ID 1 existe y se puede actualizar.

        global PRODCUCT_STOCK
        try:
            PRODCUCT_STOCK -= 1
        except (NameError, TypeError):
            PRODCUCT_STOCK = 999  # Se inicializa el stock

        product_id_to_update = "prod_006"

        # Simula una actualización del producto (POST o PUT).
        update_url = f"/products/update/{product_id_to_update}"
        update_payload = {"price": 100.0, "stock": PRODCUCT_STOCK}

        # Realiza la solicitud de actualización y marca el resultado para Locust
        with self.client.put(update_url, json=update_payload, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"La actualización falló con código {response.status_code}")
            else:
                response.success()


    @events.test_stop.add_listener
    def on_test_stop(environment, **kwargs):
        """
        Esta función se ejecuta al final de la prueba para imprimir
        un resumen de las métricas y guardarlas en un archivo de texto.
        """
        output_file = "performance_summary.txt"

        with open(output_file, "w") as f:
            # --------------------------------------------------------------------------------------
            # Escenario 1: Tasa de Aciertos de Caché
            f.write("--- Resultados de la Tasa de Aciertos de Caché (Escenario 2: Consulta y modificación productos) ---\n")
            total_cache_requests = ProductsServiceUser.cache_metrics["hit"] + ProductsServiceUser.cache_metrics["miss"]
            if total_cache_requests > 0:
                cache_hit_rate = (ProductsServiceUser.cache_metrics["hit"] / total_cache_requests) * 100
                f.write(f"Número de Cache HITs: {ProductsServiceUser.cache_metrics['hit']}\n")
                f.write(f"Número de Cache MISSs: {ProductsServiceUser.cache_metrics['miss']}\n")
                f.write(f"Tasa de Aciertos de Caché (Cache Hit Rate): {cache_hit_rate:.2f}%\n")
                f.write(f"Tiempo de respuesta promedio: {ProductsServiceUser.cache_metrics['time']/total_cache_requests:.2f}ms\n")
                f.write(f"TTL real: {statistics.mean(ProductsServiceUser.cache_metrics['ttl'][0:]):.2f}s\n")
            else:
                f.write(
                    "No se realizaron solicitudes de caché. La prueba podría haber fallado antes de la ejecución.\n")
            f.write("------------------------------------------------------------------------\n\n")


        print(f"\nResultados de la prueba consolidados en {output_file}")
