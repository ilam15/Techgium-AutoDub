import redis
import json

REDIS_CLIENT = redis.Redis(host='localhost', port=6379, db=0)

print("--- Pipeline Keys ---")
keys = REDIS_CLIENT.keys("pipeline:*")
for k in keys:
    k_str = k.decode()
    if ":results" in k_str:
        continue
    data = REDIS_CLIENT.hgetall(k)
    print(f"Key: {k_str}")
    for field, val in data.items():
        print(f"  {field.decode()}: {val.decode()}")

print("\n--- Recent Results Summary ---")
for k in keys:
    k_str = k.decode()
    if ":results" in k_str:
        results = REDIS_CLIENT.hgetall(k)
        print(f"Key: {k_str} (Count: {len(results)})")
