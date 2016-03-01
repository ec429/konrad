#!/usr/bin/python
# For computing how much delta-V your rocket has left

import math
import json

class Propellant(object):
    def __init__(self, name, volume, density, mainEngine):
        self.name = name
        self.volume = volume
        self.density = density
        self.mainEngine = mainEngine
    @property
    def mass(self):
        return self.volume * self.density
    @classmethod
    def from_dict(cls, d):
        return cls(d['name'], d['volume'], d['density'], d.get('mainEngine', True))

class Stage(object):
    def __init__(self, props, isp, dry):
        self.props = props # list of Propellant instances
        self.isp = isp # I_sp(Vac) of main engine, in seconds
        self._dry = dry # stage dry mass, in tons
        self.load = 0
    @property
    def dry(self):
        return self._dry + self.load
    def add_payload(self, mass):
        self.load = mass
    @property
    def veff(self): # effective exhaust velocity, in m/s
        return self.isp * 9.80665
    @property
    def wet(self):
        return self.dry + sum(p.mass for p in self.props if p.mainEngine)
    @property
    def deltaV(self):
        mr = self.wet / float(self.dry)
        lmr = math.log(mr)
        return self.veff * lmr
    @classmethod
    def from_dict(cls, d):
        return cls([Propellant.from_dict(p) for p in d['props']], d['isp'], d['dry'])

class Booster(object):
    def __init__(self, stages):
        self.stages = stages # list of Stage instances
        for i in xrange(len(self.stages) - 1, 0, -1):
            self.stages[i - 1].add_payload(self.stages[i].wet)
    @property
    def wet(self):
        return self.stages[0].wet
    @property
    def deltaV(self):
        return sum(s.deltaV for s in self.stages)
    @classmethod
    def from_dict(cls, d):
        return cls([Stage.from_dict(s) for s in d])
    @classmethod
    def from_json(cls, j):
        d = json.loads(j)
        return cls.from_dict(d)

if __name__ == '__main__':
    import sys
    j = sys.stdin.read()
    b = Booster.from_json(j)
    print "Wet mass: %.3ft"%(b.wet,)
    print "Delta-V : %.3fm/s"%(b.deltaV,)
    print "Breakdown by Stage"
    for i,s in enumerate(b.stages):
        print "  Stage %d:"%(i,)
        print "    Wet mass: %.3ft"%(s.wet - s.load,)
        print "    Dry mass: %.3ft"%(s.dry - s.load,)
        if s.load:
            print "    Nxt mass: %.3ft"%(s.load,)
        print "    Delta-V : %.3fm/s"%(s.deltaV,)
