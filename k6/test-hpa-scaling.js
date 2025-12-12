import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    // Fase 1: Calma (2 pods)
    { duration: '30s', target: 10 },

    // Fase 2: Carga média (deve escalar para 3-4 pods)
    { duration: '1m', target: 50 },

    // Fase 3: Carga alta (deve escalar para 5-8 pods)
    { duration: '2m', target: 100 },

    // Fase 4: Pico (testa max replicas)
    { duration: '1m', target: 150 },

    // Fase 5: Descida (deve desescalar)
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.1'],    // <10% falhas (mais tolerante)
    http_req_duration: ['p(95)<5000'], // 95% < 5s
  },
};

export default function () {
  const url = 'https://testes-de-widgets.sandbox.bonde.org';

  const res = http.get(url, {
    tags: { endpoint: 'homepage' },
    timeout: '30s',
  });

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time OK': (r) => r.timings.duration < 10000,
  });

  // Simula tempo de pensar do usuário
  sleep(Math.random() * 3 + 1);
}