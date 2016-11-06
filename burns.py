#!/usr/bin/python
# Simulates (airless) maneuver burn, for Astrogation console

import sim

class ManeuverSim(sim.RocketSim):
    orbitals = True
    UT = 0
    burnUT = 0
    def simulate(self, booster, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm):
        self.sim_setup(booster, hs, vs, alt, 0, pit, hdg, lat, lon, brad, bgm, False)
        self.has_data = False
        burnT = self.burnUT - self.UT
        if burnT > 1200:
            return
        while (self.t < burnT):
            if self.step():
                return
        self.data = {'0': self.encode()}
        self.throttle = throttle
        while not ('b' in self.data or self.t > 1200):
            if self.step():
                return
            if len(self.booster.stages) <= self.stagecap and 'b' not in self.data:
                self.data['b'] = self.encode()
            if self.debug:
                print "time %d"%(self.t,)
                print "(%g, %g) -> (%g, %g)"%(self.downrange, self.alt, self.hs, self.vs)
                print "%s"%(''.join(self.data.keys()),)
        self.has_data = True

# notes:
# burnsim should offer 'start' and 'rotating' frames for 'fixed' mode, and also have 'prograde' mode
