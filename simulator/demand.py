import csv
import datetime

from job import *

class ReplayDemand:

    def __init__(self, path):
        self.path = path
        self.csvfile = open(path, 'r')
        self.reader = csv.DictReader(self.csvfile)
        self.last = self.reader.__next__()
        self.global_idx = 0

    def get_demand(self, start, end):
        demand = {}
        last_start = datetime.datetime.strptime(self.last['tpep_pickup_datetime'], '%m/%d/%Y %I:%M:%S %p')
        end = last_start + (end - start)
        try:
            #while last_start < start:
            #    self.last = self.reader.__next__()
            #    if self.last['VendorID'] == '':
            #        self.last = self.reader.__next__()
            #        continue
            #    else:
            #        last_start = datetime.datetime.strptime(self.last['tpep_pickup_datetime'], '%m/%d/%Y %I:%M:%S %p')
            while last_start < end:
                try:
                    demand[self.global_idx] = NYCJob(self.last, self.global_idx)
                    self.global_idx += 1
                except Exception as e:
                    pass
                self.last = self.reader.__next__()
                if self.last['VendorID'] == '':
                    self.last = self.reader.__next__()

                #print(self.last)
                ll_start = last_start
                last_start = datetime.datetime.strptime(self.last['tpep_pickup_datetime'], '%m/%d/%Y %I:%M:%S %p')
                if abs((last_start - ll_start).total_seconds()) > 2 * 3600:
                    last_start = ll_start
                    self.last = self.reader.__next__()
            return demand
        except StopIteration:
            self.csvfile.close()
            self.csvfile = open(self.path, 'r')
            self.reader = csv.DictReader(self.csvfile)
            self.last = self.reader.__next__()
            last_start = datetime.datetime.strptime(self.last['tpep_pickup_datetime'], '%m/%d/%Y %I:%M:%S %p')
            self.global_idx += 1
            return self.get_demand(last_start, last_start + (end - start))

# {'VendorID': '1', 'tpep_pickup_datetime': '01/01/2020 12:28:15 AM', 'tpep_dropoff_datetime': '01/01/2020 12:33:03 AM', 'passenger_count': '1', 'trip_distance': '1.2', 'RatecodeID': '1', 'store_and_fwd_flag': 'N', 'PULocationID': '238', 'DOLocationID': '239', 'payment_type': '1', 'fare_amount': '6', 'extra': '3', 'mta_tax': '0.5', 'tip_amount': '1.47', 'tolls_amount': '0', 'improvement_surcharge': '0.3', 'total_amount': '11.27', 'congestion_surcharge': '2.5'}

