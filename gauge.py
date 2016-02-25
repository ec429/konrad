#!/usr/bin/python

import curses
import math

def initialise():
    register_colours()
    curses.nonl()
    curses.curs_set(0)

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

class VLine(Gauge):
    def draw(self):
        super(VLine, self).draw()
        self.cw.vline(0, 0, curses.ACS_VLINE, self.height)

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
        try:
            self.cw.addnstr(off, off, txt, self.olg_width)
        except curses.error:
            # for some reason addnstr doesn't like the bottom-right cell in a
            # window.  maybe it's trying to move the cursor past it...
            pass
    def addch(self, xoff, char, attr=None):
        off = int(self.bordered)
        try:
            old = self.cw.inch(off, off + xoff)
            self.cw.addch(off, off + xoff, char, attr | (old &~0xff))
        except curses.error:
            pass
    def chgat(self, xoff, num, attr):
        off = int(self.bordered)
        num = min(num, self.olg_width - xoff)
        if num > 0:
            self.cw.chgat(off, off + xoff, num, attr)

class FixedLabel(OneLineGauge):
    def __init__(self, dl, cw, text):
        super(FixedLabel, self).__init__(dl, cw)
        self.text = text
    def draw(self):
        super(FixedLabel, self).draw()
        self.addstr(self.text)

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
        if t is None:
            self.addstr('LINK DOWN')
            self.chgat(0, self.width, curses.color_pair(2))
            return
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
        self.add_prop('body', 'v.body')
        self.warn = False
    def draw(self):
        super(BodyGauge, self).draw()
        name = self.get('name')
        if name is None:
            self.addstr(self.centext("LINK DOWN"))
            self.chgat(0, self.width, curses.color_pair(2))
            return
        body = self.get('body')
        wrong = body != name
        text = '%s!%s'%(body, name) if wrong else name
        self.addstr(self.centext(text))
        if wrong:
            if not self.warn:
                self.warn = True
                return 'Change Body: %s'%(body,)

class FractionGauge(OneLineGauge):
    fracmode = 3
    def colour(self, n, d):
        if d is None or d < 0:
            self.chgat(0, self.width, curses.color_pair(0)|curses.A_BOLD)
            return
        frac = n / float(d) if d > 0 else 0
        frac = max(frac, 0)
        blocks = self.width * self.fracmode
        filled = int(blocks * frac + 0.5)
        green = int(filled / self.fracmode)
        if self.fracmode == 3:
            green = min(green, self.width)
            self.chgat(0, green, curses.color_pair(3))
            if green < self.width:
                self.chgat(green, 1, curses.color_pair(filled % 3))
            if green < self.width - 1:
                self.chgat(green + 1, self.width - green - 1, curses.color_pair(0))
        elif self.fracmode == 2:
            if green <= self.width:
                self.chgat(0, green, curses.color_pair(3))
                if green < self.width:
                    self.chgat(green, 0, curses.color_pair(2 if filled % 2 else 0))
                if green < self.width - 1:
                    self.chgat(green + 1, self.width - green - 1, curses.color_pair(0))
            else:
                over = min(green - self.width, self.width)
                green = self.width - over
                self.chgat(0, green, curses.color_pair(3))
                self.chgat(green, over, curses.color_pair(1))
        else:
            raise Exception("Bad fracmode", self.fracmode)

class SIGauge(FractionGauge):
    unit = ''
    label = ''
    maxwidth = 6
    fracmode = 2
    def __init__(self, dl, cw, target=None):
        super(SIGauge, self).__init__(dl, cw)
        self.target=target
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
        if value is None:
            bad = 'NO DATA'
            if width < 8:
                bad = '-'*(width - 1)
            bad = bad.rjust(width - 1)[:width - 1]
            self.addstr('%s: %s %s'%(self.label, bad, self.unit))
            self.chgat(0, self.width, curses.color_pair(2))
        else:
            self.addstr('%s: %*d%s%s'%(self.label, width - len(pfx[0]), value / pfx[1], pfx[0], self.unit))
            if self.target is not None:
                self.colour(value, self.target)

class DownrangeGauge(SIGauge):
    unit = 'm'
    label = 'Downrange'
    def __init__(self, dl, cw, body):
        super(DownrangeGauge, self).__init__(dl, cw)
        self.add_prop('lat', 'v.lat')
        self.add_prop('lon', 'v.long')
        self.add_prop('brad', 'b.radius[%d]'%(body,))
        self.init = None
    def draw(self):
        lat = self.get('lat')
        lon = self.get('lon')
        brad = self.get('brad')
        if None in (lat, lon):
            d = 0
        elif self.init is None:
            self.init = (lat, lon)
            d = 0
        elif brad is None:
            d = 0
        else:
            # https://en.wikipedia.org/wiki/Great-circle_distance#Formulas
            phi1 = math.radians(self.init[0])
            lbd1 = math.radians(self.init[1])
            phi2 = math.radians(lat)
            lbd2 = math.radians(lon)
            dlbd = lbd2 - lbd1
            # dsigma = acs(sin(phi1)sin(phi2)+cos(lbd1)cos(lbd2)cos(dlbd))
            ds = math.acos(math.sin(phi1) * math.sin(phi2) + math.cos(phi1) * math.cos(phi2) * math.cos(dlbd))
            # d = r dsigma
            d = brad * ds
        super(DownrangeGauge, self).draw(d)

class AltitudeGauge(SIGauge):
    unit = 'm'
    label = 'Altitude'
    def __init__(self, dl, cw, body, target=None):
        super(AltitudeGauge, self).__init__(dl, cw, target)
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
    def __init__(self, dl, cw, body, target=None):
        super(PeriapsisGauge, self).__init__(dl, cw, target)
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
    def __init__(self, dl, cw, target=None):
        super(ApoapsisGauge, self).__init__(dl, cw, target)
        self.add_prop('apo', 'o.ApA')
    def draw(self):
        super(ApoapsisGauge, self).draw(self.get('apo'))

class ObtVelocityGauge(SIGauge):
    unit = 'm/s'
    label = 'Velocity'
    fly_v = False
    def __init__(self, dl, cw, target=None, tmu=None, tsma=None, trad=None):
        super(ObtVelocityGauge, self).__init__(dl, cw, target)
        self.tmu = tmu
        self.tsma = tsma
        self.trad = trad
        if self.target is None and None not in [self.tmu, self.tsma, self.trad]:
            self.fly_v = True
            self.add_prop('alt', 'v.altitude')
        self.add_prop('orbV', 'v.orbitalVelocity')
    def draw(self):
        if self.fly_v:
            # sqrt(mu * (2/r - 1/a))
            alt = self.get('alt')
            if alt is not None:
                self.target = math.sqrt(self.tmu * (2.0 / (alt + self.trad) - 1.0 / self.tsma))
            else:
                self.target = None
        super(ObtVelocityGauge, self).draw(self.get('orbV'))

class HSpeedGauge(SIGauge):
    unit = 'm/s'
    label = 'HSpeed'
    def __init__(self, dl, cw):
        super(HSpeedGauge, self).__init__(dl, cw)
        self.add_prop('hs', 'v.surfaceSpeed')
    def draw(self):
        super(HSpeedGauge, self).draw(self.get('hs'))

class VSpeedGauge(SIGauge):
    unit = 'm/s'
    label = 'VSpeed'
    def __init__(self, dl, cw):
        super(VSpeedGauge, self).__init__(dl, cw)
        self.add_prop('vs', 'v.verticalSpeed')
    def draw(self):
        super(VSpeedGauge, self).draw(self.get('vs'))

class DynPresGauge(SIGauge):
    unit = 'Pa'
    label = 'Dyn.Pres.'
    def __init__(self, dl, cw):
        super(DynPresGauge, self).__init__(dl, cw)
        self.add_prop('q', 'v.dynamicPressure')
        self.warn = False
    def draw(self):
        dyn_pres = self.get('q')
        super(DynPresGauge, self).draw(dyn_pres)
        col = 3
        if dyn_pres > 40000:
            col = 2
        if dyn_pres > 80000:
            col = 1
        self.chgat(0, self.width, curses.color_pair(col))
        if dyn_pres > 40000:
            if not self.warn:
                self.warn = True
                return 'High dynamic pressure'
        else:
            self.warn = False

class GeeGauge(OneLineGauge):
    unit = 'g'
    label = 'g-Force'
    def __init__(self, dl, cw):
        super(GeeGauge, self).__init__(dl, cw)
        self.add_prop('g', 'v.geeForce')
        self.warn = False
    def draw(self):
        super(GeeGauge, self).draw()
        gee = self.get('g')
        width = self.width - len(self.label) - len(self.unit) - 1
        prec = min(3, width - 3)
        self.addstr('%s:%+*.*f%s'%(self.label, width, prec, gee, self.unit))
        col = 3
        if gee > 6 or gee < 0:
            col = 2
        if gee > 10 or gee < -3:
            col = 1
        self.chgat(0, self.width, curses.color_pair(col))
        if gee > 6 or gee < -3:
            if not self.warn:
                self.warn = True
                return 'High g forces'
        else:
            self.warn = False

class PercentageGauge(FractionGauge):
    def draw(self, n, d, s):
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
        self.addstr(text)
        self.colour(percent, 100.0)

class FuelGauge(PercentageGauge):
    def __init__(self, dl, cw, resource):
        super(FuelGauge, self).__init__(dl, cw)
        self.resource = resource
        self.add_prop('current', "r.resource[%s]"%(self.resource,))
        self.add_prop('max', "r.resourceMax[%s]"%(self.resource,))
        self.zero = False
    def draw(self):
        current = self.get('current')
        full = self.get('max')
        super(FuelGauge, self).draw(current, full, self.resource)
        if current < 0.01 and full > 0:
            if not self.zero:
                self.zero = True
                return '%s exhausted'%(self.resource,)
        else:
            self.zero = False

class AngleGauge(FractionGauge):
    label = ''
    fsd = 180
    api = None
    def __init__(self, dl, cw):
        super(AngleGauge, self).__init__(dl, cw)
        if self.api:
            self.add_prop('angle', self.api)
    @property
    def angle(self):
        return self.get('angle')
    def draw(self):
        angle = self.angle
        width = self.width - len(self.label) - 2
        prec = min(3, width - 4)
        if angle is None:
            self.addstr(self.centext('NO DATA'))
            self.chgat(0, self.width, curses.color_pair(2))
        else:
            self.addstr('%s:%+*.*f'%(self.label, width, prec, angle))
            self.colour(abs(angle), self.fsd)
        self.addch(self.width - 1, curses.ACS_DEGREE, curses.A_ALTCHARSET)

class PitchGauge(AngleGauge):
    label = 'PIT'
    fsd = 90
    api = 'n.pitch2'

class HeadingGauge(AngleGauge):
    label = 'HDG'
    fsd = 360
    api = 'n.heading2'
    def colour(self, n, d):
        super(HeadingGauge, self).colour((n + 90) % self.fsd, self.fsd)

class RollGauge(AngleGauge):
    label = 'RLL'
    api = 'n.roll2'

class LongitudeGauge(AngleGauge):
    label = 'Lng'
    api = 'v.long'
    def colour(self, *args):
        pass

class LatitudeGauge(AngleGauge):
    label = 'Lat'
    fsd = 90
    api = 'v.lat'
    def colour(self, *args):
        pass

class ClimbAngleGauge(AngleGauge):
    label = 'Elev'
    fsd = 90
    api = None
    def __init__(self, dl, cw):
        super(ClimbAngleGauge, self).__init__(dl, cw)
        self.add_prop('hs', 'v.surfaceSpeed')
        self.add_prop('vs', 'v.verticalSpeed')
    @property
    def angle(self):
        vs = self.get('vs')
        hs = self.get('hs')
        if None in (vs, hs):
            return None
        return math.degrees(math.atan2(vs, hs))

class AoAGauge(ClimbAngleGauge):
    label = 'AoA'
    fsd = 20
    api = None
    def __init__(self, dl, cw):
        super(AoAGauge, self).__init__(dl, cw)
        self.add_prop('hs', 'v.surfaceSpeed')
        self.add_prop('vs', 'v.verticalSpeed')
        self.add_prop('pit', 'n.pitch2')
    @property
    def angle(self):
        th = super(AoAGauge, self).angle
        pit = self.get('pit')
        if None in (pit, th):
            return None
        return pit - th

class Light(OneLineGauge):
    def __init__(self, dl, cw, text, api):
        super(Light, self).__init__(dl, cw)
        self.text = text
        self.add_prop('val', api)
    def draw(self):
        super(Light, self).draw()
        val = bool(int(self.get('val')))
        flag = ' ' if val else '!'
        self.addstr(self.centext(flag + self.text))
        self.chgat(0, self.width, curses.color_pair(2 if val else 0))

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
                messages.append("dpyerr in " + g.__class__.__name__)
                if fallover: raise
            except Exception as e:
                messages.append("telerr in " + g.__class__.__name__)
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
