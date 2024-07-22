import time
import redis
import os
import uuid

INSTANCE_ID = str(uuid.uuid4())
ROLE = 'standby'  # Initial role

def send_heartbeat():
    r = redis.StrictRedis(host='localhost', port=6379)
    while True:
        if ROLE == 'active':
            r.set('heartbeat', 'active', ex=10)
        time.sleep(5)

def check_heartbeat():
    global ROLE
    r = redis.StrictRedis(host='localhost', port=6379)
    while True:
        heartbeat = r.get('heartbeat')
        if heartbeat is None and ROLE == 'standby':
            print(f"Instance {INSTANCE_ID}: Active instance is down. Attempting to become active.")
            if try_to_become_leader(r):
                print(f"Instance {INSTANCE_ID}: Promoted to active.")
                ROLE = 'active'
                # Start the Flash application service or perform any necessary promotion actions
                os.system('systemctl start flash_application.service')  # Example command
        elif heartbeat is not None and ROLE == 'active':
            print(f"Instance {INSTANCE_ID}: Detected another active instance. Switching to standby.")
            ROLE = 'standby'
            os.system('systemctl stop flash_application.service')  # Example command to stop service
        time.sleep(5)

def try_to_become_leader(redis_client):
    # Attempt to set a lock in Redis. If successful, this instance becomes the leader
    lock_acquired = redis_client.set('leader_lock', INSTANCE_ID, nx=True, ex=15)
    if lock_acquired:
        return True
    return False

if __name__ == "__main__":
    # Run both heartbeat and failover checks
    import threading
    heartbeat_thread = threading.Thread(target=send_heartbeat)
    heartbeat_thread.start()
    check_heartbeat()