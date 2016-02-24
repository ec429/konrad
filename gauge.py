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
    def draw(self):
        self.cw.clear()
        self.cw.border()
    def post_draw(self):
        self.cw.refresh()

class OneLineGauge(Gauge):
    def __init__(self, dl, cw):
        super(OneLineGauge, self).__init__(dl, cw)
        self.bordered = self.height > 2
        if self.bordered:
            self.height -= 2
            self.width -= 2
        self.olg_width = self.width
    def centext(self, txt):
        w = self.olg_width
        return txt.center(w)[:w]
    def draw(self):
        self.cw.clear()
        if self.bordered:
            self.cw.border()
    def addstr(self, txt):
        off = int(self.bordered)
        self.cw.addstr(off, off, txt[:self.olg_width])
    def chgat(self, xoff, num, attr):
        off = int(self.bordered)
        num = min(num, self.olg_width - xoff)
        if num > 0:
            self.cw.chgat(off, off + xoff, num, attr)

class StatusReadout(OneLineGauge):
    def __init__(self, dl, cw, label):
        super(StatusReadout, self).__init__(dl, cw)
        self.label = label
        self.width -= len(label)
        self.text = ''.ljust(self.width)
    def draw(self):
        super(StatusReadout, self).draw()
        self.addstr(self.label + self.text)
    def push(self, txt):
        self.text = ("%s < %s"%(self.text, txt))[-self.width:]

class TimeGauge(OneLineGauge):
    def __init__(self, dl, cw):
        super(TimeGauge, self).__init__(dl, cw)
        self.add_prop('T', 'v.missionTime')
    def draw(self):
        super(TimeGauge, self).draw()
        t = self.get('T')
        s = t % 60
        m = (t / 60) % 60
        h = (t / 3600)
        if h < 24:
            self.addstr('T+%02d:%02d:%02d'%(h, m, s))
        else:
            d = h / 24
            h %= 24
            self.addstr('T+%02dd%02d:%02d'%(d, h, m))

class PercentageGauge(OneLineGauge):
    def draw(self, n, d, s):
        super(PercentageGauge, self).draw()
        if d is None or d < 0:
            if self.width < 7:
                text = "N/A"
            else:
                text = "N/A: " + s
            self.addstr(self.centext(text))
            self.chgat(0, self.width, curses.color_pair(0)|curses.A_BOLD)
            return
        percent = n * 100.0 / d if d > 0 else 0
        if self.width < 4:
            text = " " * (self.width - 2)
        elif self.width < 6:
            text = "%03d%%"%(percent,)
        else:
            prec = min(3, self.width - 5)
            num = "%0*.*f%%"%(prec + 4, prec, percent)
            text = "%s %s"%(num, s)
        self.addstr(text[:self.width])
        blocks = self.width * 3
        filled = int(blocks * percent / 100.0 + 0.5)
        green = int(filled / 3)
        self.chgat(0, green, curses.color_pair(3))
        if green < self.width:
            self.chgat(green, 1, curses.color_pair(filled % 3))
        if green < self.width - 1:
            self.chgat(green + 1, self.width - green - 1, curses.color_pair(0))

class FuelGauge(PercentageGauge):
    def __init__(self, dl, cw, resource):
        super(FuelGauge, self).__init__(dl, cw)
        self.resource = resource
        self.add_prop('current', "r.resourceCurrent[%s]"%(self.resource,))
        self.add_prop('max', "r.resourceCurrentMax[%s]"%(self.resource,))
        self.zero = False
    def draw(self):
        current = self.get('current')
        full = self.get('max')
        super(FuelGauge, self).draw(current, full, self.resource)
        if current < 0.01 and full > 0:
            if not self.zero:
                self.zero = True
                return 'Stage %s exhausted'%(self.resource,)
        else:
            self.zero = False

class GaugeGroup(object):
    def __init__(self, cw, gl, title):
        self.cw = cw
        self.gl = gl
        self.title = title
    def draw(self):
        self.cw.clear()
        self.cw.border()
        if self.title:
            _, width = self.cw.getmaxyx()
            title = self.title[:width]
            mid = (width - len(title)) / 2
            self.cw.addstr(0, mid, title)
        messages = []
        for g in self.gl:
            m = g.draw()
            if m is not None:
                messages.append(m)
    def post_draw(self):
        for g in self.gl:
            g.post_draw()
        self.cw.refresh()

if __name__ == '__main__':
    import downlink
    scr = curses.initscr()
    try:
        register_colours()
        dl = downlink.connect_default()
        scr.addstr(0, 31, "KONRAD: Gauges demo")
        fuel = scr.derwin(4, 27, 10, 53)
        fuelgroup = GaugeGroup(fuel, [
            FuelGauge(dl, fuel.derwin(1, 25, 1, 1), 'LiquidFuel'),
            FuelGauge(dl, fuel.derwin(1, 25, 2, 1), 'Oxidizer'),
            ], 'Stage Propellant')
        status = StatusReadout(dl, scr.derwin(1, 78, 23, 1), 'status:')
        status.push("Nominal")
        time = TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        groups = [fuelgroup, status, time]
        while True:
            dl.update()
            for g in groups:
                try:
                    m = g.draw()
                    g.post_draw()
                    if m is not None:
                        status.push(m)
                except curses.error as e:
                    status.push("dpyerr " + repr(e))
            scr.refresh()
    finally:
        curses.endwin()
