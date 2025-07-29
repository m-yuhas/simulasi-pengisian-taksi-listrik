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
            self.efficiency = 17.1

        if self.battery.lower() == 'brevo':
            self.battery_model = BrevoModel(self.capacity, 1): 

        self.location = location
        self.destination = None
        self.status = VehicleStatus.IDLE

    def go_to(location):
        pass

