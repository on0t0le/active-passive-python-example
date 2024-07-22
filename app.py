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
RABBITMQ_PORT = os.getenv('RABBITMQ_HOST', '5672')
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))

connection = None
channel = None

def send_heartbeat():
    r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)
    while True:
        if ROLE == 'active':
            r.set('heartbeat', 'active', ex=10)
        time.sleep(5)

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
            print(f"Instance {INSTANCE_ID}: Detected another active instance. Switching to standby.")
            ROLE = 'standby'
            disconnect_from_rabbitmq()
        time.sleep(5)

def try_to_become_leader(redis_client):
    # Attempt to set a lock in Redis. If successful, this instance becomes the leader
    lock_acquired = redis_client.set('leader_lock', INSTANCE_ID, nx=True, ex=15)
    if lock_acquired:
        return True
    return False

def connect_to_rabbitmq():
    global connection, channel
    credentials = pika.PlainCredentials('guest', 'guest')
    parameters = pika.ConnectionParameters(RABBITMQ_HOST,
                                        RABBITMQ_PORT,
                                        '/',
                                        credentials)
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