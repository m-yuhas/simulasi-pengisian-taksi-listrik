from typing import Dict, ForwardRef, Union
from enum import Enum

from battery import *
from region import *

class VehicleStatus(Enum):
    IDLE = 1
    TOPICKUP = 2
    TOCHARGE = 3
    CHARGING = 4
    TOLOC = 5
    ONJOB = 6
    OFFDUTY = 7
    RECOVERY = 8

class Vehicle:
    """Electric Vehicle.

    Args:
        model: select from previously defined vehicles: ['byd e6'] or provide
            a diction in the format {'capacity': kWh, 'efficiency': kWh/100km}
        battery: select from previously defined models: ['multistage'] or
            provide an object inheriting from Battery.
        location: starting location of the vehicle.
    """

    def __init__(self, model: Union[str, Dict[str, float]], battery: Union[str, Battery], location: Location, vid: int) -> None:
        self.model = model
        self.vid = vid
        self.charger = None
        if self.model.lower() == 'byd e6':
            capacity = 71.7
            self.efficiency = 17.1
        else:
            capacity = model['capacity']
            self.efficiency = model['efficiency']

        if battery.lower() == 'multistage':
            self.battery = MultiStageBattery(capacity)
        else:
            self.battery = battery

        self.depo = location
        self.location = location
        self.destination = location
        self.distance_remaining = 0.0
        self.time_remaining = 0.0
        self.time_elapsed = 0.0
        self.status = VehicleStatus.IDLE

    def to_dict(self):
        return {
            'location': self.location.to_dict(),
            'destination': self.destination.to_dict(),
            'distance_remaining': self.distance_remaining,
            'time_remaining': self.time_remaining,
            'status': self.status.name,
            'battery': self.battery.to_dict(),
            'time_elapsed': self.time_elapsed
        }

    def service_demand(self, job: ForwardRef('Job')):
        if self.charger:
            self.charger.disconnect(self.vid)
        self.destination = job.pickup_location
        self.time_remaining = self.location.to(self.destination)[1]
        self.job = job
        self.job.assign_vehicle(self.vid)
        self.status = VehicleStatus.TOPICKUP

    def charge(self, charger: ForwardRef('ChargeStation'), preferred_rate: float):
        self.charger = charger
        self.destination = charger.location
        self.time_remaining = self.location.to(self.destination)[1]
        self.preferred_rate = preferred_rate
        if self.status != VehicleStatus.CHARGING or self.location != self.destination:
            self.status = VehicleStatus.TOCHARGE
            self.charger.disconnect(self.vid)

    def idle(self):
        if self.charger:
            self.charger.disconnect(self.vid)

    def initialize_recovery_state():
        self.destination = self.depo
        self.time_remaining = 24 * 60 * 60
        self.soc = 1.0

    def tick(self, dt: int, conditions: Dict[str, int]):
        if self.status == VehicleStatus.IDLE:
            self.battery.age(dt, conditions['T_a'])
        elif self.status == VehicleStatus.TOPICKUP:
            if self.time_remaining <= 0:
                distance = self.location.to(self.destination)[0]
                dW = distance * self.efficiency / 100
                self.battery.discharge(dW, dt, conditions['T_a'])
                if self.battery.soc <= 0:
                    self.status = VehicleStatus.RECOVERY
                    self.job.fail()
                    self.initialize_recovery_state()
                else:
                    self.destination = self.job.dropoff_location
                    self.time_remaining = self.location.to(self.destination)[1]
                    self.job.inprogress()
                    self.status = VehicleStatus.ONJOB
            else:
                self.time_remaining -= dt
        elif self.status == VehicleStatus.TOCHARGE:
            if self.time_remaining <= 0:
                distance = self.location.to(self.destination)[0]
                dW = distance * self.efficiency / 100
                self.battery.discharge(dW, dt, conditions['T_a'])
                if self.battery.soc <= 0:
                    self.status = VehicleStatus.RECOVERY
                    self.initialize_recovery_state()
                else:
                    self.status = VehicleStatus.CHARGING
            else:
                self.time_remaining -= dt
        elif self.status == VehicleStatus.CHARGING:
            self.charger.request_charge(self.preferred_rate, self.vid)
            #self.battery.charge(dW, dt, conditions['T_a'])
        elif self.status == VehicleStatus.TOLOC:
            if self.time_remaining <= 0:
                distance = self.location.to(self.destination)[0]
                dW = distance * self.efficiency / 100
                self.battery.discharge(dW, dt, conditions['T_a'])
                if self.battery.soc <= 0:
                    self.status = VehicleStatus.RECOVERY
                    self.initialize_recovery_state()
                else:
                    self.status = VehicleStatus.IDLE
            else:
                self.time_remaining -= dt
        elif self.status == VehicleStatus.ONJOB:
            if self.time_remaining <= 0:
                distance = self.location.to(self.destination)[0]
                dW = distance * self.efficiency / 100
                self.battery.discharge(dW, dt, condition['T_a'])
                if self.battery.soc <= 0:
                    self.status = VehicleStatus.RECOVERY
                    self.job.fail()
                    self.initialize_recovery_state()
                else:
                    self.status = VehicleStatus.IDLE
                    self.job.complete()
            else:
                self.time_remaining -= dt
        elif self.status == VehicleStatus.RECOVERY:
            if self.time_remaining <= 0:
                self.status = VehicleStatus.IDLE
            else:
                self.time_remaining -= dt
        else:
            raise Exception(f'Invalid vehicle state: {self.status}')
