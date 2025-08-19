import datetime

from enum import Enum

from vehicle import *

class JobStatus(Enum):
    ARRIVED = 1     # Job created
    ASSIGNED = 2    # Job assigned to vehicle
    INPROGRESS = 3  # Job is being serviced
    REJECTED = 4    # Job not to be serviced
    COMPLETE = 5    # Job successfully completed

class Job:
    
    def __init__(self, **kwargs):
        self.vehicle = None
        self.start_pos = kwargs.get('start_pos')
        self.end_pos = kwargs.get('end_pos')
        self.start_time = kwargs.get('start_time')
        self.end_time = None
        self.status = JobStatus.ARRIVED
        self.elapsed_time = 0

class NYCJob:

    def __init__(self, row_dict):
        self.start_loc = int(row_dict['PULocationID'])
        self.end_loc = int(row_dict['DOLocationID'])
        self.start_time = datetime.datetime.strptime(row_dict['tpep_pickup_datetime'], '%m/%d/%Y %I:%M:%S %p')
        self.service_time = (datetime.datetime.strptime(row_dict['tpep_dropoff_datetime'], '%m/%d/%Y %I:%M:%S %p') - self.start_time).total_seconds()
        self.distance = float(row_dict['trip_distance'])
        self.vehicle = None
        self.status = JobStatus.ARRIVED

        if self.distance <= 0 or self.service_time <= 0:
            raise Exception

    def to_dict(self):
        return {
            'start_loc': self.start_loc,
            'end_loc': self.end_loc,
            'start_time': str(self.start_time),
            'service_time': self.service_time,
            'distance': self.distance,
            'vehicle': self.vehicle.to_dict() if self.vehicle else None,
            'status': self.status.name
        }

    def assign_vehicle(self, vehicle, ttp, dtp):
        if vehicle.status != VehicleStatus.IDLE:
            raise Exception('Only idle vehicle can be assigned to a job')
        self.vehicle = vehicle
        if self.vehicle.location == self.start_loc:
            self.vehicle.staus = VehicleStatus.ONJOB
            self.vehicle.destination = self.end_loc
            self.vehicle.distance_remaining = self.distance
            self.vehicle.time_remaining = self.service_time
            self.status = VehicleStatus.INPROGRESS
        else:
            self.vehicle.status = VehicleStatus.TOPICKUP
            self.vehicle.destination = self.start_loc
            self.status = VehicleStatus.ASSIGNED
            self.vehicle.distance_remaining = dtp
            self.vehicle.time_remaining = ttp

    def tick(self, delta_t, ambient_t):
        if self.vehicle:
            if self.vehicle.status == VehicleStatus.TOPICKUP:
                if self.vehicle.location != self.vehicle.destination:
                    self.vehicle.tick(delta_t, ambient_t)
                else:
                    self.vehicle.status = VehicleStatus.ONJOB
                    self.status = JobStatus.INPROGRESS
                    self.vehicle.destination = self.end_loc
                    self.vehicle.distance_remaining = self.distance
                    self.vehicle.time_remaining = self.service_time
            elif self.vehicle.status == VehicleStatus.ONJOB:
                if self.vehicle.location != self.vehicle.destination:
                    self.vehicle.tick(delta_t, ambient_t)
                else:
                    self.vehicle.status = VehicleStatus.IDLE
                    self.status = JobStatus.COMPLETE
                    self.vehicle.destination = None
                    self.vehicle = None
        if self.status not in [JobStatus.COMPLETE, JobStatus.REJECTED, JobStatus.INPROGRESS]:
            if self.elapsed_time >= 3600:
                self.status = JobStatus.REJECTED #TODO: allow custom reject times
                self.vehicle = None
            self.elapsed_time += delta_t
