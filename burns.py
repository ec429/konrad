#!/usr/bin/python
# Simulates (airless) maneuver burn, for Astrogation console

import sim
import orbit
import math

class ManeuverSim(sim.RocketSim3D):
    orbitals = True
    UT = 0
    burnUT = 0
    burn_dur = -1
    burn_end = -1
    def simulate(self, booster, throttle, pit, hdg, brad, bgm, inc, lan, tan, ape, ecc, sma):
        burnT = self.burnUT - self.UT
        burn_dur = self.burn_dur
        if self.burn_end >= 0:
            burn_dur = max(self.burn_end - self.burnUT, 0)
        ean = orbit.ean_from_tan(tan, ecc)
        man = orbit.man_from_ean(ean, ecc)
        mmo = math.sqrt(bgm / abs(sma) ** 3)
        man += mmo * burnT
        ean = orbit.ean_from_man(man, ecc, 24)
        self.sim_setup(booster, throttle, pit, hdg, brad, bgm, inc, lan, ean, ape, ecc, sma)
        self.t = burnT
        self.data = {'0': self.encode()}
        self.dt = 0.2 # Use shorter time step for higher accuracy
        if burn_dur == 0:
            self.data['b'] = self.encode()
            return
        while not ('b' in self.data or self.t > 1200 + burnT):
            if self.step():
                return
            burnout = len(self.booster.stages) <= self.stagecap
            timeout = burn_dur >= 0 and self.t >= burnT + burn_dur
            if (burnout or timeout) and 'b' not in self.data:
                self.data['b'] = self.encode()
            if self.debug:
                print "time %d"%(self.t,)
                print "(%g, %g) -> (%g, %g)"%(self.downrange, self.alt, self.hs, self.vs)
                print "%s"%(''.join(self.data.keys()),)
