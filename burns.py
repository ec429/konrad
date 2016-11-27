#!/usr/bin/python
# Simulates (airless) maneuver burn, for Astrogation console

import sim
import orbit
import math

class ManeuverSim(sim.RocketSim3D):
    orbitals = True
    UT = 0
    burnUT = 0
    def simulate(self, booster, throttle, pit, hdg, brad, bgm, inc, lan, tan, ape, ecc, sma):
        if ecc >= 1.0:
            raise sim.SimulationException("Open orbits not supported yet")
        burnT = self.burnUT - self.UT
        ean = orbit.ean_from_tan(tan, ecc)
        man = orbit.man_from_ean(ean, ecc)
        mmo = math.sqrt(bgm / sma ** 3)
        man += mmo * burnT
        ean = orbit.ean_from_man(man, ecc, 12)
        self.sim_setup(booster, throttle, pit, hdg, brad, bgm, inc, lan, ean, ape, ecc, sma)
        self.t = burnT
        self.data = {'0': self.encode()}
        while not ('b' in self.data or self.t > 1200 + burnT):
            if self.step():
                return
            if len(self.booster.stages) <= self.stagecap and 'b' not in self.data:
                self.data['b'] = self.encode()
            if self.debug:
                print "time %d"%(self.t,)
                print "(%g, %g) -> (%g, %g)"%(self.downrange, self.alt, self.hs, self.vs)
                print "%s"%(''.join(self.data.keys()),)

# notes:
# burnsim should offer 'start' and 'rotating' frames for 'fixed' mode, and also have 'prograde' mode
