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

        if battery.lower() == 'brevo':
            self.battery = BrevoModel(self.capacity, 1) 
        if battery.lower() == 'wan':
            self.battery = WanModel(self.capacity, 1)

        self.location = location
        self.destination = None
        self.distance_remaining = 0
        self.time_remaining = 0
        self.time_elapsed = 0
        self.status = VehicleStatus.IDLE

    def to_dict(self):
        return {
            'location': self.location,
            'destination': self.destination,
            'distance_remaining': self.distance_remaining,
            'time_remaining': self.time_remaining,
            'status': self.status.name,
            'battery': self.battery.to_dict(),
            'time_elapsed': self.time_elapsed
        }

    def tick(self, delta_t, ambient_t):
        self.time_elapsed += min(self.time_remaining, delta_t.total_seconds())
        self.time_remaining -= delta_t.total_seconds()
        if self.time_remaining <= 0:
            self.status = VehicleStatus.IDLE
            W = self.distance_remaining * self.efficiency / 100
            self.battery.discharge(W, self.time_elapsed, ambient_t)
            self.distance_remaining = 0
            self.time_elapsed = 0
            self.time_remaining = 0
            self.location = self.destination
