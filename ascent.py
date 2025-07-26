#!/usr/bin/python3
# Simulates (airless) ascent-to-orbit, for Ascent console

import sim
import orbit

class AscentSim(sim.RocketSim):
    orbitals = True
    def simulate(self, booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm):
        self.sim_setup(booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm, False)
        iv_sgn = 1 if (vs >= 0) else -1
        self.data = {}
        while not (('o' in self.data and 'v' in self.data and 'b' in self.data) or
                   self.t > 1200):
            if self.step():
                break
            if self.hs > self.tgt_obt_vel and 'o' not in self.data:
                self.data['o'] = self.encode()
            if self.vs * iv_sgn <= 0 and 'v' not in self.data:
                self.data['v'] = self.encode()
            if len(self.booster.stages) <= self.stagecap and 'b' not in self.data:
                self.data['b'] = self.encode()
            if self.debug:
                print("time %d"%(self.t,))
                print("(%g, %g) -> (%g, %g)"%(self.downrange, self.alt, self.hs, self.vs))
                print("%s"%(''.join(self.data.keys()),))

class AscentSim3D(sim.RocketSim3D):
    def simulate(self, booster, throttle, pit, hdg, brad, bgm, inc, lan, tan, ape, ecc, sma, reflon=None):
        ean = orbit.ean_from_tan(tan, ecc)
        self.sim_setup(booster, throttle, pit, hdg, brad, bgm, inc, lan, ean, ape, ecc, sma)
        self.set_reflon(reflon)
        iv_sgn = 1 if (self.vs >= 0) else -1
        self.data = {'0': self.encode()}
        while not (('o' in self.data and 'v' in self.data and 'b' in self.data) or
                   self.t > 1200):
            if self.step():
                break
            self.tgt_obt_vel = self.pbody.vcirc(self.alt)
            if self.hs > self.tgt_obt_vel and 'o' not in self.data:
                self.data['o'] = self.encode()
            if self.vs * iv_sgn <= 0 and 'v' not in self.data:
                self.data['v'] = self.encode()
            if len(self.booster.stages) <= self.stagecap and 'b' not in self.data:
                self.data['b'] = self.encode()
            if self.debug:
                print("time %d"%(self.t,))
                print("(%g, %g) -> (%g, %g)"%(self.downrange, self.alt, self.hs, self.vs))
                print("%s"%(''.join(self.data.keys()),))
