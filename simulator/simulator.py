from enum import Enum


import argparse
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

    def __init__(config, port=6969, logfile=None):
        self.status = SimulationStatus.INITIALIZING

        # Load Map
        if config['city']['name'] == 'New York' and config['city']['granularity'] == 'district':
            with open('../data/nyc-district-map.pkl', 'rb') as pklfile:
                self.map = pickle.loads(pklfile.read())

        # Load Demand
        self.demand = ReplayDemand(f'../data/{config["demand"]}')

        # Initialize Fleet
        self.fleet = []
        for vehicle in range(config['fleet']['size']):
            self.fleet.append(Vehicle(
                model=config['fleet']['vehicle'],
                battery=config['fleet']['battery model'],
                location=random.choice(list(self.map.keys()))
            )


        # Initialize Charging Network
        self.charging_network = []
        for station in config['charging stations']:
            self.charging_network.append(ChargingStation(
            ))

        # Initialize Network
        self.port = port
        self.t = 0
        self.max_steps = config['max steps']

        LOGGER.INFO('Simulator initialized...')

    def start():
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
            # TODO: Calculate response
            socket.send(response)
            LOGGER.debug('response sent.')
            self.t += 1
            if self.t > self.max_steps:
                self.status = SimulationStatus.STOPPED

    def step():
        pass



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulate vehicle fleet')
    parser.add_argument('-c', '--config', help='Path to configuration file for a simulation')
    parser.add_argument('-v', '--verbosity', help='Logging level')
    parser.add_argument('-o', '--output', help='Path to state output log')
    parser.add_argument('-p', '--port', help='Port for scheduler to listen to', type=int)
    parser.add_argument('-n', '--max_steps', help='Maximum number of steps for the simulation', type=int)
    parser.add_argument('-d', '--delta_t', help='Time delta per step', type=int)
    parser.parse_args()
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
    while simulation.status != 'STOPPED':
