from enum import Enum


import argparse
import datetime
import json
import logging
import pickle
import random

import coloredlogs
import numpy
import yaml
import zmq

from scipy import stats

from job import *
from vehicle import *
from charger import *
from demand import *


LOGGER = logging.getLogger('Charge Simulator')


random.seed(0)
numpy.random.seed(0)


class SimulationStatus(Enum):
    INITIALIZING = 1
    CALCULATING = 2
    WAITING = 3
    STOPPED = 4


class Simulation:

    def __init__(self, config, port=6969, logfile=None):
        self.status = SimulationStatus.INITIALIZING

        # Initialize Time
        self.max_steps = config['max steps']
        self.delta_t = datetime.timedelta(seconds=config['delta t'])
        self.t = datetime.datetime.strptime(config['start t'], '%m/%d/%Y %I:%M:%S %p')
        self.end_t = datetime.datetime.strptime(config['end t'], '%m/%d/%Y %I:%M:%S %p')
        self.ambient_t = 25 #TODO Weather model

        # Load Map
        if config['city']['name'] == 'New York' and config['city']['granularity'] == 'district':
            with open('../data/nyc-district-map2.pkl', 'rb') as pklfile:
                self.map = pickle.loads(pklfile.read())

        # Load Demand
        self.demand = ReplayDemand(f'../data/{config["demand"]}')
        self.arrived = self.demand.get_demand(self.t, self.t + self.delta_t)
        self.inprogress = {}
        self.rejected = {}
        self.completed = {}

        # Initialize Fleet
        self.fleet = []
        for vehicle in range(config['fleet']['size']):
            self.fleet.append(Vehicle(
                model=config['fleet']['vehicle'],
                battery=config['fleet']['battery model'],
                location=random.choice(list(self.map.keys()))
            ))

        # Initialize Charging Network
        self.charging_network = []
        for station in config['charging stations']:
            self.charging_network.append(DCFastCharger(
                location = station['location'],
                ports = station['ports'],
                queue_size = station['queue size'],
                max_port_power = station['max port power'],
                max_station_power = station['max station power'],
                efficiency = station['efficiency']
            ))

        # Initialize Network
        self.port = port

        LOGGER.info('Simulator initialized...')

    def start(self):
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind("tcp://*:%s" % self.port)
        LOGGER.info('Simulator serving world state on tcp://*:%s' % self.port)
        while self.status != SimulationStatus.STOPPED:
            self.status = SimulationStatus.WAITING
            LOGGER.debug('waiting...')
            request = json.loads(socket.recv())
            LOGGER.debug('received request.')
            self.status = SimulationStatus.CALCULATING

            violation_list = []

            # Move Fleet
            for veh_idx, action in enumerate(request['actions']):
                if action['command'] == 'service':
                    if action['jobid'] not in self.arrived:
                        raise Exception(f'{action["jobid"]} not in pending job list')
                    ttp, dtp = self.get_td_to_dest(self.fleet[veh_idx].location, self.arrived[action['jobid']].start_loc)
                    self.arrived[action['jobid']].assign_vehicle(self.fleet[veh_idx], ttp, dtp)
                    self.inprogress[action['jobid']] = self.arrived[action['jobid']]
                    del self.arrived[action['jobid']]
                elif action['command'] == 'charge':
                    if self.fleet[veh_idx].location != self.charging_network[action['stationidx']].location:
                        self.fleet[veh_idx].status = VehicleStatus.TOLOC
                        self.fleet[veh_idx].destination = self.charging_network[action['stationidx']].location
                        ttp, dtp = self.get_td_to_dest(self.fleet[veh_idx].location, self.charging_network[action['stationidx']].location)
                        self.fleet[veh_idx].distance_remaining = dtp
                        self.fleet[veh_idx].time_remaining = ttp
                        self.charging_network[action['stationidx']].vehicles_en_route.append({'vehicle': vehicle, 'rate': action['rate'], 'condition': action['stop condition']})
                    else:
                        self.charging_network[action['stationidx']].assign_vehicle(self.fleet[veh_idx], action['rate'], action['stop condition'])
                elif action['command'] == 'reposition':
                    if self.fleet[veh_idx].status != VehicleStatus.IDLE:
                        raise Exception(f'Vehicle {veh_idx} is not idle')
                    else:
                        self.fleet[veh_idx].status = VehicleStatus.TOLOC
                        self.fleet[veh_idx].destination = action['destination']
                        ttp, dtp = self.get_td_to_dest(self.fleet[veh_idx].location, action['destination'])
                        self.fleet[veh_idx].distance_remaining = dtp
                        self.fleet[veh_idx].time_remaining = ttp

            #LOGGER.critical(self.fleet[7].to_dict())

            # Update charging vehicles
            for charger in self.charging_network:
                charger.tick(self.delta_t, self.ambient_t)

            # Update vehicles on jobs
            del_keys = []
            for key, job in self.inprogress.items():
                job.tick(self.delta_t, self.ambient_t)
                if job.status == JobStatus.COMPLETE:
                    self.completed[key] = job
                    del_keys.append(key)
                elif job.status == JobStatus.REJECTED:
                    self.rejected[key] = job
                    del_keys.append(key)
            for key in del_keys:
                del self.inprogress[key]

            # Update moving vehicles
            for vehicle in self.fleet:
                if vehicle.status == VehicleStatus.TOLOC:
                    vehicle.tick(self.delta_t, self.ambient_t)

            # Get new arrivals Job status
            self.arrived = self.arrived | self.demand.get_demand(self.t, self.t + self.delta_t)
            LOGGER.error(len(self.arrived))
            LOGGER.warning(self.t)
            # Update time
            self.t = self.t + self.delta_t

            # Calculate response
            response = {}
            response['arrived'] = [self.arrived[j].to_dict() for j in self.arrived]
            response['completed'] = [self.completed[j].to_dict() for j in self.completed]
            response['rejected'] = [self.rejected[j].to_dict() for j in self.rejected]
            response['inprogress'] = [self.inprogress[j].to_dict() for j in self.inprogress]
            response['charging_network'] = [s.to_dict() for s in self.charging_network]
            response['fleet'] = [v.to_dict() for v in self.fleet]
            response['violations'] = violation_list
            #print(response)
            socket.send_string(json.dumps(response))
            LOGGER.debug('response sent.')
            
            if self.t >= self.end_t:
                self.status = SimulationStatus.STOPPED
                LOGGER.warning('Simulation reached its end...')
                break

    def get_td_to_dest(self, loc, dest):
        if self.map[loc][dest]['time'] is None:
            return dijkstra(loc, dest)            
        elif isinstance(self.map[loc][dest]['time'], float):
            return self.map[loc][dest]['time'], self.map[loc][dest]['distance']
        else:
            t = self.map[loc][dest]['time'].resample(1)
            d = self.map[loc][dest]['distance'].resample(1)
            if t < 0 or d < 0:
                return 0.0, 0.0
            else:
                return t, d


    def dijkstra(self, loc, dest):
        dist = []
        prev = []
        Q = set()
        for v in self.map:
            dist.append(float('inf'))
            prev.append(None)
            Q.add(v)
        dist[loc] = 0

        while len(Q) > 0:
            u = dist.index(min(dist))
            Q.remove(u)

            for v in Q:
                if self.map[u][v]['distance'] is not None:
                    dv = self.map[u][v]['distance'] if isinstance(self.map[u][v]['distance'], float) else max(self.map[u][v]['distance'].resample(1), 0)
                    alt = dist[u] + dv
                    if alt < dist[v]:
                        dist[v] = alt
                        prev[v] = u

        S = []
        u = dest
        t = 0
        if prev[u] is not None or u == loc:
            while u is not None:
                t += self.map[prev[u]][u]['time'] if isinstance(self.map[prev[u]][u]['time'], float) else max(self.map[prev[u]][u]['time'].resample(1), 0)
                S.append(u)
                u = prev[u]

        return t, dist[u]



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulate vehicle fleet')
    parser.add_argument('-c', '--config', help='Path to configuration file for a simulation')
    parser.add_argument('-v', '--verbosity', help='Logging level')
    parser.add_argument('-o', '--output', help='Path to state output log')
    parser.add_argument('-p', '--port', help='Port for scheduler to listen to', type=int)
    parser.add_argument('-n', '--max_steps', help='Maximum number of steps for the simulation', type=int)
    parser.add_argument('-d', '--delta_t', help='Time delta per step', type=int)
    args = parser.parse_args()
    coloredlogs.install(level=args.verbosity.upper())

    config = {}
    with open(args.config, 'r') as fp:
        config = yaml.safe_load(fp.read())
    if args.max_steps is not None:
        config['max steps'] = args.max_steps
    if args.delta_t is not None:
        config['delta t'] = args.delta_t

    simulation = Simulation(config, port=args.port, logfile=args.output)
    simulation.start()
