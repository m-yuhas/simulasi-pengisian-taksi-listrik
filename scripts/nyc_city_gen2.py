import csv
import datetime
import json
import pickle

import numpy

from scipy import stats



def dijkstra(loc, dest, MAP):
    dist = []
    prev = []
    Q = set()
    for v in MAP:
        dist.append(float('inf'))
        prev.append(None)
        Q.add(v)
    dist[loc - 1] = 0

    while len(Q) > 0:
        u = list(Q)[0]
        last_min = dist[u-1]
        for q in Q:
            if dist[q-1] < last_min:
                last_min = dist[q-1]
                u = q
        Q.remove(u)

        for v in Q:
            if MAP[u][v]['distance'] is not None:
                dv = MAP[u][v]['distance']
                alt = dist[u-1] + dv
                if alt < dist[v-1]:
                    dist[v-1] = alt
                    prev[v-1] = u

    S = []
    u = dest
    t = 0
    d = 0
    if prev[u-1] is not None or u == loc:
        while prev[u - 1] is not None:
            t += MAP[prev[u-1]][u]['time']
            d += MAP[prev[u-1]][u]['distance']
            S.append(u)
            u = prev[u-1]

    if dist[u-1] == float('inf'):
        return float('inf'), float('inf')

    return t, d


city = {}

with open('taxi_zone_lookup.csv') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        id = int(row['LocationID'])
        zone = row['Zone']
        city[id] = {'name': zone}

for zone_from in city:
    for zone_to in city:
        city[zone_from][zone_to] = {
            'time': [],
            'distance': []
        }

with open('../data/2020_Yellow_Taxi_Trip_Data_20250723.csv', 'r') as csvfile:
    reader = csv.DictReader(csvfile)
    i = 0
    for row in reader:
        pu = int(row['PULocationID'])
        do = int(row['DOLocationID'])
        distance = float(row['trip_distance'])
        pu_time = datetime.datetime.strptime(row['tpep_pickup_datetime'], '%m/%d/%Y %I:%M:%S %p')
        do_time = datetime.datetime.strptime(row['tpep_dropoff_datetime'], '%m/%d/%Y %I:%M:%S %p')
        if distance > 0 and do_time > pu_time:
            city[pu][do]['distance'].append(distance)
            city[pu][do]['time'].append((do_time - pu_time).total_seconds())
        i += 1

for zone_from in city:
    print(f'Processing Zone: {city[zone_from]["name"]}')
    for zone_to in city:
        if len(city[zone_from][zone_to]['time']) > 1:
            city[zone_from][zone_to]['time'] = numpy.mean(city[zone_from][zone_to]['time']).item()
            city[zone_from][zone_to]['distance'] = numpy.mean(city[zone_from][zone_to]['distance']).item()
        elif len(city[zone_from][zone_to]['time']) > 0:
            city[zone_from][zone_to]['time'] = city[zone_from][zone_to]['time'][0]
            city[zone_from][zone_to]['distance'] = city[zone_from][zone_to]['distance'][0]
        else:
            city[zone_from][zone_to]['time'] = None
            city[zone_from][zone_to]['distance'] = None

for zone_from in city:
    print(f'Calculating Unknown Routes: {city[zone_from]["name"]}')
    for zone_to in city:
        if city[zone_from][zone_to]['time'] is None:
            t, d = dijkstra(zone_from, zone_to, city)
            city[zone_from][zone_to]['time'] = float(t)
            city[zone_from][zone_to]['distance'] = float(d)
            

with open('nyc-map2.pkl', 'wb') as pklfile:
    pklfile.write(pickle.dumps(city))

#with open('nyc-map.json', 'w') as jsonfile:
#    jsonfile.write(json.dumps(city))
