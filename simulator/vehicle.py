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

        if self.battery.lower() == 'johnen':
            self.battery_model = None
            

        self.location = location
        self.soc = 1
        self.status = VehicleStatus.IDLE

    def go_to(location):
        pass

