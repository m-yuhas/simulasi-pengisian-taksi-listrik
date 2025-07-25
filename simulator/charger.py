class Charger:

    def __init__(self, **kwargs):
        self.queue_size = kwargs.get('queue_size', 0.0)
        self.ports = kwargs.get('ports', 1)
        self.charge_rate = kwargs.get('charge_rate', 1)
        self.status = 'INIT'

    def charge(vehicle):
        pass

