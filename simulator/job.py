"""Jobs."""
from typing import Dict
from enum import Enum


import datetime


from region import *
from vehicle import *


DATEFMT = '%Y-%m-%d %H:%M:%S'


class JobStatus(Enum):
    ARRIVED = 1     # Job created
    ASSIGNED = 2    # Job assigned to vehicle
    INPROGRESS = 3  # Job is being serviced
    REJECTED = 4    # Job not to be serviced
    COMPLETE = 5    # Job successfully completed
    FAILED = 6      # Job failed


class Job:
    
    def __init__(self, data: Dict, job_id: int, region):
        self.id = job_id
        self.pickup_location = CyclicZoneGraphLocation(int(data['pickup_location']), region)
        self.dropoff_location = CyclicZoneGraphLocation(int(data['dropoff_location']), region)
        self.duration = datetime.datetime.strptime(data['dropoff_time'], DATEFMT) - datetime.datetime.strptime(data['pickup_time'], DATEFMT)
        self.distance = float(data['distance'])
        self.vehicle = None
        self.status = JobStatus.ARRIVED
        self.elapsed_time = 0

    def to_dict(self):
        return {
            'pickup_location': self.pickup_location.to_dict(),
            'dropoff_location': self.dropoff_location.to_dict(),
            'duration': self.duration.total_seconds(),
            'distance': self.distance,
            'vehicle': self.vehicle,
            'status': self.status.name,
            'id': self.id
        }

    def assign_vehicle(self, vehicle):
        self.status = JobStatus.ASSIGNED
        self.vehicle = vehicle

    def inprogress(self):
        self.status = JobStatus.INPROGRESS

    def complete(self):
        self.status = JobStatus.COMPLETE

    def fail(self):
        self.status = JobStatus.FAILED

    def tick(self, dt):
        self.elapsed_time += dt
        if self.status == JobStatus.ARRIVED:
            if self.elapsed_time > dt:
                self.status = JobStatus.REJECTED
