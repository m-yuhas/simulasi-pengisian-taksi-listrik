import json
import os
import time

import requests

YEAR=2020

ENDPOINTS = {
    2020: "https://data.cityofnewyork.us/resource/kxp8-n2sj.json"
}

if not os.path.exists('cache'):
    os.mkdir('cache')

offset = 0
while True:
    r = requests.get(f'{ENDPOINTS[YEAR]}?$offset={offset}')
    if len(r.json()) == 0:
        break
    print(f"Downloaded records ${offset} - ${offset + 1000}")
    with open(os.path.join('cache', f'nyc-{year}-{offset}.json'), 'w') as fp:
        fp.write(json.dumps(r.json()))
    offset += 1000
    time.sleep(5)

print("Done")


