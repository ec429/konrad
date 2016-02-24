#!/usr/bin/python

class Gauge(object):
	def __init__(self, dl, cw):
		"""Prototypical Gauge class
		dl: Downlink object
		cw: curses window object
		"""
		self.dl = dl
		self.cw = cw
		self.props = {}
		self.height, self.width = cw.getmaxyx()
	def add_prop(self, name, apistr):
		self.props[name] = apistr
		self.dl.subscribe(apistr)
	def get(self, key, default=None):
		if key not in self.props:
			return default
		return self.dl.get(self.props[key], default)
	def draw(self):
		self.cw.clear()
		self.cw.border()
	def post_draw(self):
		self.cw.refresh()

class FuelGauge(Gauge):
	def __init__(self, dl, cw, resource):
		super(FuelGauge, self).__init__(dl, cw)
		self.resource = resource
		self.add_prop('current', "r.resourceCurrent[%s]"%(self.resource,))
		self.add_prop('max', "r.resourceCurrentMax[%s]"%(self.resource,))
	def draw(self):
		super(FuelGauge, self).draw()
		current = self.get('current')
		full = self.get('max')
		percent = current * 100.0 / full if full else 0
		if self.width < 6:
			text = " " * (self.width - 2)
		elif self.width < 8:
			text = "%03d%%"%(percent,)
		else:
			prec = min(3, self.width - 7)
			num = "%0*.*f%%"%(prec + 4, prec, percent)
			text = "%s %s"%(num, self.resource)
		self.cw.addstr(1, 1, text[:self.width - 2])

if __name__ == '__main__':
	import downlink, curses
	scr = curses.initscr()
	dl = downlink.connect_default()
	gauges = [
		FuelGauge(dl, scr.derwin(3, 24, 1, 1), 'LiquidFuel'),
		FuelGauge(dl, scr.derwin(3, 24, 4, 1), 'Oxidiser'),
		]
	status = "Nominal"
	try:
		while True:
			dl.update()
			for g in gauges:
				try:
					g.draw()
					g.post_draw()
				except curses.error as e:
					status = "ERR: " + repr(e)
			scr.addstr(23, 1, "st " + status.ljust(73)[:73])
			scr.refresh()
	except:
		curses.endwin()
		raise
