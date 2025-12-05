import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';


// Configuração
export const options = {
  stages: [
    // Rampa gradual - 5 minutos
    { duration: '1m', target: 10 },    // 0 → 10 usuários
    { duration: '2m', target: 50 },    // 10 → 50 usuários  
    { duration: '2m', target: 100 },   // 50 → 100 usuários

    // Pico sustentado - 5 minutos
    { duration: '5m', target: 200 },   // 100 → 200 usuários

    // Rampa de descida - 5 minutos
    { duration: '2m', target: 50 },    // 200 → 50 usuários
    { duration: '3m', target: 0 },     // 50 → 0 usuários
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],    // <1% de falhas
    http_req_duration: ['p(95)<2000'], // 95% < 2s
  },
};

// Métricas customizadas
const failureRate = new Rate('failed_requests');

export default function () {
  const url = 'https://testes-de-widgets.sandbox.bonde.org';
  
  // Cenário 1: Página inicial
  const res1 = http.get(url, {
    tags: { endpoint: 'homepage' },
  });
  
  check(res1, {
    'status is 200': (r) => r.status === 200,
    'response time < 2s': (r) => r.timings.duration < 2000,
  });
  
  failureRate.add(res1.status !== 200);
  
  // Pequena pausa entre requests
  sleep(Math.random() * 2);
}