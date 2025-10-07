#!/usr/bin/env python3
import os
import aws_cdk as cdk
from stack import MediSupplyStack

app = cdk.App()

# Stack principal para los experimentos
MediSupplyStack(app, "MediSupplyStack",
                # Configuración del ambiente
                env=cdk.Environment(
                    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
                    region=os.getenv('CDK_DEFAULT_REGION')
                ),
                synthesizer=cdk.DefaultStackSynthesizer(qualifier='exp'),
                # Configuración específica para experimentos
                config={
                    'offer-manager': {'enabled': False},
                    'orders': {'enabled': False},
                    'products': {'enabled': True},
                    'reports': {'enabled': False},
                    'routes': {'enabled': False},
                    'users': {'enabled': False},
                }
                )

app.synth()