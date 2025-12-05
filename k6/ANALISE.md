Resultados test-stress:
```
  █ THRESHOLDS 

    http_req_duration
    ✗ 'p(95)<2000' p(95)=31.33s

    http_req_failed
    ✗ 'rate<0.01' rate=53.88%


  █ TOTAL RESULTS 

    checks_total.......: 20076  22.282125/s
    checks_succeeded...: 43.28% 8690 out of 20076
    checks_failed......: 56.71% 11386 out of 20076

    ✗ status is 200
      ↳  46% — ✓ 4629 / ✗ 5409
    ✗ response time < 2s
      ↳  40% — ✓ 4061 / ✗ 5977

    CUSTOM
    failed_requests................: 53.88% 5409 out of 10038

    HTTP
    http_req_duration..............: avg=6.83s min=140.72ms med=3.14s max=53.25s p(90)=27.43s p(95)=31.33s
      { expected_response:true }...: avg=4.34s min=383.81ms med=3.12s max=32.23s p(90)=8.95s  p(95)=12.51s
    http_req_failed................: 53.88% 5409 out of 10038
    http_reqs......................: 10038  11.141062/s

    EXECUTION
    iteration_duration.............: avg=7.85s min=155.14ms med=3.77s max=54.8s  p(90)=28.3s  p(95)=32.45s
    iterations.....................: 10037  11.139953/s
    vus............................: 1      min=1             max=200
    vus_max........................: 200    min=200           max=200

    NETWORK
    data_received..................: 273 MB 303 kB/s
    data_sent......................: 1.3 MB 1.4 kB/s
```

Resultados test-hpa-scaling:
```
    █ THRESHOLDS 

    http_req_duration
    ✓ 'p(95)<5000' p(95)=2.13s

    http_req_failed
    ✓ 'rate<0.1' rate=0.03%


    █ TOTAL RESULTS 

    checks_total.......: 13234  36.510932/s
    checks_succeeded...: 99.98% 13232 out of 13234
    checks_failed......: 0.01%  2 out of 13234

    ✗ status is 200
      ↳  99% — ✓ 6615 / ✗ 2
    ✓ response time OK

    HTTP
    http_req_duration..............: avg=1.13s min=162.95ms med=998.95ms max=8.54s  p(90)=1.76s p(95)=2.13s
      { expected_response:true }...: avg=1.13s min=511.26ms med=999.29ms max=8.54s  p(90)=1.76s p(95)=2.13s
    http_req_failed................: 0.03%  2 out of 6617
    http_reqs......................: 6617   18.255466/s

    EXECUTION
    iteration_duration.............: avg=3.63s min=1.55s    med=3.6s     max=12.04s p(90)=4.89s p(95)=5.26s
    iterations.....................: 6617   18.255466/s
    vus............................: 1      min=1         max=150
    vus_max........................: 150    min=150       max=150

    NETWORK
    data_received..................: 389 MB 1.1 MB/s
    data_sent......................: 1.3 MB 3.5 kB/s
```

Resultados POSITIVOS:
- ✅ 0.03% de falhas (vs 53.88% antes)
- ✅ p(95)=2.13s (vs 31.33s antes)
- ✅ CPU target: 3%/70% (muito abaixo do limite)
- ✅ Escalou para 8 pods durante o pico