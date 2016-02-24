#!/usr/bin/python

import curses

def register_colours():
	curses.start_color()
	curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_RED)
	curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)
	curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_GREEN)

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
	def centext(self, txt):
		return txt.center(self.width - 2)[:self.width - 2]
	def draw(self):
		self.cw.clear()
		self.cw.border()
	def post_draw(self):
		self.cw.refresh()

class PercentageGauge(Gauge):
	def draw(self, n, d, s):
		super(PercentageGauge, self).draw()
		if d is None or d < 0:
			if self.width < 9:
				text = "N/A"
			else:
				text = "N/A: " + s
			self.cw.addstr(1, 1, self.centext(text))
			self.cw.chgat(1, 1, self.width - 2, curses.color_pair(0)|curses.A_BOLD)
			return
		percent = n * 100.0 / d if d > 0 else 0
		if self.width < 6:
			text = " " * (self.width - 2)
		elif self.width < 8:
			text = "%03d%%"%(percent,)
		else:
			prec = min(3, self.width - 7)
			num = "%0*.*f%%"%(prec + 4, prec, percent)
			text = "%s %s"%(num, s)
		self.cw.addstr(1, 1, text[:self.width - 2])
		blocks = (self.width - 2) * 3
		filled = int(blocks * percent / 100.0 + 0.5)
		green = int(filled / 3)
		self.cw.chgat(1, 1, green, curses.color_pair(3))
		if green < self.width - 2:
			self.cw.chgat(1, green + 1, 1, curses.color_pair(filled % 3))
		if green < self.width - 3:
			self.cw.chgat(1, green + 2, self.width - green - 3, curses.color_pair(0))

class FuelGauge(PercentageGauge):
	def __init__(self, dl, cw, resource):
		super(FuelGauge, self).__init__(dl, cw)
		self.resource = resource
		self.add_prop('current', "r.resourceCurrent[%s]"%(self.resource,))
		self.add_prop('max', "r.resourceCurrentMax[%s]"%(self.resource,))
	def draw(self):
		current = self.get('current')
		full = self.get('max')
		super(FuelGauge, self).draw(current, full, self.resource)

if __name__ == '__main__':
	import downlink
	scr = curses.initscr()
	register_colours()
	dl = downlink.connect_default()
	gauges = [
		FuelGauge(dl, scr.derwin(3, 27, 1, 1), 'LiquidFuel'),
		FuelGauge(dl, scr.derwin(3, 27, 4, 1), 'Oxidizer'),
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
			scr.addstr(23, 1, "status: " + status.ljust(68)[:68])
			scr.refresh()
	except:
		curses.endwin()
		raise
