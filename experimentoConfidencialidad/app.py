#!/usr/bin/env python3
import os
import aws_cdk as cdk
from experimento.experimento_stack_v5 import ExperimentoStackV5

app = cdk.App()

# Stack principal para los experimentos
ExperimentoStackV5(app, "ExperimentoStackV5",
    # Configuración del ambiente
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'), 
        region=os.getenv('CDK_DEFAULT_REGION')
    ),
    synthesizer=cdk.DefaultStackSynthesizer(qualifier='exp'),
    # Configuración específica para experimentos
    experiment_config={
        'confidentiality': {
            'enabled': True,
            'services': ['auth'],
            'infrastructure': ['cognito', 'lambda_authorizer']
        },
        'latency': {
            'enabled': True,
            'services': ['products'],
            'infrastructure': ['cache', 'load_balancer']
        }
    }
)

app.synth()