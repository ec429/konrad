#!/usr/bin/python

import curses
import math

def initialise():
    register_colours()
    curses.nonl()

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
        return txt.center(w)[:w-1]
    def draw(self):
        self.cw.clear()
        if self.bordered:
            self.cw.border()
    def addstr(self, txt):
        off = int(self.bordered)
        try:
            self.cw.addnstr(off, off, txt, self.olg_width)
        except curses.error:
            # for some reason addnstr doesn't like the bottom-right cell in a
            # window.  maybe it's trying to move the cursor past it...
            pass
    def chgat(self, xoff, num, attr):
        off = int(self.bordered)
        num = min(num, self.olg_width - xoff)
        if num > 0:
            self.cw.chgat(off, off + xoff, num, attr)

class StatusReadout(OneLineGauge):
    def __init__(self, dl, cw, label):
        super(StatusReadout, self).__init__(dl, cw)
        self.label = label
        self.width -= len(label) + 1
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

class BodyGauge(OneLineGauge):
    def __init__(self, dl, cw, body):
        super(BodyGauge, self).__init__(dl, cw)
        self.add_prop('name', 'b.name[%d]'%(body,))
    def draw(self):
        super(BodyGauge, self).draw()
        name = self.get('name')
        self.addstr(self.centext(name))

class SIGauge(OneLineGauge):
    unit = ''
    label = ''
    maxwidth = 6
    def draw(self, value):
        super(SIGauge, self).draw()
        sgn = '' if value >= 0 else '-'
        width = self.width - len(self.label) - len(self.unit) - 2
        digits = min(width, self.maxwidth)
        sz = math.log10(abs(value)) if value else 1
        if sgn: sz += 1
        pfx = ('', 1)
        if sz >= digits:
            pfx = ('k', 1000)
        if sz >= digits + 2:
            pfx = ('M', 1e6)
        if sz >= digits + 5:
            pfx = ('G', 1e9)
        if sz >= digits + 8:
            pfx = ('T', 1e12)
        self.addstr('%s: %*d%s%s'%(self.label, width - len(pfx[0]), value / pfx[1], pfx[0], self.unit))

class AltitudeGauge(SIGauge):
    unit = 'm'
    label = 'Altitude'
    def __init__(self, dl, cw, body):
        super(AltitudeGauge, self).__init__(dl, cw)
        self.add_prop('alt', 'v.altitude')
        self.add_prop('atm_top', 'b.maxAtmosphere[%d]'%(body,))
        self.vac = False
    def draw(self):
        alt = self.get('alt')
        super(AltitudeGauge, self).draw(alt)
        atm_top = self.get('atm_top')
        if alt > atm_top:
            if not self.vac:
                self.vac = True
                return 'Clear of atmosphere'
        else:
            if self.vac:
                self.vac = False
                return 'Entered atmosphere'

class PeriapsisGauge(SIGauge):
    unit = 'm'
    label = 'Periapsis'
    def __init__(self, dl, cw, body):
        super(PeriapsisGauge, self).__init__(dl, cw)
        self.add_prop('peri', 'o.PeA')
        self.add_prop('atm_top', 'b.maxAtmosphere[%d]'%(body,))
        self.orb = False
    def draw(self):
        peri = self.get('peri')
        super(PeriapsisGauge, self).draw(peri)
        atm_top = self.get('atm_top')
        if peri > atm_top:
            if not self.orb:
                self.orb = True
                return 'Stable orbit achieved'
        else:
            if self.orb:
                self.orb = False
                return 'Orbit is no longer stable'

class ApoapsisGauge(SIGauge):
    unit = 'm'
    label = 'Apoapsis'
    def __init__(self, dl, cw):
        super(ApoapsisGauge, self).__init__(dl, cw)
        self.add_prop('apo', 'o.ApA')
    def draw(self):
        super(ApoapsisGauge, self).draw(self.get('apo'))

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

global fallover

class GaugeGroup(object):
    def __init__(self, cw, gl, title):
        self.cw = cw
        self.gl = gl
        self.title = title
    def draw(self):
        self.cw.clear()
        if self.title:
            self.cw.border()
            _, width = self.cw.getmaxyx()
            title = self.title[:width]
            mid = (width - len(title)) / 2
            self.cw.addstr(0, mid, title)
        messages = []
        for g in self.gl:
            try:
                m = g.draw()
                if m is not None:
                    if isinstance(m, str):
                        messages.append(m)
                    elif isinstance(m, list):
                        messages.extend(m)
                    else:
                        messages.append(str(m))
            except curses.error as e:
                messages.append("dpyerr " + repr(e))
                if fallover: raise
            except Exception as e:
                messages.append("telerr " + repr(e))
                if fallover: raise
        return messages
    def post_draw(self):
        for g in self.gl:
            g.post_draw()
        self.cw.refresh()

if __name__ == '__main__':
    import downlink
    scr = curses.initscr()
    try:
        initialise()
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
        top = GaugeGroup(scr, [fuelgroup, status, time], None)
        while True:
            dl.update()
            ml = top.draw()
            top.post_draw()
            if ml is not None:
                for m in ml:
                    status.push(m)
            scr.refresh()
    finally:
        curses.endwin()
