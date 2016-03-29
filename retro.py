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
        def encode():
            return {'time': t, 'alt': alt, 'x': downrange, 'hs': hs, 'vs': vs}
        # results
        self.data = {}
        while not (('h' in self.data and 'v' in self.data) or
                   ('s' in self.data and 'b' in self.data)):
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
            if hs <= 0 and 'h' not in  self.data:
                self.data['h'] = encode()
            if 'h' in self.data:
                # Pitch for vertical descent
                twr = booster.twr
                if twr > abs(hs):
                    cx = -hs / twr
                    cy = math.sqrt(1 - cx*cx)
                else:
                    cx = 0
                    cy = 1
            if vs >= 0 and 'v' not in self.data:
                self.data['v'] = encode()
            if alt <= 0 and 's' not in self.data:
                self.data['s'] = encode()
            if not booster.stages and 'b' not in self.data:
                self.data['b'] = encode()
            if self.debug:
                print "time %d"%(t,)
                print "(%g, %g) -> (%g, %g)"%(downrange, alt, hs, vs)
                print "%s"%(''.join(self.data.keys()),)
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
    if 'h' in rs.data:
        print "H %gs %gm (%gm)"%(rs.data['h']['time'], rs.data['h']['alt'], rs.data['h']['x'])
    else:
        print "!H"
    if 'v' in rs.data:
        print "V %gs %gm (%gm)"%(rs.data['v']['time'], rs.data['v']['alt'], rs.data['v']['x'])
    else:
        print "!V"
    if 's' in rs.data:
        print "S %gs %gm/s (%gm %gm/s)"%(rs.data['s']['time'], rs.data['s']['vs'], rs.data['s']['x'], rs.data['s']['hs'])
    else:
        print "!S"
    if 'b' in rs.data:
        print "B %gs %gm %gm/s"%(rs.data['b']['time'], rs.data['b']['alt'], rs.data['b']['vs'])
    else:
        print "!B"
