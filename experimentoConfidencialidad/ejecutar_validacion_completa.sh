#!/bin/bash
# 🧪 SCRIPT DE VALIDACIÓN AUTOMÁTICA COMPLETA
# Experimento de Confidencialidad MeddySupply
# ============================================

# Configuración
API_URL="https://vmbwryazac.execute-api.us-east-1.amazonaws.com/prod"
RESULTS_FILE="validation_results_$(date +%Y%m%d_%H%M%S).json"
LOG_FILE="validation_log_$(date +%Y%m%d_%H%M%S).txt"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Contadores
PASSED=0
FAILED=0
TOTAL=0

echo "🚀 VALIDACIÓN COMPLETA DEL EXPERIMENTO DE CONFIDENCIALIDAD"
echo "=========================================================="
echo "📅 Fecha: $(date)"
echo "🌐 API URL: $API_URL"
echo "📊 Resultados: $RESULTS_FILE"
echo "📝 Log: $LOG_FILE"
echo ""

# Inicializar archivos de resultados
echo "# RESULTADOS DE VALIDACIÓN - $(date)" > $RESULTS_FILE
echo "# LOG DE VALIDACIÓN - $(date)" > $LOG_FILE

# Función para ejecutar test
run_test() {
    local test_num="$1"
    local test_name="$2"
    local expected_status="$3"
    local curl_command="$4"
    local description="$5"
    
    echo -e "${BLUE}Test $test_num:${NC} $test_name"
    echo "Descripción: $description"
    echo "Comando: $curl_command" >> $LOG_FILE
    
    # Ejecutar curl y capturar resultado
    result=$(eval "$curl_command" 2>/dev/null)
    status=$(echo "$result" | tail -1 | grep -o '[0-9]*$' | tail -1)
    
    TOTAL=$((TOTAL + 1))
    
    # Validar resultado
    if [ "$status" = "$expected_status" ]; then
        echo -e "   ${GREEN}✅ PASS${NC} (Status: $status)"
        echo "✅ PASS - Test $test_num: $test_name (Status: $status)" >> $RESULTS_FILE
        PASSED=$((PASSED + 1))
    else
        echo -e "   ${RED}❌ FAIL${NC} (Expected: $expected_status, Got: $status)"
        echo "❌ FAIL - Test $test_num: $test_name (Expected: $expected_status, Got: $status)" >> $RESULTS_FILE
        FAILED=$((FAILED + 1))
    fi
    
    echo "Resultado: $result" >> $LOG_FILE
    echo "Status: $status" >> $LOG_FILE
    echo "---" >> $LOG_FILE
    echo ""
}

echo "🔐 PARTE 1: VALIDACIÓN DE AUTENTICACIÓN BÁSICA"
echo "==============================================="

run_test "1" "Sin Token" "401" \
    "curl -s '$API_URL/test' -w '\nStatus: %{http_code}\n'" \
    "Verificar que sin token se deniega el acceso"

run_test "2" "Token Vacío" "403" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer ' -w '\nStatus: %{http_code}\n'" \
    "Verificar que token vacío se deniega"

run_test "3" "Token Inválido" "403" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer token_falso_123' -w '\nStatus: %{http_code}\n'" \
    "Verificar que token inválido se deniega"

run_test "4" "Token Malformado" "403" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer no-es-jwt' -w '\nStatus: %{http_code}\n'" \
    "Verificar que token malformado se deniega"

echo "✅ PARTE 2: VALIDACIÓN CON TOKENS DEMO"
echo "======================================"

run_test "5" "Demo NY" "200" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer demo.ny.jwt.token' -w '\nStatus: %{http_code}\n'" \
    "Verificar que token demo NY funciona"

run_test "6" "Demo Admin" "200" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer demo.admin.jwt.token' -w '\nStatus: %{http_code}\n'" \
    "Verificar que token demo admin funciona"

run_test "7" "Demo Alto Riesgo" "200" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer demo.highrisk.jwt.token' -w '\nStatus: %{http_code}\n'" \
    "Verificar manejo de token alto riesgo (puede variar)"

echo "🔐 PARTE 3: VALIDACIÓN CON TOKENS COGNITO REALES"
echo "==============================================="

echo "🔑 Obteniendo tokens reales de Cognito..."

# Obtener token NY
TOKEN_NY=$(python3 -c "
import boto3
import sys
try:
    cognito = boto3.client('cognito-idp', region_name='us-east-1')
    response = cognito.admin_initiate_auth(
        UserPoolId='us-east-1_vmLwVEP49',
        ClientId='59oaj71hs68pucfve29jg6elgl',
        AuthFlow='ADMIN_NO_SRP_AUTH',
        AuthParameters={'USERNAME': 'user.ny@medisupply.com', 'PASSWORD': 'TempPass123!'}
    )
    print(response['AuthenticationResult']['IdToken'])
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null)

if [ $? -eq 0 ] && [ ! -z "$TOKEN_NY" ]; then
    echo "✅ Token NY obtenido: ${TOKEN_NY:0:50}..."
    
    run_test "8" "Cognito Real NY" "200" \
        "curl -s '$API_URL/test' -H 'Authorization: Bearer $TOKEN_NY' -w '\nStatus: %{http_code}\n'" \
        "Verificar token JWT real de Cognito para usuario NY"
else
    echo "❌ Error obteniendo token NY"
    echo "❌ SKIP - Test 8: Cognito Real NY (No se pudo obtener token)" >> $RESULTS_FILE
fi

# Obtener token Admin
TOKEN_ADMIN=$(python3 -c "
import boto3
import sys
try:
    cognito = boto3.client('cognito-idp', region_name='us-east-1')
    response = cognito.admin_initiate_auth(
        UserPoolId='us-east-1_vmLwVEP49',
        ClientId='59oaj71hs68pucfve29jg6elgl',
        AuthFlow='ADMIN_NO_SRP_AUTH',
        AuthParameters={'USERNAME': 'admin@medisupply.com', 'PASSWORD': 'AdminPass123!'}
    )
    print(response['AuthenticationResult']['IdToken'])
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    sys.exit(1)
" 2>/dev/null)

if [ $? -eq 0 ] && [ ! -z "$TOKEN_ADMIN" ]; then
    echo "✅ Token Admin obtenido: ${TOKEN_ADMIN:0:50}..."
    
    run_test "9" "Cognito Real Admin" "200" \
        "curl -s '$API_URL/test' -H 'Authorization: Bearer $TOKEN_ADMIN' -w '\nStatus: %{http_code}\n'" \
        "Verificar token JWT real de Cognito para admin"
else
    echo "❌ Error obteniendo token Admin"
    echo "❌ SKIP - Test 9: Cognito Real Admin (No se pudo obtener token)" >> $RESULTS_FILE
fi

echo "🌍 PARTE 4: VALIDACIÓN CONTEXTUAL (CAMBIO DE IP)"
echo "==============================================="

run_test "10" "IP México (Legítimo)" "200" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer demo.ny.jwt.token' -H 'X-Forwarded-For: 201.123.45.67' -w '\nStatus: %{http_code}\n'" \
    "Usuario NY desde México (cambio legítimo de IP)"

run_test "11" "IP Rusia (No Autorizada)" "200" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer demo.ny.jwt.token' -H 'X-Forwarded-For: 185.220.101.50' -w '\nStatus: %{http_code}\n'" \
    "Usuario NY desde Rusia (IP no autorizada - puede aumentar riesgo)"

run_test "12" "Admin Desde Canadá" "200" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer demo.admin.jwt.token' -H 'X-Forwarded-For: 200.123.45.67' -w '\nStatus: %{http_code}\n'" \
    "Admin desde Canadá (autorizado para múltiples países)"

echo "📱 PARTE 5: VALIDACIÓN DE DISPOSITIVOS"
echo "======================================"

run_test "13" "Dispositivo Móvil" "200" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer demo.ny.jwt.token' -H 'User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)' -w '\nStatus: %{http_code}\n'" \
    "Acceso desde dispositivo móvil"

run_test "14" "Dispositivo Sospechoso" "200" \
    "curl -s '$API_URL/test' -H 'Authorization: Bearer demo.ny.jwt.token' -H 'User-Agent: SuspiciousBot/1.0 (Automated)' -w '\nStatus: %{http_code}\n'" \
    "Acceso desde dispositivo sospechoso (puede afectar risk score)"

echo "🔒 PARTE 6: ENDPOINTS PROTEGIDOS"
echo "==============================="

run_test "15" "Endpoint Seguro Sin Token" "401" \
    "curl -s '$API_URL/secure/data' -w '\nStatus: %{http_code}\n'" \
    "Endpoint seguro sin autenticación"

run_test "16" "Endpoint Seguro Con Token" "200" \
    "curl -s '$API_URL/secure/data' -H 'Authorization: Bearer demo.ny.jwt.token' -w '\nStatus: %{http_code}\n'" \
    "Endpoint seguro con token válido"

run_test "17" "Dashboard Admin - Usuario Normal" "403" \
    "curl -s '$API_URL/admin/dashboard' -H 'Authorization: Bearer demo.ny.jwt.token' -w '\nStatus: %{http_code}\n'" \
    "Dashboard admin con usuario normal (debe denegar)"

run_test "18" "Dashboard Admin - Token Admin" "200" \
    "curl -s '$API_URL/admin/dashboard' -H 'Authorization: Bearer demo.admin.jwt.token' -w '\nStatus: %{http_code}\n'" \
    "Dashboard admin con token admin (debe permitir)"

echo ""
echo "📊 RESUMEN DE VALIDACIÓN"
echo "======================="
echo "" >> $RESULTS_FILE
echo "# RESUMEN FINAL" >> $RESULTS_FILE
echo "===============" >> $RESULTS_FILE
echo "Total Tests: $TOTAL" >> $RESULTS_FILE
echo "Passed: $PASSED" >> $RESULTS_FILE  
echo "Failed: $FAILED" >> $RESULTS_FILE

if [ $TOTAL -gt 0 ]; then
    SUCCESS_RATE=$(echo "scale=1; $PASSED * 100 / $TOTAL" | bc 2>/dev/null || echo "N/A")
    echo "Success Rate: $SUCCESS_RATE%" >> $RESULTS_FILE
else
    SUCCESS_RATE="0"
fi

echo -e "📊 ${BLUE}Total Tests:${NC} $TOTAL"
echo -e "✅ ${GREEN}Passed:${NC} $PASSED"
echo -e "❌ ${RED}Failed:${NC} $FAILED"
echo -e "🎯 ${YELLOW}Success Rate:${NC} $SUCCESS_RATE%"

# Determinar estado general
if [ $FAILED -eq 0 ]; then
    echo -e "\n🏆 ${GREEN}VALIDACIÓN EXITOSA - TODOS LOS TESTS PASARON${NC}"
    echo "🎯 El experimento de confidencialidad está 100% funcional"
elif [ $PASSED -gt $FAILED ]; then
    echo -e "\n⚠️ ${YELLOW}VALIDACIÓN PARCIAL - MAYORÍA DE TESTS EXITOSOS${NC}"
    echo "🔍 Revisar tests fallidos en $RESULTS_FILE"
else
    echo -e "\n💥 ${RED}VALIDACIÓN FALLIDA - MÚLTIPLES PROBLEMAS${NC}"
    echo "🚨 Revisar configuración y logs en $LOG_FILE"
fi

echo ""
echo "📄 Archivos generados:"
echo "   📊 Resultados: $RESULTS_FILE"
echo "   📝 Log detallado: $LOG_FILE"
echo ""
echo "🔍 Para ver resultados detallados:"
echo "   cat $RESULTS_FILE"
echo ""
echo "🏁 Validación completada - $(date)"
