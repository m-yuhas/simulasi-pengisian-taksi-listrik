import json
import logging
import time

import zmq
import coloredlogs

LOGGER = logging.getLogger('Charge Simulator')
coloredlogs.install(level='DEBUG')

#random.seed(0)
#numpy.random.seed(0)

port = 6969

context = zmq.Context()
LOGGER.debug('Connecting to simulator...')
socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:%s" % port)

while True:
    LOGGER.debug('Sending Request')
    request = {'actions': []}

    socket.send_string(json.dumps(request))
    response = socket.recv()
    LOGGER.debug('RESPONSE:')
    LOGGER.debug(response)
    time.sleep(1)
