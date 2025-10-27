"""Taxi fleet simulator."""
from typing import Dict, Tuple
from enum import Enum


import argparse
import datetime
import json
import logging
import pickle
import random


import gymnasium as gym
import numpy
import yaml


from scipy import stats


from job import *
from charger import *
from demand import *
from region import *
from vehicle import *


random.seed(0)
numpy.random.seed(0)


class TaxiFleetSimulator(gym.Env):
    """Taxi fleet simulator.

    Args:
        seed: seed value for random number generator
        config: configuration dictionary, (see config.yaml for details.)
    """

    def __init__(self, config: Dict) -> None:
        super().__init__()
        self.config = config

    def _get_obs(self) -> numpy.array:
        """Get an observation from the environment."""
        obs = numpy.zeros((len(self.fleet), 2))
        for idx, v in enumerate(self.fleet):
            obs[idx, 0] = v.battery.actual_capacity / v.battery.initial_capacity
            obs[idx, 1] = v.battery.soc
        return obs

    def reset(self, seed: int = None) -> Tuple[numpy.array, Dict]:
        """Start a new episode.

        Args:
            seed: Random seed for reproducible episodes

        Returns:
            tuple: (obeservation, info) for initial state
        """
        super().reset(seed=seed)

        # Initialize Time
        self.dt = float(self.config['delta t'])
        self.t = datetime.datetime.strptime(self.config['start t'], '%Y/%m/%d %H:%M:%S')
        self.t_max = datetime.datetime.strptime(self.config['end t'], '%Y/%m/%d %H:%M:%S')
        self.T_a = 25 #TODO Weather model

        # Load Map
        self.region = CyclicZoneGraph(self.config['city']) 

        # Load Demand
        self.demand = ReplayDemand(self.config['demand'], self.region)
        self.demand.seek(self.t)
        self.arrived = self.demand.tick(self.dt)
        self.assigned = set({})
        self.inprogress = set({})
        self.rejected = 0
        self.completed = 0
        self.failed = 0

        # Initialize Fleet
        self.fleet = []
        for vehicle in range(self.config['fleet']['size']):
            self.fleet.append(Vehicle(
                model=self.config['fleet']['vehicle'],
                battery=self.config['fleet']['battery model'],
                location=CyclicZoneGraphLocation(random.choice(list(self.region.map.keys())), self.region),
                vid=vehicle
            ))

        # Initialize Charging Network
        self.charging_network = []
        for station in self.config['charging stations']:
            self.charging_network.append(ChargeStation(
                location = CyclicZoneGraphLocation(station['location'], self.region),
                ports = [ChargePort(station['max port power'], station['efficiency']) for port in range(station['ports'])],
                P_max = station['max total power'],
            ))

        # Initialize State and Action Spaces
        self.observation_space = gym.spaces.Box(0,1, shape=(len(self.fleet), 2))
        self.action_space = gym.spaces.Box(0,1, shape=(len(self.fleet), 2))
        self.step_count = 0

        # Global state information
        info = {}
        info['arrived'] = [j.to_dict() for j in self.arrived]
        info['assigned'] = [j.to_dict() for j in self.assigned]
        info['completed'] = self.completed
        info['rejected'] = self.rejected
        info['inprogress'] = [j.to_dict() for j in self.inprogress]
        info['failed'] = self.failed
        info['charging_network'] = [s.to_dict() for s in self.charging_network]
        info['fleet'] = [v.to_dict() for v in self.fleet]

        return self._get_obs(), info

    def get_closest_charger(self, vehicle: Vehicle) -> ChargeStation:
        """
        Get the closest charger to a <vehicle>.
        """
        distances = []
        for charger in self.charging_network:
            d, t = vehicle.location.to(charger.location)
            distances.append(d)
        return self.charging_network[distances.index(min(distances))]

    def get_closest_job(self, vehicle: Vehicle) -> Job:
        """
        Get the closest job to <vehicle> that is not inprogress or expired.
        """
        closest_job = None
        distance = float('inf')
        for job in self.arrived:
            d, t = vehicle.location.to(job.pickup_location)
            #if d == float('inf'):
            #    print(job.pickup_location.region.map[1])
            if d < distance:
                distance = d
                closest_job = job
        return closest_job

    def step(self, action: numpy.array) -> Tuple[numpy.array, float, bool, bool, Dict]:
        """Execute one timestep within the environment.

        Args:
            action: The action to take
        
        Returns:
            tuple: (observation, reward, terminated, truncated, info)
        """

        # First update vehicle statuses
        for idx in range(len(self.fleet)):
            if action[idx,0] > 0.5 and self.fleet[idx].status in [VehicleStatus.IDLE, VehicleStatus.CHARGING, VehicleStatus.TOCHARGE]:
                self.fleet[idx].charge(self.get_closest_charger(self.fleet[idx]), action[idx,1])
            elif len(self.arrived) > 0 and self.fleet[idx].status in [VehicleStatus.IDLE, VehicleStatus.CHARGING, VehicleStatus.TOCHARGE]:
                self.fleet[idx].service_demand(self.get_closest_job(self.fleet[idx]))

        # Update fleet
        for vehicle in self.fleet:
            vehicle.tick(self.dt, {'T_a': self.T_a}) # TODO: Check conditions

        # Update charging vehicles
        for charger in self.charging_network:
            charger.tick(self.fleet, self.dt, self.T_a)

        # Get new arrivals
        self.arrived = self.arrived | self.demand.tick(self.dt)

I       # Update jobs in progress
        to_completed = set({})
        to_failed = set({})
        for job in self.inprogress:
            if job.status == JobStatus.COMPLETE:
                to_completed = to_completed.union({job})
            elif job.status == JobStatus.FAILED:
                to_failed = to_failed.union({job})
        self.inprogress = self.inprogress - to_completed - to_failed
        self.completed += len(to_completed)
        self.failed += len(to_failed)

        # Update assigned jobs
        to_inprogress = set({})
        to_failed = set({})
        for job in self.assigned:
            if job.status == JobStatus.INPROGRESS:
                to_inprogress = to_inprogress.union({job})
            elif job.status == JobStatus.FAILED:
                to_failed = to_failed.union({job})
        self.assigned = self.assigned - to_inprogress - to_failed
        self.failed += len(to_failed)
        self.inprogress = self.inprogress.union(to_inprogress)

        # Update arrived jobs
        to_assigned = set({})
        to_rejected = set({})
        for job in self.arrived:
            job.tick(self.dt)
            if job.status == JobStatus.ASSIGNED:
                to_assigned = to_assigned.union({job})
            elif job.status == JobStatus.REJECTED:
                to_rejected = to_rejected.union({job})
            elif job.status == JobStatus.INPROGRESS:
                to_inprogress = to_inprogress.union({job})
        self.arrived = self.arrived - to_assigned - to_rejected - to_inprogress
        self.assigned = self.assigned.union(to_assigned)
        self.inprogress = self.inprogress.union(to_inprogress)
        self.rejected += len(to_rejected)

        # Update time
        self.t = self.t + datetime.timedelta(seconds=self.dt)
        self.step_count += 1
        
        print(self.t)

        # Calculate info
        info = {}
        info['arrived'] = [j.to_dict() for j in self.arrived]
        info['assigned'] = [j.to_dict() for j in self.assigned]
        info['completed'] = self.completed
        info['rejected'] = self.rejected
        info['inprogress'] = [j.to_dict() for j in self.inprogress]
        info['failed'] = self.failed
        info['charging_network'] = [s.to_dict() for s in self.charging_network]
        info['fleet'] = [v.to_dict() for v in self.fleet]
        
        # Calculate reward
        # TODO: specify as lambda
        ALPHA = 1.0
        BETA = 1.0
        #reward = sum([v.battery.soc for v in self.fleet]) + LAMBDA * sum([v.battery.actual_capacity / v.battery.initial_capacity for v in self.fleet])
        reward = self.completed + ALPHA * sum([v.battery.actual_capacity / v.battery.initial_capacity for v in self.fleet]) # - BETA * sum([1 if v.status == VehicleStatus.RECOVERY else - for v in self.fleet])

        return (
            self._get_obs(),
            reward,
            True if self.t >= self.t_max else False,
            True if self.step_count > 1000 else False,
            info
        )


