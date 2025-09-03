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
        self.vehicle_queue = []
        self.rates_queue = []
        self.stop_cond_queue = []
        self.vehicles_en_route = []
        self.max_queue_size = queue_size
        self.max_port_power = max_port_power
        self.max_station_power = max_station_power
        self.efficiency = efficiency
        self.location = location

    def to_dict(self):
        return {
            'ports': [p.to_dict() for p in self.ports],
            'vehicle_queue': [v.to_dict() for v in self.vehicle_queue],
            'vehicles_en_route': [v['vehicle'].to_dict() for v in self.vehicles_en_route],
            'max_queue_size': self.max_queue_size,
            'max_port_power': self.max_port_power,
            'max_station_power': self.max_station_power,
            'efficiency': self.efficiency,
            'location': self.location
        }


    def assign_vehicle(self, vehicle, charging_rate, end_capacity):
        assigned = False
        for port in self.ports:
            if not port.vehicle:
                port.vehicle = vehicle
                port.vehicle.next_charge_rate = charging_rate
                port.vehicle.end_capacity = end_capacity
                port.vehicle.status = VehicleStatus.CHARGING
                assigned = True
                break
            elif port.vehicle == vehicle:
                port.vehicle.next_charge_rate = charging_rate
                port.vehicle.end_capacity = end_capacity
                assigned = True
                break
        if not assigned and vehicle not in self.vehicle_queue:
            self.vehicle_queue.append(vehicle)
            self.rates_queue.append(charging_rate)
            self.stop_cond_queue.append(end_capacity)
        if assigned and vehicle in self.vehicle_queue:
            idx = self.vehicle_queue.index(vehicle)
            del self.vehicle_queue[idx]
            del self.rates_queue[idx]
            del self.stop_cond_queue[idx]

    def tick(self, delta_t, ambient_t):
        to_remove = []
        for idx, v in enumerate(self.vehicles_en_route):
            if v['vehicle'].location == self.location:
                self.assign_vehicle(v['vehicle'], v['rate'], v['condition'])
                to_remove.append(idx)
        for idx in sorted(to_remove, reverse=True):
            del self.vehicles_en_route[idx]
        for idx, v in enumerate(self.vehicle_queue):
            self.assign_vehicle(self.vehicle_queue[idx], self.rates_queue[idx], self.stop_cond_queue[idx])
        for port in self.ports:
            if port.vehicle:
                #print(port.vehicle.battery.to_dict())
                port.vehicle.battery.charge(port.vehicle.next_charge_rate * delta_t.total_seconds() / 3600, delta_t.total_seconds(), ambient_t)
                if port.vehicle.battery.soc >= port.vehicle.end_capacity:
                    port.vehicle.status = VehicleStatus.IDLE
                    port.vehicle = None
        # TODO: add concept of charging queue
        #if len(self.vehicle_queue) > self.max_queue_size:
        #    raise Exception('Too many vehicles in station queue')
