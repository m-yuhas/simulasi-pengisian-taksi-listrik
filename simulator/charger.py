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

    def charge(self, vehicle):
        pass

class DCFastCharger:
    
    def __init__(self, location, ports, queue_size, max_port_power, max_station_power, efficiency):
        self.ports = [port for ChargingPort() in range(self.port)]
        self.vehicle_queue = set()
        self.vehicles_en_route = set()
        self.max_queue_size = queue_size
        self.max_port_power = max_port_power
        self.max_station_power = max_station_power
        self.efficiency = efficiency
        self.location = location

    def assign_vehicle(self, vehicle):
        if vehicle.status != VehicleStatus.IDLE:
            raise Exception('Only idling vehicle can be assigned to a charger')
        if vehicle.location == self.location:
            self.vehicle_queue.append(vehicle)
        else:
            vehicle.destination = self.location
            self.vehicles_en_route.append(vehicle)

    def tick(self):
        for vehicle in self.vehicles_en_route:
            vehicle.tick()
            if vehicle.location == self.location:
                self.vehicle_queue.add(vehicle)
                self.vehicles_en_route.remove(vehicle)
        for port in self.ports:
            if port.vehicle:
                port.vehicle.battery.charge("TODO:")
                if stop condition:
                    port.vehicle.state = VehicleState.IDLE
                    port.vehicle = None
            else:
                if len(self.vehicle_queue) > 1:
                    port.vehicle = #TODO
        if len(self.vehicle_queue) > self.max_queue_size:
            raise Exception('Too many vehicles in station queue')
