#!/usr/bin/python
# Simulates (airless) ascent-to-orbit, for Ascent console

import sim

class AscentSim(sim.RocketSim):
    orbitals = True
    def simulate(self, booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm):
        self.sim_setup(booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm)
        self.data = {}
        while not (('o' in self.data and 'v' in self.data and 'b' in self.data) or
                   self.t > 1200):
            self.step()
            if self.hs > self.tgt_obt_vel and 'o' not in self.data:
                self.data['o'] = self.encode()
            if self.vs <= 0 and 'v' not in self.data:
                self.data['v'] = self.encode()
            if len(self.booster.stages) <= self.stagecap and 'b' not in self.data:
                self.data['b'] = self.encode()
            if self.debug:
                print "time %d"%(self.t,)
                print "(%g, %g) -> (%g, %g)"%(self.downrange, self.alt, self.hs, self.vs)
                print "%s"%(''.join(self.data.keys()),)
        self.has_data = True
