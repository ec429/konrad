#!/usr/bin/python

import websocket
import json

class Downlink(object):
	def __init__(self, addr, port, rate):
		self.uri = "ws://%s:%d/datalink"%(addr, port)
		self.rate = rate
		self.subscriptions = set([])
		self.reconnect()
	def reconnect(self):
		self.ws = websocket.create_connection(self.uri)
		self.set_rate()
		self.resubscribe()
	def disconnect(self):
		self.ws.close()
		self.ws = None
	def send_msg(self, d):
		s = json.dumps(d)
		print "Send", s
		self.ws.send(s)
	def set_rate(self):
		self.send_msg({'rate': self.rate})
		self.ws.settimeout(2000.0 / self.rate)
	def resubscribe(self):
		for key in self.subscriptions:
			self._subscribe(key)
	def listen(self):
		while True:
			try:
				msg = self.ws.recv()
				break
			except websocket.WebSocketTimeoutException:
				return {}
			except websocket.WebSocketConnectionClosedException:
				self.reconnect()
			except KeyboardInterrupt:
				self.disconnect()
				raise
		return json.loads(msg)
	def subscribe(self, key):
		self.subscriptions.add(key)
		self._subscribe(key)
	def _subscribe(self, key):
		self.send_msg({'+':[key]})
	def unsubscribe(self, key):
		self.subscriptions.discard(key)
		self.send_msg({'-':[key]})

if __name__ == '__main__':
	# Simple test code
	import pprint
	dl = Downlink("localhost", 8085, 1000)
	dl.subscribe("v.altitude")
	dl.subscribe("r.resource[LiquidFuel]")
	while True:
		d = dl.listen()
		pprint.pprint(d)
