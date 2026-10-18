import time
import uuid
import base64
import requests
import docker
import pandas as pd
from redis.sentinel import Sentinel

docker_client = docker.from_env()

def get_etcd_leader():
    containers = ["etcd1", "etcd2", "etcd3"]
    for c_name in containers:
        try:
            c = docker_client.containers.get(c_name)
            res = c.exec_run("etcdctl endpoint status --cluster -w json")
            import json
            endpoints = json.loads(res.output.decode('utf-8'))
            for ep in endpoints:
                if ep['Status']['leader'] == ep['Status']['header']['member_id']:
                    leader_id = ep['Status']['leader']
                    for probe_name in containers:
                        p_res = docker_client.containers.get(probe_name).exec_run("etcdctl endpoint status -w json")
                        p_data = json.loads(p_res.output.decode('utf-8'))
                        if p_data[0]['Status']['header']['member_id'] == leader_id:
                            return probe_name
        except Exception:
            continue
    return "etcd1"

def write_etcd_http(endpoints, key, val, timeout=0.15):
    # Native etcd v3 HTTP API uses base64 encoded keys & values
    k_b64 = base64.b64encode(key.encode('utf-8')).decode('utf-8')
    v_b64 = base64.b64encode(val.encode('utf-8')).decode('utf-8')
    payload = {"key": k_b64, "value": v_b64}
    
    for url in endpoints:
        try:
            resp = requests.post(f"{url}/v3/kv/put", json=payload, timeout=timeout)
            if resp.status_code == 200:
                return True
        except Exception:
            continue
    return False

def benchmark_run(system_type, iteration, kill_delay=4.0, duration=12.0):
    records = []
    start_time = time.time()
    kill_timestamp = None
    target_container = None

    if system_type == "etcd":
        endpoints = [
            "http://127.0.0.1:2379",
            "http://127.0.0.1:22379",
            "http://127.0.0.1:32379"
        ]
        target_container = get_etcd_leader()
    else:
        sentinel = Sentinel([('127.0.0.1', 26379), ('127.0.0.1', 26380), ('127.0.0.1', 26381)], socket_timeout=0.2)
        target_container = "redis-primary"

    seq = 0
    killed = False
    run_id = str(uuid.uuid4())[:8]

    print(f"[{system_type.upper()} Run {iteration}] Active Leader to kill: {target_container}")

    while time.time() - start_time < duration:
        t_now = time.time()

        # Mid-write SIGKILL trigger
        if not killed and (t_now - start_time) >= kill_delay:
            print(f"--> [t={t_now - start_time:.2f}s] Triggering kill -9 on {target_container}...")
            c = docker_client.containers.get(target_container)
            c.kill(signal=9)
            kill_timestamp = time.time()
            killed = True

        seq += 1
        key = f"k_{run_id}_{seq}"
        val = f"v_{t_now}"
        t_sent = time.time()
        status = "FAILED"

        try:
            if system_type == "etcd":
                if write_etcd_http(endpoints, key, val, timeout=0.15):
                    status = "SUCCESS"
            else:
                master = sentinel.master_for('mymaster', socket_timeout=0.15)
                master.set(key, val)
                status = "SUCCESS"
        except Exception:
            status = "FAILED"

        t_ack = time.time()
        records.append({
            "seq": seq,
            "key": key,
            "t_sent": t_sent,
            "t_ack": t_ack,
            "latency": t_ack - t_sent,
            "status": status,
            "killed_target": target_container
        })
        time.sleep(0.005) # 200 writes/sec target rate

    df = pd.DataFrame(records)
    
    # Calculate write loss for acknowledged writes on Redis
    lost_count = 0
    if system_type == "redis":
        time.sleep(2)
        try:
            sentinel = Sentinel([('127.0.0.1', 26379), ('127.0.0.1', 26380), ('127.0.0.1', 26381)], socket_timeout=1.0)
            master = sentinel.master_for('mymaster', socket_timeout=1.0)
            successful_keys = df[df['status'] == 'SUCCESS']['key'].tolist()
            for k in successful_keys:
                if not master.exists(k):
                    lost_count += 1
        except Exception:
            pass

    return df, kill_timestamp, lost_count
