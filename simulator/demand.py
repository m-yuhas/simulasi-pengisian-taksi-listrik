import datetime

from job import *

class ReplayDemand:

    def __init__(self, path):
        self.csvfile = open(path, 'r')
        self.reader = csv.DictReader(csvfile)
        self.last = self.reader.__next__()

    def get_demand(start, end):
        last_start = datetime.datetime.strptime(self.last['tpep_pickup_datetime'], '%m/%d/%Y %I:%M:%S %p')
        while last_start >= start and last_start < end:
            try:
                yield NYCJob(self.last)
            except Exception:
                continue
            self.last = self.reader.__next__()
        raise StopIteration

# {'VendorID': '1', 'tpep_pickup_datetime': '01/01/2020 12:28:15 AM', 'tpep_dropoff_datetime': '01/01/2020 12:33:03 AM', 'passenger_count': '1', 'trip_distance': '1.2', 'RatecodeID': '1', 'store_and_fwd_flag': 'N', 'PULocationID': '238', 'DOLocationID': '239', 'payment_type': '1', 'fare_amount': '6', 'extra': '3', 'mta_tax': '0.5', 'tip_amount': '1.47', 'tolls_amount': '0', 'improvement_surcharge': '0.3', 'total_amount': '11.27', 'congestion_surcharge': '2.5'}

