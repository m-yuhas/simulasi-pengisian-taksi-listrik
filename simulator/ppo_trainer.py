import gymnasium as gym
import yaml

import ppo_trainer_sim

config = {}
with open('config.yaml', 'r') as yamlf:
    config = yaml.safe_load(yamlf.read())

env = ppo_trainer_sim.TaxiFleetSim(config)
env.reset()


from stable_baselines3 import PPO
import torch

model = PPO('MlpPolicy', env, verbose=1)
model.learn(total_timesteps=10000)

torch.save(model.policy, 'ppo_policy.pt')
