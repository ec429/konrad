#!/usr/bin/python

import curses
import math
import matrix
import booster
import orbit
from sim import SimulationException

def initialise():
    register_colours()
    curses.nonl()
    try:
        curses.curs_set(0)
    except:
        pass

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
    def del_prop(self, name):
        if name in self.props:
            self.dl.unsubscribe(self.props[name])
            del self.props[name]
    def get(self, key, default=None):
        if key not in self.props:
            return default
        return self.dl.get(self.props[key], default)
    def getrad(self, key):
        "Like get(), but convert to radians if not None"
        v = self.get(key)
        if v is None:
            return v
        return math.radians(v)
    def put(self, key, value):
        self.dl.put(key, value)
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
        pit = self.getrad('pit')
        hdg = self.getrad('hdg')
        rll = self.getrad('rll')
        if None in (pit, hdg, rll):
            return
        m_rll = matrix.RotationMatrix(0, rll)
        m_pit = matrix.RotationMatrix(1, -pit)
        m_hdg = matrix.RotationMatrix(2, -hdg)
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

class TimeFormatterMixin(object):
    @classmethod
    def mktime(cls, t):
        t = max(int(t), 0)
        s = t % 60
        t /= 60
        m = t % 60
        t /= 60
        h = t % 24
        t /= 24
        d = t
        return (d, h, m, s)
    @classmethod
    def fmt_time(cls, t, elts):
        """Return time formatted with at most elts elements"""
        d,h,m,s = cls.mktime(abs(t))
        parts = [(d, 'd'), (h, 'h'), (m, ':'), (s, None)]
        while len(parts) > elts and not parts[0][0]:
            parts = parts[1:]
        ret = ""
        for i,p in enumerate(parts):
            if i >= elts: break
            ret += '%02d'%(p[0],)
            if i + 1 < elts and p[1] is not None:
                ret += p[1]
        if t < 0:
            ret = '-' + ret
        return ret

class TimeGauge(OneLineGauge, TimeFormatterMixin):
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
        self.addstr('T+%s'%(self.fmt_time(t, 3)))

class TimeToApGauge(OneLineGauge, TimeFormatterMixin):
    label = "ttAp"
    def __init__(self, dl, cw):
        super(TimeToApGauge, self).__init__(dl, cw)
        self.add_prop('ttAp', 'o.timeToAp')
    def draw(self):
        super(TimeToApGauge, self).draw()
        t = self.get('ttAp')
        if t is None:
            self.addstr('%s: NO DATA'%(self.label,))
            self.chgat(0, self.width, curses.color_pair(2))
            return
        elts = (self.width-1-len(self.label))/3
        self.addstr('%s: %s'%(self.label, self.fmt_time(t, elts)))

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

class BodyNameGauge(OneLineGauge):
    def __init__(self, dl, cw, body):
        super(BodyNameGauge, self).__init__(dl, cw)
        self.add_prop('name', 'b.name[%d]'%(body,))
    def draw(self):
        super(BodyNameGauge, self).draw()
        name = self.get('name')
        if name is None:
            self.addstr(self.centext("LINK DOWN"))
            self.chgat(0, self.width, curses.color_pair(2))
            return
        self.addstr(self.centext(name))

class BodyGauge(OneLineGauge):
    def __init__(self, dl, cw, body):
        super(BodyGauge, self).__init__(dl, cw)
        self.add_prop('name', 'b.name[%d]'%(body,))
        self.add_prop('body', 'v.body')
        self.warn = False
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.del_prop('name')
            self.add_prop('name', 'b.name[%d]'%(kwargs['body'],))
        super(BodyGauge, self)._changeopt(**kwargs)
    def draw(self):
        super(BodyGauge, self).draw()
        name = self.get('name')
        if name is None:
            self.addstr(self.centext("LINK DOWN"))
            self.chgat(0, self.width, curses.color_pair(2))
            return
        body = self.get('body')
        wrong = body != name
        if body in self.dl.body_ids:
            self.put('body_id', self.dl.body_ids[body])
        else:
            self.put('body_id', None)
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
        if self.fracmode <= 0:
            # Fixed colour
            self.chgat(0, self.width, curses.color_pair(-fracmode))
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
        sgnval = -1 if sgn else 1
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
            self.addstr('%s: %*d%s%s'%(self.label, width - len(pfx[0]), int(value / pfx[1] + 0.5*sgnval), pfx[0], self.unit))
            if self.target is not None:
                self.colour(value, self.target)

class DownrangeGauge(SIGauge):
    unit = 'm'
    label = 'Downrange'
    def __init__(self, dl, cw, body, init_lat=None, init_long=None):
        super(DownrangeGauge, self).__init__(dl, cw)
        self.add_prop('lat', 'v.lat')
        self.add_prop('lon', 'v.long')
        self.add_prop('brad', orbit.ParentBody.rad_api(body))
        self.init_lat = init_lat
        self.init_long = init_long
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.del_prop('brad')
            self.add_prop('brad', orbit.ParentBody.rad_api(kwargs['body']))
        super(DownrangeGauge, self)._changeopt(**kwargs)
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
        self.put('downrange.d', d)
        super(DownrangeGauge, self).draw(d)

class AltitudeGauge(SIGauge):
    unit = 'm'
    label = 'Altitude'
    def __init__(self, dl, cw, body, target=None):
        super(AltitudeGauge, self).__init__(dl, cw, target)
        self.add_prop('alt', 'v.altitude')
        self.add_prop('atm_top', 'b.maxAtmosphere[%d]'%(body,))
        self.vac = False
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.del_prop('atm_top')
            self.add_prop('atm_top', 'b.maxAtmosphere[%d]'%(kwargs['body'],))
        super(AltitudeGauge, self)._changeopt(**kwargs)
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

class DeltaHGauge(SIGauge):
    unit = 'm'
    label = 'DeltaH'
    def __init__(self, dl, cw, ground_map, ground_alt=None):
        super(DeltaHGauge, self).__init__(dl, cw)
        self.ground_map = ground_map
        self.ground_alt = ground_alt
        self.add_prop('lat', 'v.lat')
        self.add_prop('lon', 'v.long')
        self.add_prop('th', 'v.terrainHeight')
        self.fracmode = 0
    def draw(self):
        lat = self.get('lat')
        lon = self.get('lon')
        th = self.get('th')
        if None in (lat, lon, self.ground_map):
            ground_alt = self.ground_alt
        else:
            mlat = int(round(lat * 2))
            mlon = int(round(lon * 2)) % 720
            if mlon >= 360: mlon -= 720
            elif mlon < -360: mlon += 720
            ground_alt = self.ground_map[mlon][mlat]
        if None in (ground_alt, th):
            dh = None
        else:
            dh = th - ground_alt
        super(DeltaHGauge, self).draw(dh)

class TerrainAltitudeGauge(SIGauge):
    unit = 'm'
    label = 'Height'
    def __init__(self, dl, cw):
        super(TerrainAltitudeGauge, self).__init__(dl, cw)
        self.add_prop('alt', 'v.altitude')
        self.add_prop('th', 'v.terrainHeight')
    def draw(self):
        alt = self.get('alt')
        th = self.get('th')
        self.fracmode = 0
        if None in (alt, th):
            alt = None
        else:
            alt = alt - th
        super(TerrainAltitudeGauge, self).draw(alt)

class LandingPointGauge(SIGauge):
    unit = 'm'
    label = 'ILS'
    def __init__(self, dl, cw):
        super(LandingPointGauge, self).__init__(dl, cw)
        self.add_prop('alt', 'v.altitude')
        self.add_prop('th', 'v.terrainHeight')
        self.add_prop('dr', 'downrange.d')
        self.add_prop('hs', 'v.surfaceSpeed')
        self.add_prop('vs', 'v.verticalSpeed')
    def draw(self):
        self.fracmode = 0
        alt = self.get('alt')
        th = self.get('th')
        dr = self.get('dr')
        hs = self.get('hs')
        vs = self.get('vs')
        if None in (alt, dr, th, vs, hs) or vs >= 0:
            lp = None
        else:
            alt -= th
            lt = -(alt / vs)
            lp = dr - lt * hs # assumes inward radial heading
        super(LandingPointGauge, self).draw(lp)

class PeriapsisGauge(SIGauge):
    unit = 'm'
    label = 'Periapsis'
    def __init__(self, dl, cw, body, target=None):
        super(PeriapsisGauge, self).__init__(dl, cw, target)
        self.add_prop('peri', 'o.PeA')
        self.add_prop('atm_top', 'b.maxAtmosphere[%d]'%(body,))
        self.orb = False
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.del_prop('atm_top')
            self.add_prop('atm_top', 'b.maxAtmosphere[%d]'%(kwargs['body'],))
        super(PeriapsisGauge, self)._changeopt(**kwargs)
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
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.body = kwargs['body']
            self.del_prop('brad')
            self.add_prop('brad', orbit.ParentBody.rad_api(self.body))
            self.del_prop('bgm')
            self.add_prop('bgm', orbit.ParentBody.gm_api(self.body))
        super(ObtVelocityGauge, self)._changeopt(**kwargs)
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
            self.target = orbit.ParentBody(brad, bgm).vcirc(self.target_alt)
        else:
            self.target = None
        super(ObtVelocityGauge, self).draw(self.get('orbV'))

class HSpeedGauge(SIGauge):
    unit = 'm/s'
    label = 'HSpd'
    def __init__(self, dl, cw):
        super(HSpeedGauge, self).__init__(dl, cw)
        self.add_prop('hs', 'v.surfaceSpeed')
    def draw(self):
        super(HSpeedGauge, self).draw(self.get('hs'))

class VSpeedGauge(SIGauge):
    unit = 'm/s'
    label = 'VSpd'
    def __init__(self, dl, cw):
        super(VSpeedGauge, self).__init__(dl, cw)
        self.add_prop('vs', 'v.verticalSpeed')
    def draw(self):
        super(VSpeedGauge, self).draw(self.get('vs'))

class SrfSpeedGauge(SIGauge):
    unit = 'm/s'
    label = 'Speed'
    def __init__(self, dl, cw):
        super(SrfSpeedGauge, self).__init__(dl, cw)
        self.add_prop('spd', 'v.surfaceVelocity')
    def draw(self):
        super(SrfSpeedGauge, self).draw(self.get('spd'))

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

class HeatingGauge(SIGauge):
    """A figure vaguely relevant to re-entry heating.

    Heating Coefficient is w = 2 * v * a
    Neglecting changes in PE,
    d(KE)/dt = d(mv^2)/dt = 2mv(dv/dt) = 2mva
    power / mass = 2va
    """
    unit = 'W/kg'
    label = 'Pwr.Coeff'
    def __init__(self, dl, cw):
        super(HeatingGauge, self).__init__(dl, cw)
        self.add_prop('gee', 'v.geeForce')
        self.add_prop('spd', 'v.surfaceVelocity')
    def draw(self):
        spd = self.get('spd')
        gee = self.get('gee')
        if None in [spd, gee]:
            w = None
        else:
            w = 2 * spd * gee * 9.80665 # 2 * velocity * acceleration
        super(HeatingGauge, self).draw(w)
        col = 3
        if w > 200000 or w is None:
            col = 2
        if w > 600000:
            col = 1
        self.chgat(0, self.width, curses.color_pair(col))

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
    def draw(self, n, d, s, zna=False):
        super(PercentageGauge, self).draw()
        if d is None or d < 0 or n is None:
            if zna: # "Zero is N/A"
                if self.width < 7:
                    text = "N/A"
                else:
                    text = "N/A: " + s
                self.addstr(self.centext(text))
                self.chgat(0, self.width, curses.color_pair(0)|curses.A_BOLD)
            else:
                self.addstr(self.centext("NO DATA"))
                self.chgat(0, self.width, curses.color_pair(2))
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
        super(FuelGauge, self).draw(current, full, self.resource, zna=True)
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
        if throttle == 2:
            throttle = None
        super(ThrottleGauge, self).draw(throttle, 1.0, "Throttle")

class AngleGauge(FractionGauge):
    label = ''
    fsd = 180
    api = None
    signed = True
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
        if angle in (None, u'NaN'):
            self.addstr(self.centext('NO DATA'))
            self.chgat(0, self.width, curses.color_pair(2))
        else:
            if angle < (-180 if self.signed else 0):
                angle += 360
            self.addstr('%s:%+*.*f'%(self.label, width, prec, angle))
            self.colour(abs(angle), self.fsd)
        self.addch(self.width - 1, curses.ACS_DEGREE, curses.A_ALTCHARSET)

class PhaseAngleGauge(AngleGauge):
    label = 'Q'
    fsd = None
    def __init__(self, dl, cw, tgt):
        self.api = 'b.o.phaseAngle[%d]'%(tgt,)
        super(PhaseAngleGauge, self).__init__(dl, cw)
    def colour(self, *args):
        pass

class RelIncGauge(AngleGauge):
    label = 'RI'
    fsd = 5
    def __init__(self, dl, cw, tgt):
        super(RelIncGauge, self).__init__(dl, cw)
        self.add_prop('inc', 'o.inclination')
        self.add_prop('lan', 'o.lan')
        if tgt is None:
            self.add_prop('inc', 'tar.o.inclination')
            self.add_prop('lan', 'tar.o.lan')
        else:
            self.add_prop('tinc', 'b.o.inclination[%d]'%(tgt,))
            self.add_prop('tlan', 'b.o.lan[%d]'%(tgt,))
    @property
    def angle(self):
        inc = self.getrad('inc')
        lan = self.getrad('lan')
        tinc = self.getrad('tinc')
        tlan = self.getrad('tlan')
        if None in (inc, lan, tinc, tlan):
            return None
        w = (math.sin(inc) * math.cos(lan), math.sin(inc) * math.sin(lan), math.cos(inc))
        z = (math.sin(tinc) * math.cos(tlan), math.sin(tinc) * math.sin(tlan), math.cos(tinc))
        dot = sum(wi*zi for wi,zi in zip(w, z))
        theta = math.acos(dot)
        return math.degrees(theta)

class RelLanGauge(AngleGauge):
    label = 'RL'
    fsd = 5
    def __init__(self, dl, cw, tgt):
        super(RelLanGauge, self).__init__(dl, cw)
        self.add_prop('lan', 'o.lan')
        if tgt is None:
            self.add_prop('lan', 'tar.o.lan')
        else:
            self.add_prop('tlan', 'b.o.lan[%d]'%(tgt,))
    @property
    def angle(self):
        lan = self.get('lan')
        tlan = self.get('tlan')
        if None in (lan, tlan):
            return None
        return tlan - lan

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

class BearingGauge(AngleGauge):
    label = 'VOR'
    api = None
    signed = False
    def __init__(self, dl, cw, body, init_lat=None, init_long=None):
        super(BearingGauge, self).__init__(dl, cw)
        self.add_prop('lat', 'v.lat')
        self.add_prop('lon', 'v.long')
        self.init_lat = init_lat
        self.init_long = init_long
    @property
    def angle(self):
        lat = self.get('lat')
        lon = self.get('lon')
        if self.init_lat is None:
            self.init_lat = lat
        if self.init_long is None:
            self.init_long = lon
        if None in (lat, lon, self.init_lat, self.init_long):
            return
        # http://www.movable-type.co.uk/scripts/latlong.html
        phi1 = math.radians(lat)
        lbd1 = math.radians(lon)
        phi2 = math.radians(self.init_lat)
        lbd2 = math.radians(self.init_long)
        dlbd = lbd2 - lbd1
        bear = math.atan2(math.sin(dlbd) * math.cos(phi2), math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlbd))
        return math.degrees(bear)

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

class AngleRateGauge(OneLineGauge):
    def __init__(self, dl, cw):
        super(AngleRateGauge, self).__init__(dl, cw)
        self.add_prop('T', 'v.missionTime')
        self.add_prop('angle', self.api)
        self.old = (None, None)
    @property
    def rate(self):
        t = self.get('T')
        a = self.get('angle')
        ot, oa = self.old
        self.old = (t, a)
        if None in (t, a, ot, oa):
            return None
        dt = t - ot
        da = a - oa
        if dt <= 0:
            return None
        if da < -180:
            da += 380
        if da > 180:
            da -= 360
        return da / dt
    def draw(self):
        super(AngleRateGauge, self).draw()
        rate = self.rate
        if rate is None:
            self.addstr(self.centext('NO DATA'))
            self.chgat(0, self.width, curses.color_pair(2))
        else:
            width = self.width - len(self.label) - 3
            prec = width - 2
            self.addstr('%s:%+*.*f'%(self.label, width, prec, rate))
        self.addch(self.width - 1, curses.ACS_DEGREE, curses.A_ALTCHARSET)

class PitchRateGauge(AngleRateGauge):
    label = 'P.R'
    api = 'n.pitch2'

class HeadingRateGauge(AngleRateGauge):
    label = 'H.R'
    api = 'n.heading2'

class RollRateGauge(AngleRateGauge):
    label = 'R.R'
    api = 'n.roll2'

class BaseLight(OneLineGauge):
    value = False
    def __init__(self, dl, cw, text):
        super(BaseLight, self).__init__(dl, cw)
        self.text = text
    def draw(self):
        super(BaseLight, self).draw()
        raw = self.value
        if raw is None:
            flag = '?'
            col = 2
        else:
            val = bool(int(raw))
            flag = ' ' if val else '!'
            col = val * 3
        self.addstr(self.centext(flag + self.text))
        self.chgat(0, self.width, curses.color_pair(col))

class Light(BaseLight):
    def __init__(self, dl, cw, text, api):
        super(Light, self).__init__(dl, cw, text)
        self.add_prop('val', api)
    @property
    def value(self):
        v = self.get('val')
        if v == 2:
            return None
        return v

class ObtHeadingGauge(AngleGauge):
    label = 'ObtHeading'
    def __init__(self, dl, cw, body):
        super(ObtHeadingGauge, self).__init__(dl, cw)
        self.add_prop('brad', orbit.ParentBody.rad_api(body))
        self.add_prop('bgm', orbit.ParentBody.gm_api(body))
        self.add_prop('inc', 'o.inclination')
        self.add_prop('lan', 'o.lan')
        self.add_prop('tan', 'o.trueAnomaly')
        self.add_prop('ape', 'o.argumentOfPeriapsis')
        self.add_prop('ecc', 'o.eccentricity')
        self.add_prop('sma', 'o.sma')
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.del_prop('brad')
            self.add_prop('brad', orbit.ParentBody.rad_api(kwargs['body']))
            self.del_prop('bgm')
            self.add_prop('bgm', orbit.ParentBody.gm_api(kwargs['body']))
        super(ObtHeadingGauge, self)._changeopt(**kwargs)
    @property
    def angle(self):
        brad = self.get('brad')
        bgm = self.get('bgm')
        inc = self.getrad('inc')
        lan = self.getrad('lan')
        tan = self.getrad('tan')
        ape = self.getrad('ape')
        ecc = self.get('ecc')
        sma = self.get('sma')
        if None in (brad, bgm, inc, lan, tan, ape, ecc, sma):
            return None
        # 3D position & velocity
        pb = orbit.ParentBody(brad, bgm)
        ean = orbit.ean_from_tan(tan, ecc)
        r, v = pb.compute_3d_vector(sma, ecc, ean, ape, inc, lan)
        # compute lat & long
        rhat = r.hat
        vhat = v.hat
        lon = math.atan2(rhat.y, rhat.x)
        lat = math.asin(rhat.z)
        # conversion to local co-ordinates
        iM = matrix.RotationMatrix(1, lat) * matrix.RotationMatrix(2, -lon)
        lv = iM * vhat
        oh = math.atan2(lv.y, lv.z)
        return math.degrees(oh)

class UpdateBooster(Gauge):
    def __init__(self, dl, cw, bstr):
        super(UpdateBooster, self).__init__(dl, cw)
        self.booster = bstr
        self.init_booster = booster.Booster.clone(bstr)
        self.reset()
        if self.booster is None: return
        for p in self.booster.all_props:
            self.add_prop(p, 'r.resource[%s]'%(p,))
            self.add_prop('%s_max'%(p,), 'r.resourceMax[%s]'%(p,))
    def reset(self):
        if self.booster is not None:
            self.booster.stages = booster.Booster.clone(self.init_booster).stages
    def draw(self):
        # we don't actually draw anything...
        # we just do some calculations!
        if self.booster is None:
            return
        has_staged = False
        for p in self.booster.all_props:
            mx = self.get('%s_max'%(p,))
            if mx is None: continue
            if mx < self.booster.stages[0].prop_all(p) * 0.99:
                has_staged = p
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
            return "Booster staged (%s)"%(has_staged,)

class DeltaVGauge(SIGauge):
    unit = 'm/s'
    label = 'Vac.DeltaV'
    def __init__(self, dl, cw, booster):
        super(DeltaVGauge, self).__init__(dl, cw)
        self.booster = booster
    def draw(self):
        if self.booster is None:
            return
        super(DeltaVGauge, self).draw(self.booster.deltaV)

class StagesGauge(Gauge, TimeFormatterMixin):
    def __init__(self, dl, cw, booster):
        super(StagesGauge, self).__init__(dl, cw)
        self.booster = booster
        self.add_prop('throttle', 'f.throttle')
    def draw(self):
        self.cw.clear()
        if self.booster is None:
            return
        throttle = self.get('throttle')
        for i,s in enumerate(self.booster.stages):
            if i * 2 < self.height:
                header = 'Stage %d [%s]'%(i + 1, ', '.join(s.propnames))
                self.cw.addnstr(i * 2, 0, header, self.width)
                deltav = 'Vac.dV: %dm/s'%(s.deltaV,)
                bt = s.burn_time(throttle or 1.0)
                if bt is None or self.width < 28:
                    row = deltav
                else:
                    bts = 'BT %s'%(self.fmt_time(bt, 2),)
                    row = deltav.ljust(20) + bts
                try:
                    self.cw.addnstr(i * 2 + 1, 0, row, self.width)
                except curses.error:
                    # for some reason addnstr doesn't like the bottom-right cell in a
                    # window.  maybe it's trying to move the cursor past it...
                    pass

class TWRGauge(OneLineGauge):
    label = 'TWR'
    def __init__(self, dl, cw, booster, body, use_throttle=1):
        super(TWRGauge, self).__init__(dl, cw)
        self.booster = booster
        self.use_throttle = use_throttle
        self.add_prop('throttle', 'f.throttle')
        self.add_prop('alt', 'v.altitude')
        self.add_prop('brad', orbit.ParentBody.rad_api(body))
        self.add_prop('bgm', orbit.ParentBody.gm_api(body))
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.del_prop('brad')
            self.add_prop('brad', orbit.ParentBody.rad_api(kwargs['body']))
            self.del_prop('bgm')
            self.add_prop('bgm', orbit.ParentBody.gm_api(kwargs['body']))
        super(TWRGauge, self)._changeopt(**kwargs)
    def draw(self):
        super(TWRGauge, self).draw()
        if self.use_throttle:
            throttle = self.get('throttle')
            if throttle == 2:
                throttle = None
        else:
            throttle = 1.0
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
        self.use_orbital = use_orbital
        if self.use_orbital:
            self.add_prop('ov', 'v.orbitalVelocity')
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
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.del_prop('brad')
            self.add_prop('brad', orbit.ParentBody.rad_api(kwargs['body']))
            self.del_prop('bgm')
            self.add_prop('bgm', orbit.ParentBody.gm_api(kwargs['body']))
        super(UpdateRocketSim, self)._changeopt(**kwargs)
    def draw(self):
        # we don't actually draw anything...
        # we just do some calculations!
        vs = self.get('vs')
        if self.use_orbital:
            # Compute hs by pythagoras
            ov = self.get('ov')
            if None in (vs, ov):
                hs = None
            else:
                hs2 = ov*ov - vs*vs
                if hs2 < 0:
                    hs = None
                else:
                    hs = math.sqrt(hs2)
        else:
            hs = self.get('hs')
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
            self.sim.data = {}
        else:
            self.sim.simulate(self.booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm)

class UpdateRocketSim3D(Gauge):
    def __init__(self, dl, cw, body, booster, use_throttle, sim, want=None):
        super(UpdateRocketSim3D, self).__init__(dl, cw)
        self.booster = booster
        # Assumes you already have an UpdateBooster keeping booster updated!
        self.sim = sim
        self.use_throttle = use_throttle
        if use_throttle:
            self.add_prop('throttle', 'f.throttle')
        self.want = want
        self.add_prop('pit', 'n.pitch2')
        self.add_prop('hdg', 'n.heading2')
        self.add_prop('brad', orbit.ParentBody.rad_api(body))
        self.add_prop('bgm', orbit.ParentBody.gm_api(body))
        self.add_prop('inc', 'o.inclination')
        self.add_prop('lan', 'o.lan')
        self.add_prop('tan', 'o.trueAnomaly')
        self.add_prop('ape', 'o.argumentOfPeriapsis')
        self.add_prop('ecc', 'o.eccentricity')
        self.add_prop('sma', 'o.sma')
        self.add_prop('UT', 't.universalTime')
    def _changeopt(self, **kwargs):
        if 'body' in kwargs:
            self.del_prop('brad')
            self.add_prop('brad', orbit.ParentBody.rad_api(kwargs['body']))
            self.del_prop('bgm')
            self.add_prop('bgm', orbit.ParentBody.gm_api(kwargs['body']))
        super(UpdateRocketSim3D, self)._changeopt(**kwargs)
    def draw(self):
        self.sim.data = {}
        UT = self.get('UT')
        if UT is None:
            return
        self.sim.UT = UT
        if self.use_throttle:
            throttle = self.get('throttle')
        else:
            throttle = 1.0
        if self.want is not None and self.sim.mode == self.sim.MODE_FIXED:
            pit = self.want.get('PIT')
            if pit is not None:
                pit = math.radians(pit)
            hdg = self.want.get('HDG')
            if hdg is not None:
                hdg = math.radians(hdg)
        else:
            pit = self.getrad('pit')
            hdg = self.getrad('hdg')
        brad = self.get('brad')
        bgm = self.get('bgm')
        inc = self.getrad('inc')
        lan = self.getrad('lan')
        tan = self.getrad('tan')
        ape = self.getrad('ape')
        ecc = self.get('ecc')
        sma = self.get('sma')
        if None not in (throttle, pit, hdg, brad, bgm, inc, lan, tan, ape, ecc, sma):
            try:
                self.sim.simulate(self.booster, throttle, pit, hdg, brad, bgm, inc, lan, tan, ape, ecc, sma)
            except SimulationException:
                pass

class UpdateManeuverSim(UpdateRocketSim3D):
    def __init__(self, *args, **kwargs):
        super(UpdateManeuverSim, self).__init__(*args, **kwargs)
    def draw(self):
        UT = self.get('UT')
        self.sim.burnUT = max(self.sim.burnUT, UT)
        super(UpdateManeuverSim, self).draw()

class UpdateSimElements(Gauge):
    # Computes orbital elements from RocketSim results
    def __init__(self, dl, cw, sim, keys):
        super(UpdateSimElements, self).__init__(dl, cw)
        self.sim = sim
        self.keys = keys
    def draw(self):
        for key in self.keys:
            try:
                self.sim.compute_elements(key)
            except SimulationException:
                continue

class UpdateEventXform(Gauge):
    # Abstract class for orbital extensions of RocketSim[3D] results
    def __init__(self, dl, cw, sim, frm, to):
        super(UpdateEventXform, self).__init__(dl, cw)
        self.sim = sim
        self.frm = frm
        self.to = to
    @property
    def nokeys(self):
        return not any(k in self.sim.data for k in self.frm)
    def sim_get(self, key):
        froms = [k for k in self.frm if k in self.sim.data]
        if not froms:
            return None
        return self.sim.data[froms[0]].get(key)
    @property
    def sim_set(self):
        return self.sim.data[self.to]

class UpdateSoiExit(UpdateEventXform):
    # Patches conics out of current SOI (if on escape trajectory)
    def __init__(self, dl, cw, body, sim, frm, to, tgt=None):
        super(UpdateSoiExit, self).__init__(dl, cw, sim, frm, to)
        self.body = body
        self.tgt = tgt
        if tgt is None:
            self.add_prop('soi', 'b.soi[%d]'%(body,))
            self.add_prop('pbn', 'v.body')
        else:
            self.add_prop('soi', 'b.soi[%d]'%(tgt,))
            self.add_prop('pbn', 'b.name[%d]'%(tgt,))
    def _changeopt(self, **kwargs):
        if 'body' in kwargs and self.tgt is None:
            self.del_prop('soi')
            self.add_prop('soi', 'b.soi[%d]'%(kwargs['body'],))
        super(UpdateSoiExit, self)._changeopt(**kwargs)
    def draw(self):
        if self.nokeys:
            return
        soi = self.get('soi')
        if soi is None:
            return
        pbn = self.get('pbn')
        pb_cb = orbit.celestial_bodies.get(str(pbn))
        pb = orbit.ParentBody(pb_cb.rad, pb_cb.gm)
        ecc = self.sim_get('ecc')
        sma = self.sim_get('sma')
        if None in (ecc, sma):
            return
        apa = (1 + ecc) * sma # real apa, not (apa - rad)
        if apa > 0 and apa < soi:
            return
        self.sim.data[self.to] = {}
        eax = orbit.ean_from_r(sma, ecc, soi)
        self.sim_set['ean'] = eax
        manx = orbit.man_from_ean(eax, ecc)
        time = self.sim_get('time')
        if time is None:
            utime = None
        else:
            utime = time + self.sim.UT - orbit.epoch
        ma0 = self.sim_get('man')
        mmo = self.sim_get('mmo')
        xtime = None
        xut = None
        if None not in (ma0, mmo) and mmo > 0:
            ttx = (manx - ma0) / mmo
            self.sim_set['ttx'] = ttx
            if time is not None:
                xtime = time + ttx
                self.sim_set['time'] = xtime
            if utime is not None:
                xut = utime + ttx
                self.sim_set['ut'] = xut
        ape = self.sim_get('ape')
        inc = self.sim_get('inc')
        lan = self.sim_get('lan')
        if None in (ape, inc, lan):
            return
        xx, xv = pb.compute_3d_vector(sma, ecc, eax, ape, inc, lan)
        self.sim_set['x'] = xx
        self.sim_set['v'] = xv
        if None in (xut, pb_cb):
            return
        pelts = dict(pb_cb.elts)
        pmax = pelts['maae'] + pelts['mmo'] * xut
        peax = orbit.ean_from_man(pmax, pelts['ecc'], 16)
        if pb_cb.parent is None:
            return
        ppb = pb_cb.parent_body
        px, pv = ppb.compute_3d_vector(pelts['sma'], pelts['ecc'], peax, pelts['ape'], pelts['inc'], pelts['lan'])
        xpx = px + xx
        xpv = pv + xv
        self.sim_set['px'] = xpx
        self.sim_set['pv'] = xpv
        xelts = ppb.compute_3d_elements(xpx, xpv)
        self.sim_set.update(xelts)

class UpdateApoApsis(UpdateEventXform):
    # Determines parameters of apoapsis
    def draw(self):
        if self.nokeys:
            return
        self.sim.data[self.to] = {}
        tan = self.sim_get('tan')
        if tan is None:
            tana = None
        else:
            tana = math.pi - tan
            if tana < 0: tana += 2.0 * math.pi
            self.sim_set['dtan'] = tana
        man = self.sim_get('man')
        if man is None:
            mana = None
        else:
            mana = math.pi - man
            if mana < 0: mana += 2.0 * math.pi
            self.sim_set['mana'] = mana
        mmo = self.sim_get('mmo')
        ecc = self.sim_get('ecc')
        if None in (mmo, mana, ecc) or mmo <= 0 or ecc >= 1.0:
            ttap = None
        else:
            ttap = mana / mmo
            self.sim_set['ttap'] = ttap
            time = self.sim_get('time')
            if time is not None:
                self.sim_set['time'] = time + ttap
        inc = self.sim_get('inc')
        lan = self.sim_get('lan')
        ape = self.sim_get('ape')
        sma = self.sim_get('sma')
        # position at apoapsis
        if None in (inc, lan, ape, ecc, sma) or ecc >= 1.0:
            return
        rvec, vvec = self.sim.pbody.compute_3d_vector(sma, ecc, math.pi, ape, inc, lan)
        self.sim_set['rvec'] = rvec
        self.sim_set['vvec'] = vvec
        # copy orbital parameters
        self.sim_set['man'] = math.pi
        self.sim_set['ean'] = math.pi
        for k in ['sma', 'ecc', 'ape', 'inc', 'lan', 'mmo', 'sam']:
            self.sim_set[k] = self.sim_get(k)

class UpdateTgtProximity(Gauge):
    # Computes target offset from RocketSim results
    def __init__(self, dl, cw, sim, keys, tgt):
        super(UpdateTgtProximity, self).__init__(dl, cw)
        self.sim = sim
        self.keys = keys
        self.tgt = tgt
        if tgt is not None:
            self.set_tprops(tgt)
    def set_tprops(self, tgt):
        self.add_prop('tsma', 'b.o.sma[%d]'%(tgt,))
        self.add_prop('tecc', 'b.o.eccentricity[%d]'%(tgt,))
        self.add_prop('tmae', 'b.o.maae[%d]'%(tgt,))
        self.add_prop('tinc', 'b.o.inclination[%d]'%(tgt,))
        self.add_prop('tlan', 'b.o.lan[%d]'%(tgt,))
        self.add_prop('tape', 'b.o.argumentOfPeriapsis[%d]'%(tgt,))
        self.add_prop('tgm', 'b.o.gravParameter[%d]'%(tgt,))
    def unset_tprops(self):
        self.del_prop('tsma')
        self.del_prop('tecc')
        self.del_prop('tmae')
        self.del_prop('tinc')
        self.del_prop('tlan')
        self.del_prop('tape')
        self.del_prop('tgm')
    def draw(self):
        tsma = self.get('tsma')
        tmae = self.get('tmae') # Apparently this one is already in radians
        tecc = self.get('tecc')
        tinc = self.getrad('tinc')
        tlan = self.getrad('tlan')
        tape = self.getrad('tape')
        tgm = self.get('tgm')
        if None in (tgm, tsma) or not hasattr(self.sim, 'pbody'):
            gm = None
            tmmo = None
        else:
            # mu = G(M+m)
            gm = tgm + self.sim.pbody.gm
            # target mean motion n = sqrt(mu / a^3)
            tmmo = math.sqrt(gm / tsma ** 3)
        if None in (tmae, tmmo):
            return
        for key in self.keys:
            if key not in self.sim.data:
                continue
            time = self.sim.data[key].get('time')
            if time is None:
                continue
            ut0 = self.sim.UT - orbit.epoch
            ut1 = time + ut0
            # target mean anomaly at time 0
            tma0 = math.fmod(tmae + ut0 * tmmo, 2.0 * math.pi)
            self.sim.data[key]['tma0'] = tma0
            # target mean anomaly change over time
            tdma = math.fmod(time * tmmo, 2.0 * math.pi)
            self.sim.data[key]['tdma'] = tdma
            # target mean anomaly at T
            tma1 = math.fmod(tmae + ut1 * tmmo, 2.0 * math.pi)
            self.sim.data[key]['tma1'] = tma1
            if tecc is None:
                continue
            # target eccentric anomalies
            te0 = orbit.ean_from_man(tma0, tecc, 6)
            te1 = orbit.ean_from_man(tma1, tecc, 6)
            # target true anomalies
            tr0 = orbit.tan_from_ean(te0, tecc)
            tr1 = orbit.tan_from_ean(te1, tecc)
            self.sim.data[key]['tr0'] = tr0
            self.sim.data[key]['tr1'] = tr1
            # target true anomaly change over time
            tdta = math.fmod(tr1 - tr0, 2.0 * math.pi)
            self.sim.data[key]['tdta'] = tdta
            dtan = self.sim.data[key].get('dtan')
            if dtan is not None:
                # true transfer phase angle; +ve is behind
                tpy = dtan - tdta
                self.sim.data[key]['tpy'] = tpy
            # target altitude at T
            trad = tsma * (1.0 - tecc * math.cos(te1))
            talt = trad - self.sim.pbody.rad
            self.sim.data[key]['talt'] = talt
            if None in (gm, tsma, tape, tinc, tlan):
                continue
            # target state vectors at T
            tpb = orbit.ParentBody(self.sim.pbody.rad, gm)
            tr, tv = tpb.compute_3d_vector(tsma, tecc, te0, tape, tinc, tlan)
            r = self.sim.data[key].get('rvec')
            if r is None:
                continue
            # angle between direction vectors
            self.sim.data[key]['pa0'] = orbit.angle_between(tr.hat, r.hat)
            h = self.sim.data[key].get('sam')
            if h is not None:
                # relative inclination
                th = tr.cross(tv)
                ri = orbit.angle_between(h.hat, th.hat)
                self.sim.data[key]['ri'] = ri
            # target state vectors at (vessel) Ap
            txr, txv = tpb.compute_3d_vector(tsma, tecc, te1, tape, tinc, tlan)
            apvec = self.sim.data[key].get('rvec')
            if apvec is None:
                continue
            # angle between direction vectors
            self.sim.data[key]['pa1'] = orbit.angle_between(txr.hat, apvec.hat)

class UpdateTgtRI(Gauge):
    def __init__(self, dl, cw, sim, keys, tgt):
        super(UpdateTgtRI, self).__init__(dl, cw)
        self.sim = sim
        self.keys = keys
        self.tgt = tgt
        if tgt is not None:
            self.set_tprops(tgt)
    def set_tprops(self, tgt):
        self.add_prop('tname', 'b.name[%d]'%(tgt,))
    def unset_tprops(self):
        self.del_prop('tname')
    def draw(self):
        tname = self.get('tname')
        tcb = orbit.celestial_bodies.get(tname)
        if tcb is None:
            return
        # we will assume that you and the target have the same parent body as
        # of the source event.  If not, then you should have patched out with
        # an UpdateSoiExit, shouldn't you?
        pcb = tcb.parent_body
        if pcb is None:
            return
        ut0 = self.sim.UT - orbit.epoch
        for key in self.keys:
            if key not in self.sim.data:
                continue
            time = self.sim.data[key].get('time')
            if time is None:
                continue
            ut1 = time + ut0
            sam = self.sim.data[key].get('sam')
            tsam = tcb.samhat
            if None in (sam, tsam):
                continue
            ri = orbit.angle_between(sam.hat, tsam)
            self.sim.data[key]['ri'] = ri

class UpdateTgtCloseApproach(UpdateEventXform):
    # Finds close(st?) approach to target
    COARSE_STEPS = 80
    FINE_ITERS = 24
    def __init__(self, dl, cw, sim, tgt, frm, to):
        super(UpdateTgtCloseApproach, self).__init__(dl, cw, sim, frm, to)
        self.tgt = tgt
        if tgt is not None:
            self.set_tprops(tgt)
    def set_tprops(self, tgt):
        self.add_prop('tname', 'b.name[%d]'%(tgt,))
    def unset_tprops(self):
        self.del_prop('tname')
    def draw(self):
        if self.nokeys:
            return
        tname = self.get('tname')
        tcb = orbit.celestial_bodies.get(tname)
        if tcb is None:
            return
        # we will assume that you and the target have the same parent body as
        # of the source event.  If not, then you should have patched out with
        # an UpdateSoiExit, shouldn't you?
        pcb = tcb.parent_body
        if pcb is None:
            return
        self.sim.data[self.to] = {}
        ut0 = self.sim.UT - orbit.epoch
        time = self.sim_get('time')
        if time is None:
            return
        ut1 = time + ut0
        mmo = self.sim_get('mmo')
        tmmo = tcb.elts['mmo']
        if None in (mmo, tmmo):
            return
        # Synodic mean motion
        symmo = abs(tmmo - mmo)
        # Synodic period
        syper = 2.0 * math.pi / symmo
        self.sim_set['syper'] = syper
        man0 = self.sim_get('man')
        sma = self.sim_get('sma')
        ecc = self.sim_get('ecc')
        ape = self.sim_get('ape')
        inc = self.sim_get('inc')
        lan = self.sim_get('lan')
        if None in (man0, sma, ecc, ape, inc, lan):
            return
        mind = None
        argmind = None
        # Let's find the rough region first
        # We're not interested in anything more than 1 syper out
        for i in xrange(self.COARSE_STEPS):
            it = i * syper / float(self.COARSE_STEPS)
            t = time + it
            ut = ut1 + it
            man = man0 + it * mmo
            ean = orbit.ean_from_man(man, ecc, 16)
            r, v = pcb.compute_3d_vector(sma, ecc, ean, ape, inc, lan)
            tr, tv = tcb.vectors_at_ut(ut)
            d = (tr - r).mag
            if mind is None or d < mind:
                mind = d
                argmind = it
        if argmind is None:
            return
        dt = argmind
        self.sim_set['rough'] = time + dt
        # Now we Newton it in
        last_step_size = None
        for i in xrange(self.FINE_ITERS):
            t = time + dt
            ut = ut1 + dt
            man = man0 + dt * mmo
            ean = orbit.ean_from_man(man, ecc, 16)
            r, v = pcb.compute_3d_vector(sma, ecc, ean, ape, inc, lan)
            tr, tv = tcb.vectors_at_ut(ut)
            dr = tr - r
            dv = tv - v
            # Solve closest approach of x = dr + w dv to 0
            # at that point, x . dv = 0
            # but x . dv = (dr + w dv) . dv = dr . dv + w dv . dv
            drdv = dr.dot(dv)
            dvdv = dv.dot(dv)
            if dvdv == 0:
                # we're at rest relative to the target.  Let's give up :'(
                return
            w = -drdv / dvdv
            if last_step_size is not None and abs(w) > last_step_size:
                # our step size just got bigger, we're probably diverging
                # this is another of those 'give up' situations, isn't it?
                return
            last_step_size = abs(w)
            dt += w
            if abs(w) < 1.0:
                # We got within a second.  That's probably good enough
                break
        self.sim_set['lss'] = last_step_size
        self.sim_set['time'] = t
        # copy orbital parameters
        self.sim_set['man'] = man
        self.sim_set['ean'] = ean
        for k in ['sma', 'ecc', 'ape', 'inc', 'lan', 'mmo']:
            self.sim_set[k] = self.sim_get(k)
        # vectors
        self.sim_set['rvec'] = r
        self.sim_set['vvec'] = v
        self.sim_set['trvec'] = tr
        self.sim_set['tvvec'] = tv
        self.sim_set['drvec'] = dr
        self.sim_set['dvvec'] = dv
        # find distance to Earth (for comms range)
        ecb = orbit.celestial_bodies.get('Earth', orbit.celestial_bodies.get('Kerbin'))
        if ecb is None:
            return
        if ecb.name == tcb.parent:
            self.sim_set['edrvec'] = r
        else:
            er, _ = ecb.vectors_at_ut(ut)
            self.sim_set['ervec'] = er
            edr = r - er
            self.sim_set['edrvec'] = edr

class UpdateSoiEntry(UpdateEventXform):
    """Patches into target SOI.  Input event should be close approach"""
    FINE_ITERS = 16
    def __init__(self, dl, cw, sim, tgt, frm, to):
        super(UpdateSoiEntry, self).__init__(dl, cw, sim, frm, to)
        self.tgt = tgt
        if tgt is not None:
            self.set_tprops(tgt)
    def set_tprops(self, tgt):
        self.add_prop('tname', 'b.name[%d]'%(tgt,))
        self.add_prop('tsoi', 'b.soi[%d]'%(tgt,))
    def unset_tprops(self):
        self.del_prop('tname')
        self.del_prop('tsoi')
    def draw(self):
        if self.nokeys:
            return
        tname = self.get('tname')
        tcb = orbit.celestial_bodies.get(tname)
        if tcb is None:
            return
        # we will assume that you and the target have the same parent body as
        # of the source event.  If not, then you should have patched out with
        # an UpdateSoiExit, shouldn't you?
        pcb = tcb.parent_body
        if pcb is None:
            return
        ut0 = self.sim.UT - orbit.epoch
        time = self.sim_get('time')
        if time is None:
            return
        ut1 = ut0 + time
        soi = self.get('tsoi')
        dr = self.sim_get('drvec')
        dv = self.sim_get('dvvec')
        if None in (soi, dr, dv):
            return
        if soi <= dr.mag:
            # We're going to miss the SOI entirely
            return
        man0 = self.sim_get('man')
        sma = self.sim_get('sma')
        ecc = self.sim_get('ecc')
        ape = self.sim_get('ape')
        inc = self.sim_get('inc')
        lan = self.sim_get('lan')
        mmo = self.sim_get('mmo')
        if None in (man0, sma, ecc, ape, inc, lan, mmo):
            return
        last_step_size = None
        dt = 0
        for i in xrange(self.FINE_ITERS):
            t = time + dt
            ut = ut1 + dt
            man = man0 + dt * mmo
            ean = orbit.ean_from_man(man, ecc, 16)
            r, v = pcb.compute_3d_vector(sma, ecc, ean, ape, inc, lan)
            tr, tv = tcb.vectors_at_ut(ut)
            dr = r - tr
            dv = v - tv
            # x = dr + w dv, we want |x| = soi, decreasing (hence lower branch)
            # x . x = dr.dr + 2w dr.dv + w^2 dv.dv
            # so dv.dv w^2 + 2dr.dv w + (dr.dr - soi^2) = 0
            a = dv.dot(dv)
            b = dr.dot(dv) * 2.0
            c = dr.dot(dr) - soi ** 2
            # solve quadratic
            d = b ** 2 - 4.0 * a * c
            if d < 0:
                # apparently our current linearisation misses the SOI
                # let's just give up, we were probably right on the edge anyway
                return
            # we want the negative root, i.e. entry rather than exit
            w = (-b - math.sqrt(d)) / (a * 2.0)
            if last_step_size is not None and abs(w) > last_step_size:
                # our step size just got bigger, we're probably diverging
                # this is another of those 'give up' situations, isn't it?
                return
            last_step_size = abs(w)
            dt += w
            if abs(w) < 1.0:
                # We got within a second.  That's probably good enough
                break
        self.sim.data[self.to] = {}
        self.sim_set['lss'] = last_step_size
        self.sim_set['time'] = t
        self.sim_set['rvec'] = r
        self.sim_set['vvec'] = v
        self.sim_set['trvec'] = tr
        self.sim_set['tvvec'] = tv
        self.sim_set['drvec'] = dr
        self.sim_set['dvvec'] = dv
        tpb = orbit.ParentBody(tcb.rad, tcb.gm)
        elts = tpb.compute_3d_elements(dr, dv)
        self.sim_set.update(elts)
        # find distance to Earth (for comms range)
        ecb = orbit.celestial_bodies.get('Earth', orbit.celestial_bodies.get('Kerbin'))
        if ecb is None:
            return
        if ecb.name == tcb.parent:
            self.sim_set['edrvec'] = r
        else:
            er, _ = ecb.vectors_at_ut(ut)
            self.sim_set['ervec'] = er
            edr = r - er
            self.sim_set['edrvec'] = edr

class RSTime(OneLineGauge, TimeFormatterMixin):
    def __init__(self, dl, cw, key, sim):
        super(RSTime, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        super(RSTime, self).draw()
        t = self.sim.data.get(self.key, {}).get('time')
        if t is not None:
            if t > 7200:
                text = self.fmt_time(t, 3)
                width = self.olg_width - 2
                self.addstr('T:%*s'%(width, text))
            elif self.sim.dt < 1.0 and self.olg_width > 6:
                self.addstr('T:%*.1fs'%(self.olg_width - 3, t))
            else:
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
        self.chgat(0, self.width, curses.color_pair(col))

class RSAlt(SIGauge):
    unit = 'm'
    label = 'Y'
    def __init__(self, dl, cw, key, sim):
        super(RSAlt, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        alt = None
        if self.key in self.sim.data:
            d = self.sim.data[self.key]
            alt = d.get('height', d.get('alt'))
        if alt is not None:
            super(RSAlt, self).draw(alt)
            col = 3 if alt > 0 else 1
            if self.key == 'b':
                col = 1 if alt > 10 else 0 # TODO parametrise
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 1
            if self.key == 'b':
                col = 3
        self.chgat(0, self.width, curses.color_pair(col))

class RSDownrange(SIGauge):
    unit = 'm'
    label = 'X'
    def __init__(self, dl, cw, key, sim):
        super(RSDownrange, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        x = self.sim.data.get(self.key, {}).get('downrange')
        if x is not None:
            super(RSDownrange, self).draw(x)
            col = 3
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 1
            if self.key == 's':
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
        vs = self.sim.data.get(self.key, {}).get('vs')
        if vs is not None:
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
        self.chgat(0, self.width, curses.color_pair(col))

class RSHSpeed(SIGauge):
    unit = 'm/s'
    label = 'H'
    def __init__(self, dl, cw, key, sim):
        super(RSHSpeed, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        hs = self.sim.data.get(self.key, {}).get('hs')
        if hs is not None:
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
        self.chgat(0, self.width, curses.color_pair(col))

class RSApoapsis(SIGauge):
    unit = 'm'
    label = 'A'
    def __init__(self, dl, cw, key, sim):
        super(RSApoapsis, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        apa = self.sim.data.get(self.key, {}).get('apa')
        if apa is not None:
            super(RSApoapsis, self).draw(apa)
            col = 3
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSPeriapsis(SIGauge):
    unit = 'm'
    label = 'P'
    def __init__(self, dl, cw, key, sim):
        super(RSPeriapsis, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        pea = self.sim.data.get(self.key, {}).get('pea')
        if pea is not None:
            super(RSPeriapsis, self).draw(pea)
            col = 3
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSAngleGauge(OneLineGauge):
    signed = False
    def __init__(self, dl, cw, key, sim):
        super(RSAngleGauge, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        super(RSAngleGauge, self).draw()
        keys = [k for k in list(self.key)
                if k in self.sim.data and
                   self.param in self.sim.data[k]]
        if keys:
            angle = math.degrees(self.sim.data[keys[0]][self.param])
            if angle < 0 and not self.signed:
                angle += 360
            width = self.olg_width - 3
            prec = min(5, width - 4)
            self.addstr('%s:%+*.*f'%(self.label, width, prec, angle))
            col = 3
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))
        self.addch(self.olg_width - 1, curses.ACS_DEGREE, curses.A_ALTCHARSET)

class RSTimeGauge(OneLineGauge, TimeFormatterMixin):
    def __init__(self, dl, cw, key, sim):
        super(RSTimeGauge, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        super(RSTimeGauge, self).draw()
        keys = [k for k in list(self.key)
                if k in self.sim.data and
                   self.param in self.sim.data[k]]
        width = self.olg_width - len(self.label)
        if keys:
            t = self.sim.data[keys[0]][self.param]
            text = self.fmt_time(t, 3)
            self.addstr('%s:%*s'%(self.label, width - 1, text))
            col = 3
        else:
            self.addstr(self.label + '-' * width)
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSObtPeriod(RSTimeGauge):
    param = 'per'
    label = 'D'

class RSTTAp(RSTimeGauge):
    param = 'ttap'
    label = 'T'

class RSTimeParam(RSTimeGauge):
    def __init__(self, dl, cw, key, sim, param, label):
        self.param = param
        self.label = label
        super(RSTimeParam, self).__init__(dl, cw, key, sim)

class RSAngleParam(RSAngleGauge):
    def __init__(self, dl, cw, key, sim, param, label):
        self.param = param
        self.label = label
        super(RSAngleParam, self).__init__(dl, cw, key, sim)

class RSTgtAlt(SIGauge):
    unit = 'm'
    param = 'talt'
    label = 'Z'
    def __init__(self, dl, cw, key, sim):
        super(RSTgtAlt, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
    def draw(self):
        keys = [k for k in list(self.key)
                if k in self.sim.data and
                   self.param in self.sim.data[k]]
        if keys:
            d = self.sim.data[keys[0]]
            alt = d.get(self.param)
            super(RSTgtAlt, self).draw(alt)
            col = 3
        else:
            self.addstr(self.label+'-'*(self.olg_width - 1))
            col = 2
        self.chgat(0, self.width, curses.color_pair(col))

class RSSIParam(SIGauge):
    def __init__(self, dl, cw, key, sim, param, label, unit):
        super(RSSIParam, self).__init__(dl, cw)
        self.sim = sim
        self.key = key
        self.param = param
        self.label = label
        self.unit = unit
    def draw(self):
        value = self.sim.data.get(self.key, {}).get(self.param)
        if value is not None:
            if isinstance(value, matrix.Vector3):
                value = value.mag
            super(RSSIParam, self).draw(value)
            col = 3
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
        keys = [k for k in list(self.key)
                if k in self.sim.data and
                   self.param in self.sim.data[k]]
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
