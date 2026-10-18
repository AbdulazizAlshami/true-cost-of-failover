import time
import uuid
import sys
import os
import pandas as pd
from redis.sentinel import Sentinel

system_mode = sys.argv[1] # aggressive or conservative
iteration = sys.argv[2]
kill_delay = 4.0
duration = 14.0

# Connect directly inside the docker network
sentinel = Sentinel([
    ('sentinel1', 26379),
    ('sentinel2', 26379),
    ('sentinel3', 26379)
], socket_timeout=0.15)

records = []
start_time = time.time()
seq = 0
run_id = str(uuid.uuid4())[:8]

while time.time() - start_time < duration:
    t_now = time.time()
    seq += 1
    key = f"rk_{run_id}_{seq}"
    val = f"rv_{t_now}"
    t_sent = time.time()
    status = "FAILED"

    try:
        # Request master with low timeout
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
        "status": status
    })
    time.sleep(0.005)

df = pd.DataFrame(records)
os.makedirs("/results", exist_ok=True)
df.to_csv(f"/results/redis_{system_mode}_{iteration}.csv", index=False)

# Check acknowledged write loss
time.sleep(2)
lost_count = 0
try:
    master = sentinel.master_for('mymaster', socket_timeout=1.0)
    success_keys = df[df['status'] == 'SUCCESS']['key'].tolist()
    for k in success_keys:
        if not master.exists(k):
            lost_count += 1
except Exception:
    pass

with open(f"/results/redis_{system_mode}_{iteration}.meta", "w") as f:
    # We will pass the kill timestamp into this file
    f.write(f"{lost_count}")

print(f"Finished Redis {system_mode} run {iteration}. Lost writes: {lost_count}")
