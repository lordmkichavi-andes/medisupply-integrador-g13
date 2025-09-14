"""
Configuración específica para los experimentos de confidencialidad y latencia
"""

EXPERIMENTS_CONFIG = {
    'confidentiality': {
        'name': 'Confidentiality Experiment',
        'description': 'Validar confidencialidad de información sensible',
        'target_services': ['auth'],
        'infrastructure': ['cognito', 'lambda_authorizer'],
        'metrics': {
            'authentication_success_rate': 0.95,
            'authorization_failure_rate': 0.05
        },
        'test_scenarios': [
            'authenticated_user_access',
            'unauthenticated_user_denied',
            'insufficient_permissions_denied',
            'expired_token_denied',
            'invalid_token_denied'
        ]
    },
    'latency': {
        'name': 'Latency Experiment',
        'description': 'Validar latencia < 2 segundos',
        'target_services': ['products'],
        'infrastructure': ['cache', 'load_balancer'],
        'metrics': {
            'response_time_p95': 2000,  # ms
            'response_time_p99': 2000   # ms
        },
        'test_scenarios': [
            'simple_query_by_id',
            'complex_query_with_filters',
            'query_with_joins',
            'concurrent_100_users',
            'concurrent_400_users'
        ]
    }
}

# Configuración de servicios para experimentos
SERVICES_CONFIG = {
    'auth': {
        'name': 'Auth Service',
        'description': 'Servicio de autenticación y autorización',
        'port': 8080,
        'cpu': 256,
        'memory': 512,
        'environment': {
            'SERVICE_NAME': 'auth-service',
            'LOG_LEVEL': 'INFO'
        }
    },
    'products': {
        'name': 'Products Service',
        'description': 'Servicio de gestión de productos',
        'port': 8080,
        'cpu': 256,
        'memory': 512,
        'environment': {
            'SERVICE_NAME': 'products-service',
            'LOG_LEVEL': 'INFO'
        }
    }
}

# Configuración de infraestructura
INFRASTRUCTURE_CONFIG = {
    'vpc': {
        'cidr': '10.0.0.0/16',
        'max_azs': 2,
        'nat_gateways': 1
    },
    'rds': {
        'instance_class': 'db.t3.micro',
        'engine': 'postgres',
        'version': '13.7',
        'allocated_storage': 20
    },
    'cache': {
        'node_type': 'cache.t3.micro',
        'num_cache_nodes': 1,
        'engine': 'redis',
        'version': '6.x'
    },
    'ecs': {
        'cluster_name': 'experimento-cluster',
        'fargate_spot': False
    }
}
