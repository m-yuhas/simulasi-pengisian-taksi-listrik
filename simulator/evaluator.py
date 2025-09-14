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

from scipy import stats

from job import *
from vehicle import *
from charger import *
from demand import *

import stable_baselines3
import torch


class SchedulePolicy:
    """Abstract Policy Class."""

    def __init__(self):
        pass

    def schedule(observation, info):
        raise NotImplemented


class EightyTwentyPolicy(SchedulePolicy):

    def __init__(self):
        super().__init__()

    def schedule(observation, info):
        pass


class DnnPolicy(SchedulePolicy):

    def __init__(self, weights):
        super().__init__()
        self.dnn = torch.load(weights, weights_only=False).eval()


    def schedule(observation, info):
        with torch.no_grad():
            x = torch.from_numpy(observation).unsqueeze(0).cuda()
            return self.policy(x)[0].cpu().detach().numpy()


class DataLogger:
    """Get data for plots."""

    def __init__(self, logfile):
        self.csvfile = open(logfile, 'w')
        header = ''
        self.csvfile.write(header + '\n')

    def write(info):
        row = ''
        self.csvfile.write(row + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simulate vehicle fleet')
    parser.add_argument('-c', '--config', help='Path to configuration file for a simulation')
    parser.add_argument('-o', '--output', help='Path to state output log')
    parser.add_argument('-p', '--policy', help='EIGHTYTWENTY or DNN', type=int)
    parser.add_argument('-w', '--weights', help='Path to policy weights for DNN')
    args = parser.parse_args()

    config = {}
    with open(args.config, 'r') as fp:
        config = yaml.safe_load(fp.read())

    datalogger = DataLogger(args.output)

    policy = None
    if args.policy.lower() == 'eightytwenty':
        policy = EightyTwentyPolicy()
    elif args.policy.lower() == 'dnn':
        policy = DnnPolicy(args.weights)
    else:
        raise Exception('Choose a supported policy!')

    environment = TaxiFleetSimulator(config)
    observation, info = environment.reset()
    done = False

    while not done:
        datalogger.write(info)
        action = policy.schedule(observation, info)
        observation, done, _, info = environment.step(action)        

