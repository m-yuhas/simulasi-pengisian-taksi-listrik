from enum import Enum

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
        self.status = 'INIT'

class NYCJob:

    def __init__(self, row_dict):
        self.start_loc = int(row_dict['PULocationID'])
        self.end_loc = int(row_dict['DOLocationID'])
        self.start_time = datetime.datetime.strptime(row_dict['tpep_pickup_datetime'], '%m/%d/%Y %I:%M:%S %p')
        self.service_time = (datetime.datetime.strptime(row_dict['tpep_dropoff_datetime'], '%m/%d/%Y %I:%M:%S %p')) - self.start_time).total_seconds()
        self.distance = float(row_dict['trip_distance'])
        self.vehicle = None
        self.status = JobStatus.ARRIVED

        if self.distance <= 0 or self.service_time <= 0:
            raise Exception

