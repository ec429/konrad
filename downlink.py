#!/usr/bin/python

import websocket
import json

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 8085
DEFAULT_RATE = 1000

class Downlink(object):
    def __init__(self, addr, port, rate):
        self.uri = "ws://%s:%d/datalink"%(addr, port)
        self.rate = rate
        self.subscriptions = {}
        self.data = {}
        self.reconnect()
    def reconnect(self):
        self.ws = websocket.create_connection(self.uri)
        self.set_rate()
        self.resubscribe()
    def disconnect(self):
        self.ws.close()
        self.ws = None
        self.data = {}
    def send_msg(self, d):
        s = json.dumps(d)
        self.ws.send(s)
    def set_rate(self):
        self.send_msg({'rate': self.rate})
        self.ws.settimeout(self.rate / 500.0)
    def resubscribe(self):
        for key in self.subscriptions:
            self._subscribe(key)
    def listen(self):
        msg = '{}'
        for i in xrange(3):
            try:
                msg = self.ws.recv()
                break
            except websocket.WebSocketTimeoutException:
                break
            except websocket.WebSocketConnectionClosedException:
                self.reconnect()
            except KeyboardInterrupt:
                self.disconnect()
                raise
        return json.loads(msg)
    def update(self):
        d = self.listen()
        if not d: # Loss of Signal
            self.data = {}
        self.data.update(d)
        return self.data
    def get(self, key, default=None):
        return self.data.get(key, default)
    def subscribe(self, key):
        self.subscriptions[key] = self.subscriptions.get(key, 0) + 1
        self._subscribe(key)
    def _subscribe(self, key):
        self.send_msg({'+':[key]})
    def unsubscribe(self, key):
        if self.subscriptions.get(key, 0) > 1:
            self.subscriptions[key] -= 1
        else:
            self.subscriptions.pop(key, None)
            self.data.pop(key, None)
            self.send_msg({'-':[key]})
    def __del__(self):
        # Make sure we disconnect cleanly, or telemachus gets unhappy
        if getattr(self, 'ws', None) is not None:
            self.disconnect()

def connect_default():
    return Downlink(DEFAULT_HOST, DEFAULT_PORT, DEFAULT_RATE)

if __name__ == '__main__':
    # Simple test code
    import pprint
    dl = connect_default()
    dl.subscribe("v.altitude")
    dl.subscribe("r.resource[LiquidFuel]")
    while True:
        d = dl.update()
        pprint.pprint(d)
