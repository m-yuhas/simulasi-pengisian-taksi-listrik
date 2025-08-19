from vehicle import *

class Charger:

    def __init__(self, **kwargs):
        self.queue_size = kwargs.get('queue_size', 0.0)
        self.ports = kwargs.get('ports', 1)
        self.charge_rate = kwargs.get('charge_rate', 1)
        self.status = 'INIT'

    def charge(vehicle):
        pass


class ChargingPort:

    def __init__(self):
        self.charge_power = 0.0
        self.vehicle = None

    def to_dict(self):
        return {
            'charge_power': self.charge_power,
            'vehicle': self.vehicle.to_dict() if self.vehicle else None
        }

    def charge(self, vehicle):
        pass

class DCFastCharger:
    
    def __init__(self, location, ports, queue_size, max_port_power, max_station_power, efficiency):
        self.ports = [ChargingPort() for port in range(ports)]
        self.vehicle_queue = set()
        self.vehicles_en_route = set()
        self.max_queue_size = queue_size
        self.max_port_power = max_port_power
        self.max_station_power = max_station_power
        self.efficiency = efficiency
        self.location = location

    def to_dict(self):
        return {
            'ports': [p.to_dict() for p in self.ports],
            'vehicle_queue': [v.to_dict() for v in self.vehicle_queue],
            'vehicles_en_route': [v.to_dict() for v in self.vehicles_en_route],
            'max_queue_size': self.max_queue_size,
            'max_port_power': self.max_port_power,
            'max_station_power': self.max_station_power,
            'efficiency': self.efficiency,
            'location': self.location
        }

    def assign_vehicle(self, vehicle, charging_rate, end_capacity):
        if vehicle.location != self.location:
            raise Exception('Vehicle needs to be at charging location')
        assigned = False
        for port in self.ports:
            if not port.vehicle:
                port.vehicle = vehicle
                port.vehicle.next_charge_rate = charging_rate
                port.vehicle.end_capacity = end_capacity
                port.vehicle.status = VehicleStatus.CHARGING
                assigned = True
            elif port.vehicle == vehicle:
                port.vehicle.next_charge_rate = charging_rate
                port.vehicle.end_capacity = end_capacity
                assigned = True
        if not assigned:
            raise Exception('All chargers are full')

    def tick(self, delta_t, ambient_t):
        for port in self.ports:
            if port.vehicle:
                port.vehicle.battery.charge(vehicle.next_charge_rate * delta_t / 3600, delta_t, ambient_t)
                if port.vehicle.battery.soc >= port.vehicle.end_capacity:
                    port.vehicle.status = VehicleStatus.IDLE
                    port.vehicle = None
        # TODO: add concept of charging queue
        #if len(self.vehicle_queue) > self.max_queue_size:
        #    raise Exception('Too many vehicles in station queue')
