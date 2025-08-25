#!/usr/bin/python3
# For computing how much delta-V your rocket has left, and other goodness

import math
import json
import os
import cfg

resid = False # Incorporate 1% propellant residuals into calculations

class Propellant(object):
    def __init__(self, name, volume, density, mainEngine, filled=None, ratio=None):
        self.name = name
        self.volume = volume
        self.filled = volume if filled is None else filled
        self.density = density
        self.mainEngine = mainEngine
        self.ratio = ratio
    @classmethod
    def clone(cls, other):
        return cls(other.name, other.volume, other.density, other.mainEngine, other.filled)
    @property
    def mass(self):
        return self.filled * self.density
    @property
    def full_mass(self):
        return self.volume * self.density
    @property
    def residuals(self): # assume 1% typical; in fact it varies between engines
        return self.full_mass * 0.01 if resid else 0.0
    def __str__(self):
        return self.name if self.mainEngine else '(%s)'%(self.name,)
    @classmethod
    def from_dict(cls, d):
        name = d['name']
        if 'density' not in d:
            d['density'] = known_props[name]
        return cls(name, d['volume'], d['density'], d.get('mainEngine', True), ratio=d.get('ratio'))

class Stage(object):
    def __init__(self, props, isp, dry, thrust=None, minThrottle=100.0):
        self.props = list(props) # list of Propellant instances
        check = [p.name for p in props]
        if len(check) != len(set(check)):
            raise Exception("A propellant name was repeated within a stage, we don't like that")
        self.isp = isp # I_sp(Vac) of main engine, in seconds
        self.thrust = thrust # Thrust(Vac) of main engine, in kN.  Optional
        self.minThrottle = minThrottle # Minimum throttle, in %
        self._dry = dry # stage dry mass, in tons
        self._load = None
        self.mfrac = {}
        full_m = sum(p.full_mass for p in self.props if p.mainEngine)
        full_r = sum(p.ratio * p.density for p in self.props if p.mainEngine and p.ratio is not None)
        for p in self.props:
            if not p.mainEngine: continue
            if p.ratio is not None:
                self.mfrac[p.name] = p.ratio * p.density / full_r
            else:
                self.mfrac[p.name] = p.full_mass / full_m
    @classmethod
    def clone(cls, other): # does not clone link to payload!
        return cls([Propellant.clone(prop) for prop in other.props], other.isp, other._dry, other.thrust, other.minThrottle)
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
    def twr(self): # thrust to weight ratio, in m/s^2
        if self.thrust is None: return None
        return self.thrust / self.wet
    @property
    def veff(self): # effective exhaust velocity, in m/s
        return self.isp * 9.80665
    @property
    def is_empty(self):
        if self.thrust == 0: return True # Always stage straight past this, it's dead weight
        # Engines generally won't run if <0.01 in the tank
        return any(p.mass - p.residuals <= 0 for p in self.props if p.mainEngine)
    @property
    def prop_mass(self):
        return sum(p.mass for p in self.props if p.mainEngine)
    @property
    def wet(self):
        return self.dry + self.prop_mass
    @property
    def deltaV(self):
        if self.thrust in (0, None): return 0 # dead weight
        if self.veff in (0, None): return 0 # dead weight
        bt = self.burn_time(1.0)
        mdot = self.thrust / self.veff # tons/s
        residue = sum((p.filled - mdot * self.mfrac[p.name] * bt / p.density) * p.density
                      for p in self.props if p.mainEngine)
        mr = self.wet / (residue + float(self.dry))
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
    def burn_time(self, throttle):
        if self.thrust is None: return None
        if self.thrust == 0: return 0
        throttle = self.convert_throttle(throttle)
        if throttle is None: return None
        mdot = self.thrust * throttle / self.veff # tons/s
        if mdot <= 0: return None
        return min((p.filled * p.density - p.residuals) / (mdot * self.mfrac[p.name])
                   for p in self.props if p.mainEngine)
    def convert_throttle(self, throttle):
        if throttle is None: return None
        if throttle == 0: return 0
        minThrottle = self.minThrottle / 100.0
        return (throttle * (1.0 - minThrottle)) + minThrottle
    def simulate(self, throttle, dt):
        if self.thrust is None: return None
        if self.thrust == 0: return 0
        throttle = self.convert_throttle(throttle)
        if throttle is None: return None
        dm = self.thrust * throttle * dt / self.veff # kN * s / (m / s) = kN * s^2 / m = tons
        mtot = self.prop_mass
        if mtot <= 0:
            return 0
        max_dm = dm
        for p in self.props:
            if not p.mainEngine: continue
            need = dm * self.mfrac[p.name] / p.density
            fr = p.filled - p.residuals
            if need > p.filled and need > 0:
                max_dm = min(max_dm, dm * fr / need)
        for p in self.props:
            if not p.mainEngine: continue
            p.filled -= max_dm * self.mfrac[p.name] / p.density
        mr = (mtot + self.dry) / self.wet
        lmr = math.log(mr)
        return self.veff * lmr
    @classmethod
    def from_dict(cls, d):
        return cls([Propellant.from_dict(p) for p in d['props']], d['isp'], d['dry'], d.get('thrust'), d.get('minThrottle', 100.0))

class Booster(object):
    def __init__(self, stages):
        self.stages = list(stages) # list of Stage instances
        for i in range(len(self.stages) - 1, 0, -1):
            self.stages[i - 1].add_payload(self.stages[i])
    @classmethod
    def clone(cls, other):
        if other is None:
            return cls([])
        return cls([Stage.clone(stage) for stage in other.stages])
    @property
    def twr(self): # thrust to weight ratio, in m/s^2
        return self.stages[0].twr if self.stages else 0
    def convert_throttle(self, throttle):
        return self.stages[0].convert_throttle(throttle) if self.stages else throttle
    def stage(self):
        if self.stages:
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
    def simulate(self, throttle, dt, stagecap=0):
        if len(self.stages) <= stagecap: return 0
        dv = self.stages[0].simulate(throttle, dt)
        if self.stages[0].is_empty:
            self.stage()
        return dv
    @classmethod
    def from_dict(cls, d):
        return cls([Stage.from_dict(s) for s in d])
    @classmethod
    def from_json(cls, j):
        d = json.loads(j)
        return cls.from_dict(d)

class FakeBooster(object):
    """Implements enough of the Booster API for use in xfer console

    Models a constant TMR of 10m/s^2."""
    stages = []
    @classmethod
    def clone(cls, other):
        return cls()
    @property
    def all_props(self):
        return []
    def stage(self):
        return
    def convert_throttle(self, throttle):
        return throttle
    @property
    def deltaV(self):
        return 10000
    def simulate(self, throttle, dt, stagecap=0):
        return dt * 10

known_props = {}
config = cfg.get_default_config()
if config is not None:
    d = config.get('UrlConfig', {})
    for c in d:
        if 'RESOURCE_DEFINITION' in c:
            r = c['RESOURCE_DEFINITION']
            for rd in r:
                if 'name' in rd and 'density' in rd:
                    known_props[rd['name']] = float(rd['density'])

if __name__ == '__main__':
    import sys
    resid = '-e' in sys.argv[1:]
    j = sys.stdin.read()
    b = Booster.from_json(j)
    print("Wet mass: %.3ft"%(b.wet,))
    print("Delta-V : %.3fm/s"%(b.deltaV,))
    print("Breakdown by Stage")
    for i,s in enumerate(b.stages):
        print("  Stage %d:"%(i,))
        print("    Wet mass: %.3ft"%(s.wet - s.load,))
        print("    Dry mass: %.3ft"%(s.dry - s.load,))
        if s.load:
            print("    Nxt mass: %.3ft"%(s.load,))
        print("    Delta-V : %.3fm/s"%(s.deltaV,))
