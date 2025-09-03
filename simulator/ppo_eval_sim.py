from enum import Enum


import argparse
import datetime
import json
import logging
import pickle
import random

import coloredlogs
import gymnasium as gym
import numpy
import yaml
import zmq

from scipy import stats

from job import *
from vehicle import *
from charger import *
from demand import *

import stable_baselines3
import torch


random.seed(0)
numpy.random.seed(0)


class SimulationStatus(Enum):
    INITIALIZING = 1
    CALCULATING = 2
    WAITING = 3
    STOPPED = 4


class TaxiFleetSim(gym.Env):

    def __init__(self, config, weights, logfile):
        self.status = SimulationStatus.INITIALIZING
        self.policy = torch.load(weights, weights_only=False)
        self.logfile = open(logfile, 'w')
        header = ",".join([ f"h{i}" for i in range(50) ]) + "," + ",".join([ f"s{i}" for i in range(50) ]) + "," + ",".join([ f"c{i}" for i in range(5)]) + ",served\n"
        self.logfile.write(header)
        self.config = config
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
                queue_size = 100,
                max_port_power = station['max port power'],
                max_station_power = station['max station power'],
                efficiency = station['efficiency']
            ))

        # Gym Stuff
        self.observation_space = gym.spaces.Box(0,1, shape=(len(self.fleet), 2))
        self.action_space = gym.spaces.Box(0,1, shape=(len(self.fleet), ))
        self.step_count = 0

    def _get_obs(self):
        obs = numpy.zeros((len(self.fleet), 2))
        for idx, v in enumerate(self.fleet):
            obs[idx, 0] = v.battery.actual_capacity / v.battery.initial_capacity
            obs[idx, 1] = v.battery.soc
        return obs

    def reset(self, seed = None, options = None):
        """Start a new episode.

        Args:
            seed: Random seed for reproducible episodes
            options: Additional configuration (unused)

        Returns:
            tuple: (obeservation, info) for initial state
        """
        super().reset(seed=seed)
        self.step_count = 0
        self.status = SimulationStatus.INITIALIZING

        # Initialize Time
        self.max_steps = self.config['max steps']
        self.delta_t = datetime.timedelta(seconds=self.config['delta t'])
        self.t = datetime.datetime.strptime(self.config['start t'], '%m/%d/%Y %I:%M:%S %p')
        self.end_t = datetime.datetime.strptime(self.config['end t'], '%m/%d/%Y %I:%M:%S %p')
        self.ambient_t = 25 #TODO Weather model

        # Load Map
        if self.config['city']['name'] == 'New York' and self.config['city']['granularity'] == 'district':
            with open('../data/nyc-district-map2.pkl', 'rb') as pklfile:
                self.map = pickle.loads(pklfile.read())

        # Load Demand
        self.demand = ReplayDemand(f'../data/{self.config["demand"]}')
        self.arrived = self.demand.get_demand(self.t, self.t + self.delta_t)
        self.inprogress = {}
        self.rejected = {}
        self.completed = {}

        # Initialize Fleet
        self.fleet = []
        for vehicle in range(self.config['fleet']['size']):
            self.fleet.append(Vehicle(
                model=self.config['fleet']['vehicle'],
                battery=self.config['fleet']['battery model'],
                location=random.choice(list(self.map.keys()))
            ))

        # Initialize Charging Network
        self.charging_network = []
        for station in self.config['charging stations']:
            self.charging_network.append(DCFastCharger(
                location = station['location'],
                ports = station['ports'],
                queue_size = station['queue size'],
                max_port_power = station['max port power'],
                max_station_power = station['max station power'],
                efficiency = station['efficiency']
            ))

 

        return self._get_obs(), {}


    def get_closest_charger(self, veh_loc, charging_network):
        distances = []
        for charger in charging_network:
            t, d = self.get_td_to_dest(veh_loc, charger.location)
            distances.append(d)
        return distances.index(min(distances))

    def get_distance(self, veh_loc, job_loc):
        t, d = self.get_td_to_dest(veh_loc, job_loc)
        return d


    def step(self, action):
        """Execute one timestep within the environment.

        Args:
            action: The action to take
        
        Returns:
            tuple: (observation, reward, terminated, truncated, info)
        """
        self.step_count += 1

        actions = []
        assigned_jids = []
        for idx, v in numpy.ndenumerate(action):
            if v > 0.5:
                actions.append({
                    'command': 'charge',
                    'stationidx': self.get_closest_charger(self.fleet[idx[0]].location, self.charging_network),
                    'rate': v * 20 ,
                    'stop condition': 0.8
                })
            elif len(self.arrived) > 0:
                distances = []
                jids = []
                for job in self.arrived:
                    distances.append(self.get_distance(self.fleet[idx[0]].location, self.arrived[job].start_loc))
                    jids.append(job)
                jidx = jids[distances.index(min(distances))]
                if self.fleet[idx[0]].battery.soc * self.fleet[idx[0]].battery.actual_capacity * 100 / 17.1 > min(distances) + self.get_distance(self.arrived[job].end_loc, self.charging_network[self.get_closest_charger(self.arrived[job].end_loc, self.charging_network)].location) and jidx not in assigned_jids:
                    actions.append({
                        'command': 'service',
                        'jobid': self.arrived[jidx].idx
                    })
                    assigned_jids.append(jidx)
                else:
                    actions.append({'command' : None})
            else:
                actions.append({'command' : None})

        # Move Fleet
        for veh_idx, action in enumerate(actions):
            if action['command'] == 'service':
                if action['jobid'] not in self.arrived:
                    raise Exception(f'{action["jobid"]} not in pending job list')
                if self.fleet[veh_idx].status != VehicleStatus.IDLE:
                    continue
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
                    self.charging_network[action['stationidx']].vehicles_en_route.append({'vehicle': self.fleet[veh_idx], 'rate': action['rate'], 'condition': action['stop condition']})
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

        self.actions = actions

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
        
        for key in del_keys:
            del self.inprogress[key]

        # Update moving vehicles
        for vehicle in self.fleet:
            if vehicle.status == VehicleStatus.TOLOC:
                vehicle.tick(self.delta_t, self.ambient_t)

        # Get new arrivals Job status
        self.arrived = self.arrived | self.demand.get_demand(self.t, self.t + self.delta_t)
        del_keys = []
        for job in self.arrived:
            self.arrived[job].tick(self.delta_t, self.ambient_t)
            if self.arrived[job].status == JobStatus.COMPLETE:
                self.completed[job] = self.arrived[job]
                del_keys.append(job)
            if self.arrived[job].status == JobStatus.REJECTED:
                self.rejected[job] = self.arrived[job]
                del_keys.append(job)
        for key in del_keys:
            del self.arrived[key]

        # Update time
        self.t = self.t + self.delta_t

        # Calculate response
        #response = {}
        #response['arrived'] = [self.arrived[j].to_dict() for j in self.arrived]
        #response['completed'] = len(self.completed)
        #response['rejected'] = len(self.rejected)
        #response['inprogress'] = [self.inprogress[j].to_dict() for j in self.inprogress]
        #response['charging_network'] = [s.to_dict() for s in self.charging_network]
        #response['fleet'] = [v.to_dict() for v in self.fleet]
        #response['violations'] = violation_list
        
        LAMBDA = 1.0
        reward = sum([v.battery.soc for v in self.fleet]) + LAMBDA * sum([v.battery.actual_capacity / v.battery.initial_capacity for v in self.fleet])

        return (
            self._get_obs(),
            reward,
            True if self.t >= self.end_t else False,
            True if self.step_count > 168 else False,
            {}
        )

    def start(self):
        action = numpy.zeros(50)
        obs, _, _, res, _ = self.step(action)
        h = 0
        while True:
            self.policy.eval()
            x = torch.from_numpy(obs).unsqueeze(0).cuda()
            obs, _, _, res, _ = self.step(self.policy(x)[0].cpu().detach().numpy())
            if res:
                print("Resetting step count")
                last_state = self.fleet
                self.reset()
                self.fleet = last_state
            print(f"Hour {h}")
            h += 1

            # LOG
            data = ",".join([ str(v.battery.actual_capacity) for v in self.fleet]) + "," + ",".join([ str(v.battery.soc) for v in self.fleet]) + "," + ",".join(["1" if i['command'] == 'charge' else "0" for i in self.actions]) + f",{len(self.completed)}\n"
            self.logfile.write(data)

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
    parser.add_argument('-o', '--output', help='Path to state output log')
    parser.add_argument('-p', '--port', help='Port for scheduler to listen to', type=int)
    parser.add_argument('-n', '--max_steps', help='Maximum number of steps for the simulation', type=int)
    parser.add_argument('-d', '--delta_t', help='Time delta per step', type=int)
    parser.add_argument('-i', '--input', help='Path to input')
    parser.add_argument('-w', '--weights', help='Path to policy weights')
    args = parser.parse_args()

    config = {}
    with open(args.config, 'r') as fp:
        config = yaml.safe_load(fp.read())
    if args.max_steps is not None:
        config['max steps'] = args.max_steps
    if args.delta_t is not None:
        config['delta t'] = args.delta_t

    simulation = TaxiFleetSim(config, weights=args.weights, logfile=args.output)
    simulation.start()
