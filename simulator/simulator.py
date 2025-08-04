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
        self.ambient_t = 25 #TODO Weather model

        # Load Map
        if config['city']['name'] == 'New York' and config['city']['granularity'] == 'district':
            with open('../data/nyc-district-map.pkl', 'rb') as pklfile:
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
                max_port_power = station['max_port_power'],
                max_station_power = station['max_station_power'],
                efficiency = station['efficiency']
            ))

        # Initialize Network
        self.port = port

        LOGGER.INFO('Simulator initialized...')

    def start(self):
        context = zmq.Context()
        socket = self.context.socket(zmq.REP)
        socket.bind("tcp://*:%s" % self.port)
        LOGGER.INFO('Simulator serving world state on tcp://*:%s' % self.port)
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
                        violation_list.append(f'{action["jobid"]} not in pending job list')
                    try:
                        ttp, dtp = self.get_td_to_dest(self.vehicle_list[veh_idx].location, self.arrived[action['jobid']].start_pos)
                        self.arrived[action['jobid']].assign_vehicle(self.vehicle_list[veh_idx], ttp, dtp)
                        self.inprogress[action['jobid']] = self.arrived[action['jobid']]
                        del self.arrived[action['jobid']]
                    except Exception as e:
                        violation_list.append(e.message)
                elif action['command'] == 'charge':
                    try:
                        self.charging_network[action['stationidx']].assign_vehicle(self.vehicle_list[veh_idx], action['rate'], action['stop condition'])
                    except Exception as e:
                        violation_list.append(e.message)
                elif action['command'] == 'reposition':
                    if self.vehicle_list[veh_idx].status != VehicleStatus.IDLE:
                        violation_list.append(f'Vehicle {veh_idx} is not idle')
                    else:
                        self.vehicle_list[veh_idx].status = VehicleStatus.TOLOC
                        self.vehicle_list[veh_idx].destination = action['destination']
                        ttp, dtp = self.get_td_to_dest(self.vehicle_list[veh_idx].location, action['destination'])
                        self.vehicle_list[veh_idx].distance_remaining = dtp
                        self.vehicle_list[veh_idx].time_remaining = ttp

            # Update charging vehicles
            for charger in self.charging_network:
                charger.tick(self.delta_t, self.ambient_t)

            # Update vehicles on jobs
            for key, job in self.inprogress.item():
                job.tick(self.delta_t, self.ambient_t)
                if job.status == JobStatus.COMPLETE:
                    self.completed[key] = job
                    del self.inprogress[key]
                elif job.status == JobStatus.REJECTED:
                    self.rejected[key] = job
                    del self.inprgress[key]

            # Update moving vehicles
            for vehicle in self.vehicle_list:
                if vehicle.status == VehicleStatus.TOLOC:
                    vehicle.tick(self.delta_t, self.ambient_t)

            # Get new arrivals Job status
            self.pending = self.pending | self.get_demand(self.t, self.t + self.delta_t)

            # Update time
            self.t = self.t + self.delta_t

            # Calculate response
            response = {}
            response['pending'] = self.pending
            response['completed'] = self.completed
            response['rejected'] = self.rejected
            response['charging_network'] = self.charging_network
            response['fleet'] = self.vehicle_list
            socket.send(response)
            LOGGER.debug('response sent.')
            self.t += 1
            if self.t > self.max_steps:
                self.status = SimulationStatus.STOPPED

    def get_td_to_dest(self, loc, dest):
        if self.map[loc][dest]['time'] is None:
            return dijkstra(loc, dest)            
        elif isintance(self.map[loc][dest]['time'], float):
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
            dist.append(flaot('inf'))
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
