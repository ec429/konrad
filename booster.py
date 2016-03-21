#!/usr/bin/python
# For computing how much delta-V your rocket has left

import math
import json
import os
import cfg

class Propellant(object):
    def __init__(self, name, volume, density, mainEngine):
        self.name = name
        self.volume = volume
        self.filled = volume
        self.density = density
        self.mainEngine = mainEngine
    @property
    def mass(self):
        return self.filled * self.density
    def __str__(self):
        return self.name if self.mainEngine else '(%s)'%(self.name,)
    @classmethod
    def from_dict(cls, d):
        name = d['name']
        if 'density' not in d:
            d['density'] = known_props[name]
        return cls(name, d['volume'], d['density'], d.get('mainEngine', True))

class Stage(object):
    def __init__(self, props, isp, dry):
        self.props = props # list of Propellant instances
        check = [p.name for p in props]
        if len(check) != len(set(check)):
            raise Exception("A propellant name was repeated within a stage, we don't like that")
        self.isp = isp # I_sp(Vac) of main engine, in seconds
        self._dry = dry # stage dry mass, in tons
        self._load = None
    @property
    def dry(self):
        return self._dry + self.load + sum(p.mass for p in self.props if not p.mainEngine)
    def add_payload(self, load):
        self._load = load
    @property
    def load(self):
        if self._load is None:
            return 0
        return self._load.wet
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
    def this_prop(self, propname):
        """Returns Propellant object for given propellant in this stage, or None"""
        for p in self.props:
            if p.name == propname:
                return p
    def prop_here(self, propname):
        """Returns volume of given propellant in this stage"""
        return sum(prop.volume if prop.name == propname else 0 for prop in self.props)
    def prop_above(self, propname):
        """Returns volume of given propellant in all upper stages"""
        if self._load is None:
            return 0
        return self._load.prop_all(propname)
    def prop_all(self, propname):
        """Returns total volume of given propellant in this stage and all upper stages"""
        return self.prop_here(propname) + self.prop_above(propname)
    @property
    def propnames(self):
        return [str(p) for p in self.props]
    @classmethod
    def from_dict(cls, d):
        return cls([Propellant.from_dict(p) for p in d['props']], d['isp'], d['dry'])

class Booster(object):
    def __init__(self, stages):
        self.stages = stages # list of Stage instances
        for i in xrange(len(self.stages) - 1, 0, -1):
            self.stages[i - 1].add_payload(self.stages[i])
    def stage(self):
        del self.stages[0]
    @property
    def all_props(self):
        # All propellants, sorted by which stage they appear in first
        l = []
        for s in self.stages:
            for p in (prop.name for prop in s.props):
                if p not in l:
                    l.append(p)
        return l
    @property
    def wet(self):
        return self.stages[0].wet if self.stages else 0
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

ksppath = os.environ.get('KSPPATH')
known_props = {}
if ksppath is not None:
    try:
        with open(os.path.join(ksppath, 'GameData', 'ModuleManager.ConfigCache'), 'r') as f:
            d = cfg.parse(f)
            d = d.get('UrlConfig', {})
            for c in d:
                if 'RESOURCE_DEFINITION' in c:
                    r = c['RESOURCE_DEFINITION']
                    for rd in r:
                        if 'name' in rd and 'density' in rd:
                            known_props[rd['name']] = float(rd['density'])
    except IOError:
        pass

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
