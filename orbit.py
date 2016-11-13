#!/usr/bin/python
# Calculations for target orbits

import math

class ParentBody(object):
    def __init__(self, rad, gm):
        self.rad = rad
        self.gm = gm
    def vcirc(self, alt):
        if self.rad is None: return None
        if alt is None: return None
        sma = self.rad + alt
        return self.vsma(sma)
    def vellip(self, peri, apo, alt):
        if None in (self.rad, self.gm):
            return None
        if None in (peri, apo, alt):
            return None
        sma = self.rad + (peri + apo) / 2.0
        # v = sqrt(mu * (2/r - 1/a))
        squared = self.gm * (2.0 / (alt + self.rad) - 1.0 / sma)
        return None if squared < 0 else math.sqrt(squared)
    def vsma(self, sma):
        if self.gm is None: return None
        if sma is None: return None
        if self.gm < 0: return None
        if sma <= 0: return None
        return math.sqrt(self.gm / sma)
    @classmethod
    def rad_api(cls, body):
        return "b.radius[%d]"%(body,)
    @classmethod
    def gm_api(cls, body):
        return "b.o.gravParameter[%d]"%(body,)
    def compute_soe(self, r, vs, hs):
        # specific orbital energy
        # v^2 / 2 - mu / r
        vv = hs ** 2 + vs ** 2
        return vv / 2.0 - self.gm / r
    def compute_elements(self, alt, vs, hs):
        # Compute 2D elements from 2D state vector
        r = alt + self.rad
        soe = self.compute_soe(r, vs, hs)
        # a = -mu / 2e
        sma = -self.gm / (2.0 * soe)
        # specific angular momentum
        # h~ = r~ x v~, and r~ = (0, 0, r) in local frame
        # so h = r * hs
        sam = hs * r
        # eccentricity
        # h^2 = a * mu * (1-e^2)
        ne = sam ** 2 / (sma * self.gm) # 1 - e^2
        ecc = math.sqrt(1 - ne)
        apa = (1 + ecc) * sma
        pea = (1 - ecc) * sma
        return {'sma': sma, 'ecc': ecc, 'apa': apa, 'pea': pea}
