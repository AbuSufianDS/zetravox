import multiprocessing

workers = 1
threads = 2
worker_class = 'sync'
max_requests = 100
max_requests_jitter = 20
timeout = 120
keepalive = 5
preload_app = True