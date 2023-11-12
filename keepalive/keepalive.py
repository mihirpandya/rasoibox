#!/usr/bin/python3
from datetime import datetime

import requests
import os
import time
import logging

logging.basicConfig(filename='keepalive.log', encoding='utf-8', level=logging.INFO)
logger = logging.getLogger("keepalive")

pid = os.getpid()
f = open("keepalive.pid", "w")
f.write(str(pid))
f.close()

logger.info("PID: {}".format(pid))
while True:
    r = requests.get("https://rasoibox.onrender.com/healthz")
    logger.info("{}: {}".format(datetime.now().strftime("%-I:%M %p, %b %-d"), r.status_code))
    time.sleep(300)
