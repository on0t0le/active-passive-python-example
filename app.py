import time
import redis
import os
import uuid
import threading
import pika

# Fetch configuration from environment variables
INSTANCE_ID = str(uuid.uuid4())
ROLE = 'standby'  # Initial role
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
RABBITMQ_PASSWORD = os.getenv('RABBITMQ_PASSWORD', 'guest')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
LOCK_EXPIRATION = 15  # Lock expiration time in seconds
HEARTBEAT_INTERVAL = 5  # Heartbeat interval in seconds

connection = None
channel = None

def send_heartbeat():
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)
    while True:
        if ROLE == 'active':
            r.set('heartbeat', 'active', ex=LOCK_EXPIRATION)
        time.sleep(HEARTBEAT_INTERVAL)

def check_heartbeat():
    global ROLE
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)
    while True:
        heartbeat = r.get('heartbeat')
        if heartbeat is None and ROLE == 'standby':
            print(f"Instance {INSTANCE_ID}: Active instance is down. Attempting to become active.")
            if try_to_become_leader(r):
                print(f"Instance {INSTANCE_ID}: Promoted to active.")
                ROLE = 'active'
                connect_to_rabbitmq()
        elif heartbeat is not None and ROLE == 'active':
            print(f"Instance {INSTANCE_ID}: Detected another active instance. Checking leadership.")
            if not renew_leader_lock(r):
                print(f"Instance {INSTANCE_ID}: Lost leadership. Switching to standby.")
                ROLE = 'standby'
                disconnect_from_rabbitmq()
        time.sleep(HEARTBEAT_INTERVAL)

def try_to_become_leader(redis_client):
    # Attempt to set a lock in Redis. If successful, this instance becomes the leader
    lock_acquired = redis_client.set('leader_lock', INSTANCE_ID, nx=True, ex=LOCK_EXPIRATION)
    return lock_acquired

def renew_leader_lock(redis_client):
    # Renew the lock if this instance is still the leader
    current_leader = redis_client.get('leader_lock')
    if current_leader == INSTANCE_ID.encode('utf-8'):
        redis_client.expire('leader_lock', LOCK_EXPIRATION)
        return True
    return False

def connect_to_rabbitmq():
    global connection, channel
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    print(f"Instance {INSTANCE_ID}: Connected to RabbitMQ")

def disconnect_from_rabbitmq():
    global connection, channel
    if connection:
        connection.close()
    print(f"Instance {INSTANCE_ID}: Disconnected from RabbitMQ")

if __name__ == "__main__":
    # Run both heartbeat and failover checks
    heartbeat_thread = threading.Thread(target=send_heartbeat)
    heartbeat_thread.start()
    check_heartbeat()