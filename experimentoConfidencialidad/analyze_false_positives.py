#!/usr/bin/env python3
"""
Analizador de falsos positivos en logs de CloudWatch
Identifica usuarios legítimos que están siendo denegados incorrectamente
"""

import boto3
import json
from datetime import datetime, timedelta

def analyze_false_positives():
    """Analizar logs para identificar posibles falsos positivos"""
    
    # Patrones que sugieren falsos positivos:
    false_positive_patterns = {
        'legitimate_travel': {
            'description': 'Usuario viajando legítimamente',
            'indicators': [
                'risk_score entre 0.4-0.8',
                'denegación por geografía',
                'usuario con historial limpio'
            ]
        },
        'emergency_access': {
            'description': 'Acceso médico de emergencia',
            'indicators': [
                'fuera de horario laboral',
                'departamento médico',
                'IP desde hospital/clínica'
            ]
        },
        'remote_worker': {
            'description': 'Trabajador remoto legítimo',
            'indicators': [
                'IP pública nueva',
                'dispositivo conocido',
                'patrón de trabajo remoto'
            ]
        }
    }
    
    print("🔍 ANÁLISIS DE FALSOS POSITIVOS")
    print("=" * 50)
    
    for pattern_name, pattern_info in false_positive_patterns.items():
        print(f"\n📋 {pattern_info['description']}:")
        for indicator in pattern_info['indicators']:
            print(f"   • {indicator}")
    
    print(f"\n💡 RECOMENDACIONES:")
    print("1. Implementar MFA challenge para cambios geográficos")
    print("2. Excepciones por departamento (médico, emergencias)")
    print("3. Registro de dispositivos conocidos")
    print("4. Umbrales adaptativos por contexto")
    print("5. Proceso de whitelist temporal para viajes")

if __name__ == "__main__":
    analyze_false_positives()
