#!/usr/bin/python
# Simulates airless descent, for Retro

import math

class RetroSim(object):
    def __init__(self, debug=False):
        self.has_data = False
        self.debug = debug
    def simulate(self, booster, hs, vs, alt, throttle, pit, g):
        pitch = math.radians(pit)
        # components of unit thrust
        cy = math.sin(pitch)
        cx = -math.cos(pitch)
        # state
        downrange = 0
        t = 0
        # time step, in seconds
        dt = 1
        # are we done?
        self.have = [False, False, False, False]
        while not ((self.have[0] and self.have[1]) or
                   (self.have[2] and self.have[3])):
            hs0 = hs
            vs0 = vs
            alt0 = alt
            t += dt
            dv = booster.simulate(throttle, dt)
            dhs = dv * cx
            dvs = dv * cy
            hs += dhs
            vs += dvs - (g * dt)
            alt += (vs + vs0) / 2.0
            downrange += (hs + hs0) / 2.0
            if hs <= 0 and not self.have[0]:
                self.htime = t
                self.halt = alt
                self.hx = downrange
                self.have[0] = True
            if self.have[0]:
                # Pitch for vertical descent
                twr = booster.twr
                if twr > abs(hs):
                    cx = -hs / twr
                    cy = math.sqrt(1 - cx*cx)
                else:
                    cx = 0
                    cy = 1
            if vs >= 0 and not self.have[1]:
                self.vtime = t
                self.valt = alt
                self.vx = downrange
                self.have[1] = True
            if alt <= 0 and not self.have[2]:
                self.stime = t
                self.shs = hs
                self.svs = vs
                self.sx = downrange
                self.have[2] = True
            if not booster.stages and not self.have[3]:
                self.btime = t
                self.balt = alt
                self.bvs = vs
                self.have[3] = True
            if self.debug:
                print "time %d"%(t,)
                print "(%g, %g) -> (%g, %g)"%(downrange, alt, hs, vs)
                print "%s%s%s%s"%tuple('*' if b else ' ' for b in self.have)
        self.has_data = True

if __name__ == '__main__':
    import booster
    b = booster.Booster.from_json('''[{
    "props": [{"name": "MON10", "volume": 48.4},
              {"name": "MMH", "volume": 51.6}],
    "isp": 260,
    "dry": 0.4,
    "thrust": 1
    }]''')
    rs = RetroSim()
    rs.simulate(booster.Booster.clone(b), 100, -10, 2000, 0.88326, 60, 1.6)
    assert rs.has_data
    if rs.have[0]:
        print "H %gs %gm (%gm)"%(rs.htime, rs.halt, rs.hx)
    else:
        print "!H"
    if rs.have[1]:
        print "V %gs %gm (%gm)"%(rs.vtime, rs.valt, rs.vx)
    else:
        print "!V"
    if rs.have[2]:
        print "Y %gs %gm/s (%gm %gm/s)"%(rs.stime, rs.svs, rs.sx, rs.shs)
    else:
        print "!Y"
    if rs.have[3]:
        print "B %gs %gm %gm/s"%(rs.btime, rs.balt, rs.bvs)
    else:
        print "!B"
