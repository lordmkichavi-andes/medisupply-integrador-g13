#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stack import ExperimentoStack

app = cdk.App()

# Stack principal para los experimentos
ExperimentoStack(app, "ExperimentoStack",
    # Configuración del ambiente
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION')
    ),
    synthesizer=cdk.DefaultStackSynthesizer(qualifier='exp'),
    # Configuración específica para experimentos
    experiment_config={
        'latency': {
            'enabled': True,
            'services': ['products'],
            'infrastructure': ['cache', 'load_balancer']
        }
    }
)

app.synth()