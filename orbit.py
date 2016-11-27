#!/usr/bin/python
# Calculations for target orbits

import math
import matrix

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
        data = {'sma': sma, 'ecc': ecc,
                'apa': apa - self.rad,
                'pea': pea - self.rad}
        try:
            # period T = 2pi sqrt(a^3 / mu)
            per = 2.0 * math.pi * math.sqrt(sma ** 3 / self.gm)
            data['per'] = per
        except ValueError:
            pass
        try:
            # anomalies (since periapsis)
            # eccentric anomaly E: e cos E = 1 - (r/a)
            # sgn(vs) == sgn(sin E)
            ecosE = 1.0 - (r / sma)
            ean = math.acos(ecosE / ecc)
            if vs < 0: ean += math.pi
            data['ean'] = ean
            # mean anomaly M = E - e sin E
            data['man'] = ean - ecc * math.sin(ean)
            # true anomaly J
            tan = tra_from_ean(ean, ecc)
            data['tan'] = tan
        except ValueError:
            pass
        return data
    def compute_3d_elements(self, rvec, vvec):
        # Compute 3D elements from 3D state vector
        ### uses eqns from https://downloads.rene-schwarz.com/download/M002-Cartesian_State_Vectors_to_Keplerian_Orbit_Elements.pdf
        # specific orbital energy, epsilon = v.v / 2 - mu / |r|
        soe = vvec.dot(vvec) / 2.0 - self.gm / rvec.mag
        # a = -mu / 2epsilon
        sma = -self.gm / (2.0 * soe)
        # specific angular momentum
        # h = r x v
        sam = rvec.cross(vvec)
        # eccentricity vector
        # e = v x h / mu - rhat
        evec = (1.0 / self.gm) * vvec.cross(sam) - rvec.hat
        # eccentricity = |e|
        ecc = evec.mag
        apa = (1 + ecc) * sma
        pea = (1 - ecc) * sma
        data = {'sma': sma, 'ecc': ecc,
                'apa': apa - self.rad,
                'pea': pea - self.rad}
        # vector to ascending node
        n = matrix.Vector3((-sam.y, sam.x, 0))
        # mean motion n = sqrt(mu / a^3)
        mmo = math.sqrt(self.gm / sma ** 3)
        data['mmo'] = mmo
        # period T = 2pi / n
        per = 2.0 * math.pi / mmo
        data['per'] = per
        # anomalies (since periapsis)
        if ecc == 0:
            tan = 0
            ean = 0
        else:
            # true anomaly nu
            tan = angle_between(evec.hat, rvec.hat)
            if vvec.dot(rvec) < 0:
                tan = 2.0 * math.pi - tan
            # eccentric anomaly E = 2 arctan(tan(nu/2)/sqrt((1+e)/(1-e)))
            ean = ean_from_tan(tan, ecc)
        data['tan'] = tan
        data['ean'] = ean
        # mean anomaly M = E - e sin E
        data['man'] = ean - ecc * math.sin(ean)
        # inclination
        inc = angle_between(sam.hat, matrix.Vector3.ez())
        data['inc'] = inc
        # longitude of ascending node
        if n.mag == 0:
            lan = ean
        else:
            lan = angle_between(n.hat, matrix.Vector3.ex())
            if n.y < 0:
                lan = 2.0 * math.pi - lan
        data['lan'] = lan
        # argument of periapsis
        if ecc == 0:
            ape = 2.0 * math.pi - lan
        elif n.mag == 0:
            ape = 0
        else:
            ape = angle_between(n.hat, evec.hat)
            if evec.z < 0:
                ape = 2.0 * math.pi - ape
        data['ape'] = ape
        return data
    def compute_3d_vector(self, sma, ecc, tan, ape, inc, lan):
        ean = ean_from_tan(tan, ecc)
        o = ovec(sma, ecc, ean)
        od = odot(self.gm, sma, ecc, ean)
        xform = oxform(ape, inc, lan)
        r = xform * o
        v = xform * od
        return (r, v)

def ean_from_man(man, ecc, k):
    # Iterated approximation; k is number of iterations
    ean = man
    for i in xrange(k):
        ean = man + ecc * math.sin(ean)
    return ean

def ean_from_tan(tan, ecc):
    teh = math.tan(tan / 2.0) / math.sqrt((1.0 + ecc) / (1.0 - ecc))
    return 2 * math.atan(teh)

def tan_from_ean(ean, ecc):
    tjh = math.sqrt((1.0 + ecc) / (1.0 - ecc)) * math.tan(ean / 2.0)
    return 2 * math.atan(tjh)

def r(sma, ecc, ean):
    return sma * (1.0 - ecc * math.cos(ean))

### eqns from from https://downloads.rene-schwarz.com/download/M001-Keplerian_Orbit_Elements_to_Cartesian_State_Vectors.pdf

def ovec(sma, ecc, ean):
    tan = tan_from_ean(ean, ecc)
    rad = r(sma, ecc, ean)
    return rad * matrix.Vector3((math.cos(tan), math.sin(tan), 0))

def odot(gm, sma, ecc, ean):
    rad = r(sma, ecc, ean)
    sf = math.sqrt(gm * sma) / rad
    efac = math.sqrt(1.0 - ecc ** 2)
    return sf * matrix.Vector3((-math.sin(ean), efac * math.cos(ean), 0))

def oxform(ape, inc, lan):
    lanx = matrix.RotationMatrix(2, -lan)
    incx = matrix.RotationMatrix(0, -inc)
    apex = matrix.RotationMatrix(2, -ape)
    return lanx * incx * apex

###

def angle_between(w, z):
    # assumes w and z are unit vectors
    dot = sum(wi*zi for wi,zi in zip(w.data, z.data))
    return math.acos(dot)

if __name__ == "__main__":
    # round-trip test
    in_r = matrix.Vector3((40, 0, 20))
    in_v = matrix.Vector3((0, 1.0, 0.01))
    in_gm = 50
    in_rad = 0
    pbody = ParentBody(in_rad, in_gm)
    elts = pbody.compute_3d_elements(in_r, in_v)
    for k,v in elts.iteritems():
        if 'an' in k or k in 'mmo, inc, ape':
            v = math.degrees(v)
        print k, v
    print
    out_r, out_v = pbody.compute_3d_vector(elts['sma'], elts['ecc'], elts['tan'], elts['ape'], elts['inc'], elts['lan'])
    print out_r
    print out_v

if 0:
    out_r = x(elts['sma'], elts['ecc'], elts['ean'], elts['tan'], elts['inc'], elts['lan'], elts['ape'])
    out_v = xdot(elts['sma'], elts['lan'], elts['inc'], elts['ape'], elts['mmo'], elts['ean'], elts['tan'], elts['ecc'])
    print out_r
    print out_v
    tan = elts['tan']
    print tandot(elts['mmo'], elts['sma'], elts['ecc'], elts['ean'])
    elts['man'] += elts['mmo']
    elts['ean'] = ean_from_man(elts['man'], elts['ecc'], 12)
    elts['tan'] = tra_from_ean(elts['ean'], elts['ecc'])
    print elts['tan'] - tan
    print x(elts['sma'], elts['ecc'], elts['ean'], elts['tan'], elts['inc'], elts['lan'], elts['ape'])
