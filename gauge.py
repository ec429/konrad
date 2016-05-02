#!/usr/bin/python

import curses
import math
import matrix
import booster
import orbit

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
    def _changeopt(self, **kwargs):
        pass
    def changeopt(self, cls, **kwargs):
        if isinstance(self, cls):
            self._changeopt(**kwargs)
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
        self.cw.noutrefresh()

class VLine(Gauge):
    def draw(self):
        super(VLine, self).draw()
        self.cw.vline(0, 0, curses.ACS_VLINE, self.height)

class NavBall(Gauge):
    def __init__(self, dl, cw):
        super(NavBall, self).__init__(dl, cw)
        self.add_prop('pit', 'n.pitch2')
        self.add_prop('hdg', 'n.heading2')
        self.add_prop('rll', 'n.roll2')
        self.cardinals = {'N': matrix.Vector3((1, 0, 0)),
                          'S': matrix.Vector3((-1, 0, 0)),
                          'E': matrix.Vector3((0, 1, 0)),
                          'W': matrix.Vector3((0, -1, 0)),
                          'O': matrix.Vector3((0, 0, -1)),
                          'X': matrix.Vector3((0, 0, 1)),
                          }
        self.size = min(self.height * 2, self.width) - 1
        self.half_size = self.size / 2
        self.center = (self.width / 2, self.height / 2)
    def draw(self):
        self.cw.clear()
        pit = self.get('pit')
        hdg = self.get('hdg')
        rll = self.get('rll')
        if None in (pit, hdg, rll):
            return
        m_rll = matrix.RotationMatrix(0, math.radians(rll))
        m_pit = matrix.RotationMatrix(1, -math.radians(pit))
        m_hdg = matrix.RotationMatrix(2, -math.radians(hdg))
        final = m_rll * m_pit * m_hdg
        self.cw.addch(self.center[1], self.center[0], '.')
        for k, v in self.cardinals.items():
            p = final * v
            if p.data[0] >= -0.05:
                x = p.data[1] * self.half_size + self.center[0]
                y = p.data[2] * self.half_size / 2 + self.center[1]
                self.cw.addch(int(y), int(x), k)

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
    def __init__(self, dl, cw, text, centered=False):
        super(FixedLabel, self).__init__(dl, cw)
        self.text = text
        self.centered = centered
    def draw(self):
        super(FixedLabel, self).draw()
        text = self.text
        if self.centered:
            text = self.centext(text)
        self.addstr(text)

class VariableLabel(OneLineGauge):
    def __init__(self, dl, cw, d, key, centered=False):
        super(VariableLabel, self).__init__(dl, cw)
        self.d = d
        self.key = key
        self.centered = centered
    def draw(self):
        super(VariableLabel, self).draw()
        text = self.d.get(self.key, '')
        if self.centered:
            text = self.centext(text)
        self.addstr(text)

class MJMode(OneLineGauge):
    # Return codes for mj.*:
    # 0 Success
    # 1 Game paused
    # 2 Antenna unpowered
    # 3 Antenna inactive
    # 4 Antenna unreach
    # 5 No MJ part
    # (source: https://github.com/SavinaRoja/Kerminal/blob/master/kerminal/commands/mechjeb.py)
    def __init__(self, dl, cw, want):
        super(MJMode, self).__init__(dl, cw)
        self.want = want
    def draw(self):
        if 'reqm' in self.want:
            reqm = self.want['reqm']
            if reqm in self.dl.data:
                rc = self.dl.data[reqm]
                if rc:
                    self.want['mode'] = 'Error %d'%(rc,)
                del self.dl.data[reqm]
                del self.want['reqm']
        text = self.want.get('mode', '')
        self.addstr(self.centext(text))

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

class ObtPeriodGauge(OneLineGauge):
    def __init__(self, dl, cw):
        super(ObtPeriodGauge, self).__init__(dl, cw)
        self.add_prop('T', 'o.period')
    def draw(self):
        super(ObtPeriodGauge, self).draw()
        t = self.get('T')
        if t is None:
            self.addstr('LINK DOWN')
            self.chgat(0, self.width, curses.color_pair(2))
            return
        s = t % 60
        m = (t / 60) % 60
        h = (t / 3600) % 24
        d = (t / 86400)
        if t < 60:
            text = '%ds'%(t,)
        elif t < 3600:
            text = '%dm%02ds'%(t / 60, t % 60)
        elif t < 86400:
            text = '%dh%02dm%02ds'%(h, m, s)
        else:
            text = '%dd%02dh%02dm'%(d, h, m)
        label = 'Period'
        width = self.width - len(label) - 2
        self.addstr('%s: %s'%(label, text.rjust(width)[:width]))

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
                    self.chgat(green, 1, curses.color_pair(2 if filled % 2 else 0))
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
        if value is None or math.isnan(value) or math.isinf(value):
            bad = 'NO DATA'
            if width < 8:
                bad = '-'*(width - 1)
            bad = bad.rjust(width - 1)[:width - 1]
            self.addstr('%s: %s %s'%(self.label, bad, self.unit))
            self.chgat(0, self.width, curses.color_pair(2))
        else:
            self.addstr('%s: %*d%s%s'%(self.label, width - len(pfx[0]), int(value / pfx[1] + 0.5), pfx[0], self.unit))
            if self.target is not None:
                self.colour(value, self.target)

class DownrangeGauge(SIGauge):
    unit = 'm'
    label = 'Downrange'
    def __init__(self, dl, cw, body, init_lat=None, init_long=None):
        super(DownrangeGauge, self).__init__(dl, cw)
        self.add_prop('lat', 'v.lat')
        self.add_prop('lon', 'v.long')
        self.add_prop('brad', 'b.radius[%d]'%(body,))
        self.init_lat = init_lat
        self.init_long = init_long
    def draw(self):
        lat = self.get('lat')
        lon = self.get('lon')
        brad = self.get('brad')
        if self.init_lat is None:
            self.init_lat = lat
        if self.init_long is None:
            self.init_long = lon
        if None in (lat, lon, self.init_lat, self.init_long, brad):
            d = None
        else:
            # https://en.wikipedia.org/wiki/Great-circle_distance#Formulas
            phi1 = math.radians(self.init_lat)
            lbd1 = math.radians(self.init_long)
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
        if None in (alt, atm_top):
            return
        if alt > atm_top:
            if not self.vac:
                self.vac = True
                return 'Clear of atmosphere'
        else:
            if self.vac:
                self.vac = False
                return 'Entered atmosphere'

class TerrainAltitudeGauge(SIGauge):
    unit = 'm'
    label = 'Height'
    def __init__(self, dl, cw, ground_map):
        super(TerrainAltitudeGauge, self).__init__(dl, cw)
        self.ground_map = ground_map
        self.add_prop('alt', 'v.altitude')
        self.add_prop('lat', 'v.lat')
        self.add_prop('lon', 'v.long')
    def draw(self):
        alt = self.get('alt')
        lat = self.get('lat')
        lon = self.get('lon')
        if None in (alt, lat, lon):
            alt = None
        else:
            mlat = int(round(lat * 2))
            mlon = int(round(lon * 2)) % 720
            if mlon >= 360: mlon -= 720
            elif mlon < -360: mlon += 720
            alt -= self.ground_map[mlon][mlat]
        super(TerrainAltitudeGauge, self).draw(alt)

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
        if None in (peri, atm_top): return
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
    mode = 0
    def __init__(self, dl, cw, body, target_alt=None, target_apo=None, target_peri=None):
        self.body = body
        super(ObtVelocityGauge, self).__init__(dl, cw, None)
        self.target_alt = target_alt
        self.target_apo = target_apo
        self.target_peri = target_peri
        if None not in (self.target_apo, self.target_peri):
            self.mode = 1
            self.add_prop('alt', 'v.altitude')
        elif self.target_alt is not None:
            self.mode = 2
        self.add_prop('orbV', 'v.orbitalVelocity')
        self.add_prop('brad', orbit.ParentBody.rad_api(self.body))
        self.add_prop('bgm', orbit.ParentBody.gm_api(self.body))
    def draw(self):
        alt = self.get('alt')
        brad = self.get('brad')
        bgm = self.get('bgm')
        if None in (brad, bgm):
            self.target = None
        elif self.mode == 1:
            if alt is not None:
                self.target = orbit.ParentBody(brad, bgm).vellip(self.target_peri, self.target_apo, alt)
            else:
                self.target = None
        elif self.mode == 2:
            self.target = orbit.ParentBody(brad, bdm).vcirc(self.target_alt)
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
        if dyn_pres > 40000 or dyn_pres is None:
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
        if gee is None:
            self.addstr(self.centext('NO DATA'))
            self.chgat(0, self.width, curses.color_pair(2))
            return
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
        super(PercentageGauge, self).draw()
        if d is None or d < 0 or n is None:
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
        if None in (current, full):
            return
        if current < 0.01 and full > 0:
            if not self.zero:
                self.zero = True
                return '%s exhausted'%(self.resource,)
        else:
            self.zero = False

class ThrottleGauge(PercentageGauge):
    def __init__(self, dl, cw):
        super(ThrottleGauge, self).__init__(dl, cw)
        self.add_prop('throttle', "f.throttle")
    def draw(self):
        throttle = self.get('throttle')
        super(ThrottleGauge, self).draw(throttle, 1.0, "Throttle")

class AngleGauge(FractionGauge):
    label = ''
    fsd = 180
    api = None
    def __init__(self, dl, cw, want=None):
        super(AngleGauge, self).__init__(dl, cw)
        self.want = want
        if self.api and (self.want is None):
            self.add_prop('angle', self.api)
    @property
    def angle(self):
        if self.want is None:
            return self.get('angle')
        return self.want.get(self.label)
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

class InclinationGauge(AngleGauge):
    label = 'Inclination'
    fsd = None
    api = 'o.inclination'
    def colour(self, *args):
        pass

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
    def __init__(self, dl, cw, retro=False):
        super(AoAGauge, self).__init__(dl, cw)
        self.add_prop('hs', 'v.surfaceSpeed')
        self.add_prop('vs', 'v.verticalSpeed')
        self.add_prop('pit', 'n.pitch2')
        self.retro = retro
    def _changeopt(self, **kwargs):
        if 'retro' in kwargs:
            self.retro = kwargs['retro']
    @property
    def angle(self):
        th = super(AoAGauge, self).angle
        pit = self.get('pit')
        if None in (pit, th):
            return None
        return pit + th if self.retro else pit - th

class Light(OneLineGauge):
    def __init__(self, dl, cw, text, api):
        super(Light, self).__init__(dl, cw)
        self.text = text
        self.add_prop('val', api)
    def draw(self):
        super(Light, self).draw()
        raw = self.get('val')
        if raw is None:
            val = True
            flag = '?'
            col = 2
        else:
            val = bool(int(raw))
            flag = ' ' if val else '!'
            col = val * 3
        self.addstr(self.centext(flag + self.text))
        self.chgat(0, self.width, curses.color_pair(col))

class UpdateBooster(Gauge):
    def __init__(self, dl, cw, booster):
        super(UpdateBooster, self).__init__(dl, cw)
        self.booster = booster
        for p in self.booster.all_props:
            self.add_prop(p, 'r.resource[%s]'%(p,))
            self.add_prop('%s_max'%(p,), 'r.resourceMax[%s]'%(p,))
    def draw(self):
        # we don't actually draw anything...
        # we just do some calculations!
        has_staged = False
        for p in self.booster.all_props:
            mx = self.get('%s_max'%(p,))
            if mx is None: continue
            if mx < self.booster.stages[0].prop_all(p) * 0.99:
                has_staged = True
        if has_staged:
            self.booster.stage()
        for p in self.booster.all_props:
            amt = self.get(p)
            if amt is None: continue
            for s in reversed(self.booster.stages):
                prop = s.this_prop(p)
                if prop is not None:
                    prop.filled = min(amt, prop.volume)
                    amt -= prop.filled
        if has_staged:
            return "Booster staged"

class DeltaVGauge(SIGauge):
    unit = 'm/s'
    label = 'Vac.DeltaV'
    def __init__(self, dl, cw, booster):
        super(DeltaVGauge, self).__init__(dl, cw)
        self.booster = booster
    def draw(self):
        super(DeltaVGauge, self).draw(self.booster.deltaV)

class StagesGauge(Gauge):
    def __init__(self, dl, cw, booster):
        super(StagesGauge, self).__init__(dl, cw)
        self.booster = booster
        self.add_prop('throttle', 'f.throttle')
    def draw(self):
        self.cw.clear()
        throttle = self.get('throttle')
        for i,s in enumerate(self.booster.stages):
            if i * 2 < self.height:
                header = 'Stage %d [%s]'%(i + 1, ', '.join(s.propnames))
                self.cw.addnstr(i * 2, 0, header, self.width)
                deltav = 'Vac.dV: %dm/s'%(s.deltaV,)
                bt = s.burn_time(throttle)
                if bt is None or self.width < 28:
                    row = deltav
                else:
                    mins = bt / 60
                    secs = bt % 60
                    bts = 'BT %02d:%02d'%(mins, secs)
                    row = deltav.ljust(20) + bts
                self.cw.addnstr(i * 2 + 1, 0, row, self.width)

class TWRGauge(OneLineGauge):
    label = 'TWR'
    def __init__(self, dl, cw, booster, body):
        super(TWRGauge, self).__init__(dl, cw)
        self.booster = booster
        self.add_prop('throttle', 'f.throttle')
        self.add_prop('alt', 'v.altitude')
        self.add_prop('brad', "b.radius[%d]"%(body,))
        self.add_prop('bgm', "b.o.gravParameter[%d]"%(body,))
    def draw(self):
        super(TWRGauge, self).draw()
        throttle = self.get('throttle')
        alt = self.get('alt')
        brad = self.get('brad')
        bgm = self.get('bgm')
        twr = self.booster.twr
        if None in (throttle, twr):
            tmr = None
        else:
            tmr = twr * self.booster.convert_throttle(throttle)
        if None in (alt, brad, bgm):
            g = None
        else:
            g = bgm / (alt + brad)**2
        if None in (tmr, g):
            twr = None
        else:
            twr = tmr / float(g)
        if twr is None:
            self.addstr(self.centext('NO DATA'))
            self.chgat(0, self.width, curses.color_pair(2))
            return
        else:
            width = self.width - len(self.label)  - 1
            prec = min(3, width - 3)
            self.addstr('%s:%+*.*f'%(self.label, width, prec, twr))

class UpdateRocketSim(Gauge):
    def __init__(self, dl, cw, body, booster, use_throttle, use_orbital, sim):
        super(UpdateRocketSim, self).__init__(dl, cw)
        self.booster = booster
        # Assumes you already have an UpdateBooster keeping booster updated!
        self.sim = sim
        self.use_throttle = use_throttle
        if use_orbital:
            self.add_prop('hs', 'v.orbitalVelocity')
        else:
            self.add_prop('hs', 'v.surfaceSpeed')
        self.add_prop('vs', 'v.verticalSpeed')
        self.add_prop('alt', 'v.altitude')
        if use_throttle:
            self.add_prop('throttle', 'f.throttle')
        self.add_prop('pit', 'n.pitch2')
        self.add_prop('hdg', 'n.heading2')
        self.add_prop('lat', 'v.lat')
        self.add_prop('lon', 'v.long')
        self.add_prop('brad', orbit.ParentBody.rad_api(body))
        self.add_prop('bgm', orbit.ParentBody.gm_api(body))
    def draw(self):
        # we don't actually draw anything...
        # we just do some calculations!
        hs = self.get('hs')
        vs = self.get('vs')
        alt = self.get('alt')
        if self.use_throttle:
            throttle = self.get('throttle')
        else:
            throttle = 1.0
        pit = self.get('pit')
        hdg = self.get('hdg')
        lat = self.get('lat')
        lon = self.get('lon')
        brad = self.get('brad')
        bgm = self.get('bgm')
        if None in (hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm):
            self.sim.has_data = False
        else:
            self.sim.simulate(self.booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm)

class RSTime(OneLineGauge):
    def __init__(self, dl, cw, key, sim):
        super(RSTime, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        super(RSTime, self).draw()
        if self.sim.has_data:
            if self.key in self.sim.data:
                t = self.sim.data[self.key]['time']
                self.addstr('T:%*ds'%(self.olg_width - 3, t))
                col = 0
                if self.key in 'hv':
                    if 's' in self.sim.data and self.sim.data['s']['time'] < t:
                        col = 1
                    elif self.key == 'h' and 'v' in self.sim.data and self.sim.data['v']['time'] < t:
                        col = 1
                    else:
                        col = 3
                elif self.key == 'b':
                    if 's' in self.sim.data and self.sim.data['s']['time'] > t:
                        col = 1
                    elif 'o' in self.sim.data and self.sim.data['o']['time'] > t:
                        col = 1
                    else:
                        col = 3
            else:
                self.addstr('T'+'-'*(self.olg_width - 1))
                col = 1
                if self.key == 's':
                    col = 2
                elif self.key == 'b':
                    col = 3
        else:
            self.addstr('T'+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSAlt(SIGauge):
    unit = 'm'
    label = 'Y'
    def __init__(self, dl, cw, key, sim):
        super(RSAlt, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        if self.sim.has_data:
            if self.key in self.sim.data:
                d = self.sim.data[self.key]
                alt = d.get('height', d['alt'])
                super(RSAlt, self).draw(alt)
                col = 3 if alt > 0 else 1
                if self.key == 'b':
                    col = 1 if alt > 10 else 0 # TODO parametrise
            else:
                self.addstr(self.label+'-'*(self.olg_width - 1))
                col = 1
                if self.key == 'b':
                    col = 3
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSDownrange(SIGauge):
    unit = 'm'
    label = 'X'
    def __init__(self, dl, cw, key, sim):
        super(RSDownrange, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        if self.sim.has_data:
            if self.key in self.sim.data:
                x = self.sim.data[self.key]['x']
                super(RSDownrange, self).draw(x)
                col = 3
            else:
                self.addstr(self.label+'-'*(self.olg_width - 1))
                col = 1
                if self.key == 's':
                    col = 2
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSVSpeed(SIGauge):
    unit = 'm/s'
    label = 'V'
    def __init__(self, dl, cw, key, sim):
        super(RSVSpeed, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        if self.sim.has_data:
            if self.key in self.sim.data:
                vs = self.sim.data[self.key]['vs']
                super(RSVSpeed, self).draw(vs)
                col = 3
                if self.key == 'o':
                    if abs(vs) > 20: # TODO parametrise
                        col = 1
                elif vs < -8: # TODO parametrise
                    col = 1
            else:
                self.addstr(self.label+'-'*(self.olg_width - 1))
                col = 1
                if self.key == 's':
                    col = 2
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSHSpeed(SIGauge):
    unit = 'm/s'
    label = 'H'
    def __init__(self, dl, cw, key, sim):
        super(RSHSpeed, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        if self.sim.has_data:
            if self.key in self.sim.data:
                hs = self.sim.data[self.key]['hs']
                super(RSHSpeed, self).draw(hs)
                col = 3
                if self.key == 'o':
                    col = 0
                elif abs(hs) > 1: # TODO parametrise
                    col = 1
            else:
                self.addstr(self.label+'-'*(self.olg_width - 1))
                col = 1
                if self.key == 's':
                    col = 2
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSLatitude(OneLineGauge):
    param = 'lat'
    labels = 'NS'
    def __init__(self, dl, cw, key, sim):
        super(RSLatitude, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        super(RSLatitude, self).draw()
        if self.sim.has_data:
            keys = [k for k in list(self.key) if k in self.sim.data]
            if keys:
                angle = self.sim.data[keys[0]][self.param]
                label = self.labels[angle < 0]
                width = self.olg_width - 3
                prec = min(3, width - 4)
                self.addstr('%s:%+*.*f'%(label, width, prec, angle))
                col = 0
            else:
                self.addstr('-'*self.olg_width)
                col = 2
        else:
            self.addstr('-'*self.olg_width)
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))
        self.addch(self.olg_width - 1, curses.ACS_DEGREE, curses.A_ALTCHARSET)

class RSLongitude(RSLatitude):
    param = 'lon'
    labels = 'EW'

global fallover

class GaugeGroup(object):
    def __init__(self, cw, gl, title):
        self.cw = cw
        self.gl = gl
        self.title = title
    def changeopt(self, cls, **kwargs):
        for g in self.gl:
            g.changeopt(cls, **kwargs)
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
        self.cw.noutrefresh()

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
