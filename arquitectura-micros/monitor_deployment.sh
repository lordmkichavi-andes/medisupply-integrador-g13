#!/bin/bash

# Script para monitorear el progreso del despliegue de MediSupplyStack
# Actualiza cada 30 segundos

STACK_NAME="MediSupplyStack"
UPDATE_INTERVAL=30

echo "🚀 Monitoreando el despliegue de MediSupplyStack..."
echo "📊 Actualizando cada ${UPDATE_INTERVAL} segundos"
echo "⏰ Iniciado: $(date)"
echo "=========================================="

while true; do
    # Obtener el estado del stack
    STACK_STATUS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --query 'Stacks[0].StackStatus' --output text 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        echo "❌ Error: No se pudo obtener el estado del stack"
        sleep $UPDATE_INTERVAL
        continue
    fi
    
    # Contar recursos completados
    COMPLETED=$(aws cloudformation describe-stack-events --stack-name $STACK_NAME --query 'StackEvents[?ResourceStatus==`CREATE_COMPLETE`].LogicalResourceId' --output text 2>/dev/null | wc -w)
    
    # Contar recursos en progreso (únicos)
    IN_PROGRESS=$(aws cloudformation describe-stack-events --stack-name $STACK_NAME --query 'StackEvents[?ResourceStatus==`CREATE_IN_PROGRESS`].LogicalResourceId' --output text 2>/dev/null | tr ' ' '\n' | sort | uniq | wc -l)
    
    # Contar recursos fallidos
    FAILED=$(aws cloudformation describe-stack-events --stack-name $STACK_NAME --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].LogicalResourceId' --output text 2>/dev/null | wc -w)
    
    # Obtener el tiempo actual
    CURRENT_TIME=$(date '+%H:%M:%S')
    
    # Mostrar progreso
    echo "⏰ $CURRENT_TIME | 📊 Estado: $STACK_STATUS"
    echo "✅ Completados: $COMPLETED recursos"
    echo "🔄 En progreso: $IN_PROGRESS recursos"
    if [ $FAILED -gt 0 ]; then
        echo "❌ Fallidos: $FAILED recursos"
    fi
    
    # Calcular porcentaje aproximado (asumiendo ~80 recursos totales)
    TOTAL_ESTIMATED=80
    PERCENTAGE=$((COMPLETED * 100 / TOTAL_ESTIMATED))
    echo "📈 Progreso estimado: $PERCENTAGE%"
    
    # Mostrar recursos en progreso actual
    if [ $IN_PROGRESS -gt 0 ]; then
        echo "🔄 Recursos en progreso:"
        aws cloudformation describe-stack-events --stack-name $STACK_NAME --query 'StackEvents[?ResourceStatus==`CREATE_IN_PROGRESS`].LogicalResourceId' --output text 2>/dev/null | tr ' ' '\n' | sort | uniq | head -5 | sed 's/^/   - /'
        if [ $IN_PROGRESS -gt 5 ]; then
            echo "   ... y $((IN_PROGRESS - 5)) más"
        fi
    fi
    
    echo "=========================================="
    
    # Verificar si el stack está completo
    if [[ "$STACK_STATUS" == "CREATE_COMPLETE" ]]; then
        echo "🎉 ¡DESPLIEGUE COMPLETADO EXITOSAMENTE!"
        echo "✅ Todos los recursos han sido creados"
        break
    elif [[ "$STACK_STATUS" == "CREATE_FAILED" ]] || [[ "$STACK_STATUS" == "ROLLBACK_IN_PROGRESS" ]] || [[ "$STACK_STATUS" == "ROLLBACK_COMPLETE" ]]; then
        echo "❌ DESPLIEGUE FALLIDO"
        echo "🔍 Estado: $STACK_STATUS"
        echo "📋 Revisa los logs para más detalles"
        break
    fi
    
    # Esperar antes de la siguiente actualización
    sleep $UPDATE_INTERVAL
done

echo "🏁 Monitoreo finalizado: $(date)"
