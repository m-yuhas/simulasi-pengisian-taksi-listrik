import csv
import datetime
import json
import pickle

import numpy

from scipy import stats

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
        try:
            time_kde = stats.gaussian_kde(numpy.array(city[zone_from][zone_to]['time']))
            dist_kde = stats.gaussian_kde(numpy.array(city[zone_from][zone_to]['distance']))
            city[zone_from][zone_to]['time'] = time_kde
            city[zone_from][zone_to]['distance'] = dist_kde
        except Exception:
            if len(city[zone_from][zone_to]['time']) > 0:
                city[zone_from][zone_to]['time'] = city[zone_from][zone_to]['time'][0]
                city[zone_from][zone_to]['distance'] = city[zone_from][zone_to]['distance'][0]
            else:
                city[zone_from][zone_to]['time'] = None
                city[zone_from][zone_to]['distance'] = None

with open('nyc-map.pkl', 'wb') as pklfile:
    pklfile.write(pickle.dumps(city))

#with open('nyc-map.json', 'w') as jsonfile:
#    jsonfile.write(json.dumps(city))
