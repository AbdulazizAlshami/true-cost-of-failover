#!/usr/bin/env bash
set -e

CONFIGS=(
  "aggressive 100 1000 1000 2000"
  "conservative 500 5000 5000 10000"
)

mkdir -p results

for cfg in "${CONFIGS[@]}"; do
  read -r NAME ETCD_HB ETCD_ELECT REDIS_DOWN REDIS_FAIL <<< "$cfg"
  echo "=========================================="
  echo " Running Suite: $NAME"
  echo " etcd: $ETCD_HB / $ETCD_ELECT ms"
  echo " redis: $REDIS_DOWN / $REDIS_FAIL ms"
  echo "=========================================="

  # 1. etcd runs
  ETCD_HEARTBEAT=$ETCD_HB ETCD_ELECTION=$ETCD_ELECT docker compose -f docker-compose-etcd.yml up -d
  sleep 5
  
  for i in $(seq 1 20); do
    echo "--- etcd $NAME Run $i/20 ---"
    python3 -c "from scripts.runner import benchmark_run; df, kt, _ = benchmark_run('etcd', $i); df.to_csv('results/etcd_${NAME}_${i}.csv', index=False); open('results/etcd_${NAME}_${i}.meta', 'w').write(str(kt))"
    ETCD_HEARTBEAT=$ETCD_HB ETCD_ELECTION=$ETCD_ELECT docker compose -f docker-compose-etcd.yml up -d
    sleep 3
  done
  docker compose -f docker-compose-etcd.yml down -v

  # 2. Redis Sentinel runs
  sed -e "s/DOWN_AFTER_MS/$REDIS_DOWN/g" -e "s/FAILOVER_TIMEOUT_MS/$REDIS_FAIL/g" redis/sentinel.template.conf > redis/sentinel1.conf
  cp redis/sentinel1.conf redis/sentinel2.conf
  cp redis/sentinel1.conf redis/sentinel3.conf

  docker compose -f docker-compose-redis.yml up -d
  sleep 5

  for i in $(seq 1 20); do
    echo "--- redis $NAME Run $i/20 ---"
    python3 -c "from scripts.runner import benchmark_run; df, kt, lost = benchmark_run('redis', $i); df.to_csv('results/redis_${NAME}_${i}.csv', index=False); open('results/redis_${NAME}_${i}.meta', 'w').write(f'{kt},{lost}')"
    docker compose -f docker-compose-redis.yml up -d
    sleep 3
  done
  docker compose -f docker-compose-redis.yml down -v
done
