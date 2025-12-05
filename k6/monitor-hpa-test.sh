#!/bin/bash
# monitor-hpa-test.sh

echo "=== MONITORAMENTO HPA DURANTE TESTE ==="
echo "Executando em 3... 2... 1..."
echo

# Tempo total do teste (5.5 minutos + margem)
TOTAL_TIME=400  # ~6.5 minutos

# Inicia o k6 em background
echo "🔥 Iniciando teste de carga..."
k6 run test-hpa-scaling.js > k6-output.log 2>&1 &
K6_PID=$!

# Monitoramento
echo "📊 Iniciando monitoramento (atualiza a cada 10s)..."
echo

for i in $(seq 1 $((TOTAL_TIME / 10))); do
  clear
  echo "[$(date '+%H:%M:%S')] - Passo $((i*10))s/$TOTAL_TIME""s"
  echo "════════════════════════════════════════════════"
  
  # 1. HPA Status
  echo "⚡ HPA STATUS:"
  kubectl get hpa -n sandbox 2>/dev/null || echo "   HPA não encontrado"
  echo
  
  # 2. Pods
  echo "📦 PODS (public):"
  kubectl get pods -n sandbox -l App=public --no-headers 2>/dev/null | \
    awk '{print "   - " $1 ": " $2 " (Running " $5 ")"}' || \
    echo "   Nenhum pod encontrado"
  
  POD_COUNT=$(kubectl get pods -n sandbox -l App=public --no-headers 2>/dev/null | wc -l | tr -d ' ')
  echo "   Total pods: $POD_COUNT/8"
  echo
  
  # 3. CPU Usage
  echo "💻 CPU USAGE:"
  kubectl top pods -n sandbox -l App=public --no-headers 2>/dev/null | \
    while read line; do
      pod=$(echo $line | awk '{print $1}')
      cpu=$(echo $line | awk '{print $2}')
      mem=$(echo $line | awk '{print $3}')
      echo "   - $pod: CPU $cpu, MEM $mem"
    done || echo "   ⏳ Aguardando métricas..."
  echo
  
  # 4. Eventos recentes
  echo "📝 EVENTOS RECENTES:"
  kubectl get events -n sandbox \
    --field-selector involvedObject.name=public-hpa \
    --sort-by='.lastTimestamp' \
    --tail=2 2>/dev/null | grep -v "^\s*$" || \
    echo "   Nenhum evento recente"
  echo
  
  # 5. HPA details (a cada 30s para não sobrecarregar)
  if (( i % 3 == 0 )); then
    echo "🔍 HPA DETAILS (current/target):"
    kubectl describe hpa public-hpa -n sandbox 2>/dev/null | \
      grep -A2 "Metrics:" | tail -1 | \
      sed 's/^/   /' || echo "   Detalhes não disponíveis"
    echo
  fi
  
  echo "════════════════════════════════════════════════"
  echo "Próxima atualização em 10s (Ctrl+C para interromper)"
  sleep 10
done

# Finalização
echo ""
echo "✅ Teste concluído!"
echo ""
echo "📋 Resultados k6:"
tail -20 k6-output.log

# Limpeza
kill $K6_PID 2>/dev/null