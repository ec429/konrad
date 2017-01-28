#!/usr/bin/python
# Simulates airless descent, for Retro

import sim
import orbit

class RetroSim(sim.RocketSim):
    surface = True
    def simulate(self, booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm):
        self.sim_setup(booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm, True)
        self.data = {}
        while not ((
                    (
                     ('h' in self.data and 'v' in self.data)
                     and
                     's' in self.data
                    ) and
                    'b' in self.data
                   ) or
                   self.t > 1200):
            if self.step():
                break
            if self.hs <= 0 and 'h' not in self.data:
                self.data['h'] = self.encode()
            if self.vs >= 0 and 'v' not in self.data:
                self.data['v'] = self.encode()
            if self.alt <= self.local_ground_alt and 's' not in self.data:
                self.data['s'] = self.encode()
            if len(self.booster.stages) <= self.stagecap and 'b' not in self.data:
                self.data['b'] = self.encode()
            if self.debug:
                print "time %d"%(self.t,)
                print "(%g, %g) -> (%g, %g)"%(self.downrange, self.alt, self.hs, self.vs)
                print "%s"%(''.join(self.data.keys()),)

class RetroSim3D(sim.RocketSim3D):
    def simulate(self, booster, throttle, pit, hdg, brad, bgm, inc, lan, tan, ape, ecc, sma, reflon=None):
        ean = orbit.ean_from_tan(tan, ecc)
        self.sim_setup(booster, throttle, pit, hdg, brad, bgm, inc, lan, ean, ape, ecc, sma)
        self.set_reflon(reflon)
        self.data = {'0': self.encode()}
        hv0 = self.hv
        while not ((
                    (
                     ('h' in self.data and 'v' in self.data)
                     and
                     's' in self.data
                    ) and
                    'b' in self.data
                   ) or
                   self.t > 1200):
            if self.step():
                break
            if self.hv.dot(hv0) <= 0 and 'h' not in self.data:
                self.data['h'] = self.encode()
            if self.vs >= 0 and 'v' not in self.data:
                self.data['v'] = self.encode()
            if self.alt <= self.local_ground_alt and 's' not in self.data:
                self.data['s'] = self.encode()
            if len(self.booster.stages) <= self.stagecap and 'b' not in self.data:
                self.data['b'] = self.encode()
            if self.debug:
                print "time %d"%(self.t,)
                print "(%g, %g) -> (%g, %g)"%(self.downrange, self.alt, self.hs, self.vs)
                print "%s"%(''.join(self.data.keys()),)
