from enum import Enum

from battery import *

class VehicleStatus(Enum):
    IDLE = 1
    TOPICKUP = 2
    TOCHARGE = 3
    CHARGING = 4
    TOLOC = 5
    ONJOB = 6
    OFFDUTY = 7

class Vehicle:

    def __init__(self, model, battery, location):
        self.model = model
        if self.model.lower() == 'byd e6':
            self.capacity = 71.7
            self.efficiency = 17.1 # kWh/100km

        if self.battery.lower() == 'brevo':
            self.battery_model = BrevoModel(self.capacity, 1) 

        self.location = location
        self.destination = None
        self.distance_remaining = 0
        self.time_remaining = 0
        self.status = VehicleStatus.IDLE

    def tick(delta_t, ambient_t):
        self.time_elapsed = self.time_remaining
        self.time_remaining = self.time_remaining - delta_t
        if self.time_remaining <= 0:
            self.status = VehicleStatus.IDLE
            W = self.efficiency * self.distance_remaining / 100
            self.battery.discharge(W, self.time_elapsed, ambient_t)



