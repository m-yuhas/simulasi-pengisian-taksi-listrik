import yaml


import gymnasium as gym
from stable_baselines3 import PPO
import torch


from simulator import *


config = {}
with open('../config.yaml', 'r') as yamlfile:
    config = yaml.safe_load(yamlfile.read())


env = TaxiFleetSimulator(config)
env.reset()

model = PPO('MlpPolicy', env, verbose=1)
model.learn(total_timesteps=10000)

torch.save(model.policy, 'ppo_policy.pt')
