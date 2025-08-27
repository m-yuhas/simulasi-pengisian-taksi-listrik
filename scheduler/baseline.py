import json
import logging
import pickle
import time

import numpy
import zmq
import coloredlogs

from scipy import stats

LOGGER = logging.getLogger('Charge Simulator')
coloredlogs.install(level='DEBUG')

MAP = None
with open('../data/nyc-district-map2.pkl', 'rb') as pklfile:
    MAP = pickle.loads(pklfile.read())

def get_td_to_dest(loc, dest):
    if MAP[loc][dest]['time'] is None:
        return dijkstra(loc, dest)
    elif isinstance(MAP[loc][dest]['time'], float):
        return MAP[loc][dest]['time'], MAP[loc][dest]['distance']
    else:
        t = MAP[loc][dest]['time'].resample(1)
        d = MAP[loc][dest]['distance'].resample(1)
        if t < 0 or d < 0:
            return 0.0, 0.0
        else:
            return t, d

def dijkstra(loc, dest):
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
                dv = MAP[u][v]['distance'] if isinstance(MAP[u][v]['distance'], float) else max(MAP[u][v]['distance'].resample(1), 0)
                alt = dist[u-1] + dv
                if alt < dist[v-1]:
                    dist[v-1] = alt
                    prev[v-1] = u

    S = []
    u = dest
    t = 0
    if prev[u-1] is not None or u == loc:
        while prev[u - 1] is not None:
            t += MAP[prev[u-1]][u]['time'] if isinstance(MAP[prev[u-1]][u]['time'], float) else max(MAP[prev[u-1]][u]['time'].resample(1), 0)
            S.append(u)
            u = prev[u-1]

    return t, dist[u-1]


def get_closest_charger(veh_loc, charging_network):
    distances = []
    for charger in charging_network:
        t, d = get_td_to_dest(veh_loc, charger['location'])
        distances.append(d)
    return distances.index(min(distances))

def get_distance(veh_loc, job_loc):
    t, d = get_td_to_dest(veh_loc, job_loc)
    return d

#random.seed(0)
#numpy.random.seed(0)

EPSILON = 0.1

port = 6969

context = zmq.Context()
LOGGER.debug('Connecting to simulator...')
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:%s" % port)

request = {'actions': []}

logf = open('baseline_logs.csv', 'w')
header = ",".join([ f"h{i}" for i in range(50) ]) + "," + ",".join([ f"s{i}" for i in range(50) ]) + "," + ",".join([ f"c{i}" for i in range(5)]) + ",served\n"
logf.write(header)

while True:
    LOGGER.debug('Sending Request')

    socket.send_string(json.dumps(request))
    response = socket.recv()
    response = json.loads(response)
    #LOGGER.warning(response['violations'])
    #LOGGER.warning([v['battery']['soc'] for v in response['fleet']])
    #LOGGER.info([v['battery']['actual_capacity'] for v in response['fleet']])
    request = {'actions': []}
    total_power = 0
    for vehicle in response['fleet']:


        # 1. If a vehicle's SoC < 0.2, send to nearest charger and at maximum rate
        if vehicle['battery']['soc'] < 0.2 and vehicle['status'] == 'IDLE':
            destination = get_closest_charger(vehicle['location'], response['charging_network'])
            charge_power = max(1 - vehicle['battery']['soc'] - EPSILON, 0) * vehicle['battery']['actual_capacity']
            request['actions'].append({
                'command': 'charge',
                'stationidx': destination,
                'rate': charge_power,
                'stop condition': 0.8
            })
            total_power += charge_power
        elif vehicle['status'] == 'CHARGING' and (1 - vehicle['battery']['soc']) * vehicle['battery']['actual_capacity'] < 60:
            charge_power = max(1 - vehicle['battery']['soc'] - EPSILON, 0) * vehicle['battery']['actual_capacity']
            request['actions'].append({
                'command': 'charge',
                'stationidx': destination,
                'rate': charge_power,
                'stop condition': 0.8
            })
            total_power += charge_power
            # 2. Assign closest vehicle that can complete a job
        elif vehicle['status'] == 'IDLE' and len(response['arrived']) > 0:
            distances = []
            for job in response['arrived']:
                distances.append(get_distance(vehicle['location'], job['start_loc']))
            jidx = distances.index(min(distances))
            if vehicle['battery']['soc'] * vehicle['battery']['actual_capacity'] * 100 / 17.1 > min(distances) + get_distance(job['end_loc'], response['charging_network'][get_closest_charger(job['end_loc'], response['charging_network'])]['location']):
                #LOGGER.info(vehicle['battery']['soc'] * vehicle['battery']['actual_capacity'] * 100 / 17.1)
                #LOGGER.warning(min(distances) + get_distance(job['end_loc'], response['charging_network'][get_closest_charger(job['end_loc'], response['charging_network'])]['location']))
                #LOGGER.error(vehicle['battery']['soc'])
                request['actions'].append({
                    'command': 'service',
                    'jobid': response['arrived'][jidx]['idx']
                })
                del response['arrived'][jidx]
            else:
                request['actions'].append({'command': None})

            # Else do nothing
        else:
            request['actions'].append({'command': None})

    if total_power >= 500:
        n_charging = 0
        for action in request['actions']:
            if action['command'] == 'charge':
                n_charging += 1

        new_charge = 500 / n_charging
        for idx, action in enumerate(request['actions']):
            if action['command'] == 'charge' and new_charge <= action['rate']:
                request['actions'][idx]['rate'] = new_charge


    #LOGGER.critical(response['inprogress'])
    #LOGGER.warning([v['battery']['soc'] for v in response['fleet']])
    #LOGGER.info([v['battery']['actual_capacity'] for v in response['fleet']])

    data = ",".join([ str(v['battery']['actual_capacity']) for v in response['fleet']]) + "," + ",".join([ str(v['battery']['soc']) for v in response['fleet']]) + "," + ",".join(["1" if i['command'] == 'charge' else "0" for i in request['actions']]) + f",{response['completed']}\n"
    logf.write(data)
