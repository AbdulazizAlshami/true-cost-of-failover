#!/usr/bin/env bash
set -e

CONFIGS=(
  "aggressive 1000 2000"
  "conservative 5000 10000"
)

mkdir -p results

for cfg in "${CONFIGS[@]}"; do
  read -r NAME REDIS_DOWN REDIS_FAIL <<< "$cfg"
  echo "=========================================="
  echo " Running Redis Suite: $NAME"
  echo " Down-after: ${REDIS_DOWN}ms | Failover: ${REDIS_FAIL}ms"
  echo "=========================================="

  sed -e "s/DOWN_AFTER_MS/$REDIS_DOWN/g" -e "s/FAILOVER_TIMEOUT_MS/$REDIS_FAIL/g" redis/sentinel.template.conf > redis/sentinel1.conf
  cp redis/sentinel1.conf redis/sentinel2.conf
  cp redis/sentinel1.conf redis/sentinel3.conf

  docker compose -f docker-compose-redis.yml down -v 2>/dev/null || true
  docker compose -f docker-compose-redis.yml up -d
  sleep 4

  for i in $(seq 1 20); do
    echo "--- Redis $NAME Run $i/20 ---"
    
    # Run the client in the background inside the Docker network
    docker run -d --rm \
      --name redis-bench-client \
      --network failover-benchmark_redis-net \
      -v "$(pwd)/redis/run_redis_inside_docker.py:/app.py" \
      -v "$(pwd)/results:/results" \
      python:3.11-slim bash -c "pip install redis pandas -q && python /app.py $NAME $i"

    # Wait 4.0 seconds into the workload, then trigger SIGKILL (kill -9) on primary
    sleep 4.0
    KILL_TIME=$(python3 -c "import time; print(time.time())")
    echo "--> [t=4.0s] Issuing SIGKILL to redis-primary..."
    docker kill -s 9 redis-primary

    # Wait for the client run to complete
    docker wait redis-bench-client 2>/dev/null || true
    
    # Update meta file with exact kill timestamp: <kill_time>,<lost_count>
    LOST_COUNT=$(cat "results/redis_${NAME}_${i}.meta" 2>/dev/null || echo "0")
    echo "${KILL_TIME},${LOST_COUNT}" > "results/redis_${NAME}_${i}.meta"

    # Restore primary for next iteration
    docker compose -f docker-compose-redis.yml up -d
    sleep 3
  done

  docker compose -f docker-compose-redis.yml down -v
done
