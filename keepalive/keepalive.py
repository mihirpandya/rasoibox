import requests
import os
import time

pid = os.getpid()
f = open("keepalive.pid", "w")
f.write(str(pid))
f.close()

while True:
    try:
        r = requests.get("https://rasoibox.onrender.com/healthz")
        time.sleep(1)
    except Exception as e:
        print(e)
