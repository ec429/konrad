#!/usr/bin/python
# Simulates airless descent, for Retro

import math

class RetroSim(object):
    def __init__(self, ground_alt=None, ground_map=None, mode=0, debug=False):
        self.has_data = False
        self.ground_alt = ground_alt
        self.ground_map = ground_map
        self.mode = mode
        self.debug = debug
    def simulate(self, booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm):
        if self.ground_alt is not None:
            alt -= self.ground_alt
        # components of unit thrust
        pitch = math.radians(pit)
        cy = math.sin(pitch)
        cx = -math.cos(pitch)
        # components of unit 'x', assumes hdg is retrograde
        heading = math.radians(hdg)
        clat = -math.cos(heading)
        clong = -math.sin(heading)
        # state
        downrange = 0
        t = 0
        ground_alt = None
        # time step, in seconds
        dt = 1
        def encode():
            return {'time': t, 'alt': alt - ground_alt, 'x': downrange, 'hs': hs, 'vs': vs}
        # results
        self.data = {}
        while not ((
                    (
                     ('h' in self.data and 'v' in self.data)
                     or
                     's' in self.data
                    ) and
                    'b' in self.data
                   ) or
                   t > 1200):
            hs0 = hs
            vs0 = vs
            alt0 = alt
            t += dt
            dv = booster.simulate(throttle, dt)
            if self.mode == 1:
                vel = math.hypot(hs, vs)
                if vel > 0:
                    cx = -hs / vel
                    cy = -vs / vel
            dhs = dv * cx
            dvs = dv * cy
            hs += dhs
            # local gravity
            if None in (alt, brad, bgm):
                g = 0
            else:
                g = bgm / (alt + brad)**2
            vs += dvs - (g * dt)
            alt += (vs + vs0) / 2.0
            mhs = (hs + hs0) / 2.0
            downrange += mhs
            if brad is not None:
                # update lat & long
                lat += mhs * clat / (brad + alt)
                lon += mhs * clong / ((brad + alt) * math.cos(lat))
                # transform our velocity - planet is curving away beneath us
                rot = mhs / (brad + alt)
                nhs = hs * math.cos(rot) - vs * math.sin(rot)
                nvs = hs * math.sin(rot) + vs * math.cos(rot)
                hs, vs = nhs, nvs
            if self.ground_map is not None:
                mlat = int(round(lat * 2))
                mlon = int(round(lon * 2)) % 720
                if mlon >= 360: mlon -= 720
                elif mlon < -360: mlon += 720
                ground_alt = self.ground_map[mlon][mlat]
            elif self.ground_alt is not None:
                ground_alt = self.ground_alt
            else:
                ground_alt = 0
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
            if alt <= ground_alt and 's' not in self.data:
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
    rs = RetroSim(ground_alt=6700)#booster, hs, vs, alt, throttle, pit, hdg, lat, lon, g):
    rs.simulate(booster.Booster.clone(b), 100, -10, 2000, 0.88326, 60, 90, 0, 0, 1.6)
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
