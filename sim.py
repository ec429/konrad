#!/usr/bin/python
# Simulation engine for RetroSim and AscentSim

import math
import booster
import matrix
import orbit

class SimulationException(Exception): pass

class RocketSim(object):
    MODE_FIXED = 0
    MODE_PROGRADE = 1
    MODE_RETROGRADE = 2
    MODE_VL = 3
    @classmethod
    def modename(cls, mode):
        return {cls.MODE_FIXED: "Fixed", cls.MODE_PROGRADE: "Progd",
                cls.MODE_RETROGRADE: "Retro", cls.MODE_VL: "VertL",
                }.get(mode, "%r?"%(mode,))
    surface = False
    orbitals = False
    def __init__(self, ground_alt=None, ground_map=None, mode=0, debug=False):
        self.data = {}
        self.ground_alt = ground_alt
        self.ground_map = ground_map
        self.mode = mode
        self.stagecap = 0
        self.debug = debug
    def sim_setup(self, bstr, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm, retro):
        self.booster = booster.Booster.clone(bstr)
        self.alt = alt
        # components of unit thrust
        pitch = math.radians(pit)
        self.cy = math.sin(pitch)
        if retro:
            self.cx = -math.cos(pitch)
        else:
            self.cx = math.cos(pitch)
        # components of unit 'x', assumes hdg is prograde (or retrograde if retro)
        heading = math.radians(hdg)
        if retro:
            self.clat = -math.cos(heading)
            self.clong = -math.sin(heading)
        else:
            self.clat = math.cos(heading)
            self.clong = math.sin(heading)
        # state
        self.downrange = 0
        self.t = 0
        self.local_ground_alt = self.ground_alt
        self.lat = math.radians(lat)
        self.lon = math.radians(lon)
        self.throttle = throttle
        self.brad = brad
        self.bgm = bgm
        self.pbody = orbit.ParentBody(brad, bgm)
        self.hs = hs
        self.vs = vs
        self.act_mode = self.mode
        # time step, in seconds
        self.dt = 1.0
    def encode(self):
        d = {'time': self.t, 'alt': self.alt, 'downrange': self.downrange,
             'hs': self.hs, 'vs': self.vs,
             'lat': math.degrees(self.lat), 'lon': math.degrees(self.lon)}
        if self.surface:
            if self.local_ground_alt is not None:
                d['height'] = self.alt - self.local_ground_alt
        return d
    def step(self):
        hs0 = self.hs
        vs0 = self.vs
        alt0 = self.alt
        self.t += self.dt
        dv = self.booster.simulate(self.throttle, self.dt, stagecap=self.stagecap)
        if dv is None:
            return True
        if self.act_mode == self.MODE_FIXED:
            pass
        elif self.act_mode == self.MODE_PROGRADE:
            vel = math.hypot(self.hs, self.vs)
            if vel > 0:
                self.cx = self.hs / vel
                self.cy = self.vs / vel
        elif self.act_mode == self.MODE_RETROGRADE:
            vel = math.hypot(self.hs, self.vs)
            if vel > 0:
                self.cx = -self.hs / vel
                self.cy = -self.vs / vel
        elif self.act_mode == self.MODE_VL:
            # Pitch for vertical descent
            twr = self.booster.twr
            if twr > abs(self.hs):
                self.cx = -self.hs / twr
                self.cy = math.sqrt(1 - self.cx*self.cx)
            else:
                self.cx = 0
                self.cy = 1
        else:
            raise Exception("Unhandled mode", self.mode)
        dhs = dv * self.cx
        dvs = dv * self.cy
        self.hs += dhs
        # local gravity
        if None in (self.alt, self.brad, self.bgm):
            g = 0
        else:
            g = self.bgm / (self.alt + self.brad)**2
        self.vs += dvs - (g * self.dt)
        self.alt += (self.vs + vs0) / 2.0
        mhs = (self.hs + hs0) / 2.0
        self.downrange += mhs
        if self.brad is not None:
            # update lat & long
            self.lat += mhs * self.clat / (self.brad + self.alt)
            if abs(self.lat) > (math.pi / 2):
                if self.lat > 0:
                    # crossed north pole
                    self.lat = math.pi - self.lat
                else:
                    # crossed south pole
                    self.lat = -math.pi - self.lat
                self.lon += math.pi
                # heading switches around too
                self.clat = -self.clat
                self.clong = -self.clong
            self.lon += mhs * self.clong / ((self.brad + self.alt) * math.cos(self.lat))
            self.lon %= (math.pi * 2)
            # transform our velocity - planet is curving away beneath us
            rot = mhs / (self.brad + self.alt)
            nhs = self.hs * math.cos(rot) - self.vs * math.sin(rot)
            nvs = self.hs * math.sin(rot) + self.vs * math.cos(rot)
            self.hs, self.vs = nhs, nvs
            if self.orbitals:
                # Vcirc at current altitude
                self.tgt_obt_vel = self.pbody.vcirc(self.alt)
        if self.surface:
            if self.ground_map is not None:
                mlat = int(round(math.degrees(self.lat) * 2))
                mlon = int(round(math.degrees(self.lon) * 2)) % 720
                mlat = min(mlat, 179)
                if mlon >= 360: mlon -= 720
                elif mlon < -360: mlon += 720
                self.local_ground_alt = self.ground_map[mlon][mlat]
            elif self.ground_alt is not None:
                self.local_ground_alt = self.ground_alt
            else:
                self.local_ground_alt = 0
        if self.hs <= 0 and self.act_mode == self.MODE_RETROGRADE:
            self.act_mode = self.MODE_VL
    def compute_elements(self, key):
        if key in self.data:
            sv = self.data[key]
            if 'alt' in sv and 'vs' in sv and 'hs' in sv:
                elts = self.pbody.compute_elements(sv['alt'], sv['vs'], sv['hs'])
                self.data[key].update(elts)

class RocketSim3D(object):
    MODE_FIXED = 0
    MODE_PROGRADE = 1
    MODE_RETROGRADE = 2
    MODE_LIVE = 3
    MODE_INERTIAL = 4
    MODE_LIVE_INERTIAL = 5
    @classmethod
    def modename(cls, mode):
        return {cls.MODE_FIXED: "Fixed", cls.MODE_PROGRADE: "Progd",
                cls.MODE_RETROGRADE: "Retro", cls.MODE_LIVE: "LiveF",
                cls.MODE_INERTIAL: "Inert", cls.MODE_LIVE_INERTIAL: "LiveI",
                }.get(mode, "%r?"%(mode,))
    def __init__(self, mode=0, debug=False, ground_alt=None, ground_map=None):
        self.data = {}
        self.ground_alt = ground_alt
        self.ground_map = ground_map
        self.mode = mode
        self.stagecap = 0
        self.debug = debug
        self.reflon = None
        self.force_ground_alt = None
    def sim_setup(self, bstr, throttle, pit, hdg, brad, bgm, inc, lan, ean, ape, ecc, sma):
        self.booster = bstr.__class__.clone(bstr)
        self.pbody = orbit.ParentBody(brad, bgm)
        self.pit = pit
        self.hdg = hdg
        # orbital state vector
        self.rvec, self.vvec = self.pbody.compute_3d_vector(sma, ecc, ean, ape, inc, lan)
        self.point(pit, hdg)
        self.t = 0
        self.init_rvec = self.rvec
        self.throttle = throttle
        self.act_mode = self.mode
        # time step, in seconds
        self.dt = 1.0
        # Total expended delta-V
        self.total_dv = 0
    def set_reflon(self, lon):
        if lon is None:
            self.reflon = None
            return
        self.reflon = lon + self.lon
    def point(self, pit, hdg):
        # pointing vector in local co-ordinates
        pvec = matrix.Vector3((math.sin(pit),
                               math.sin(hdg) * math.cos(pit),
                               math.cos(hdg) * math.cos(pit)))
        self.pvec = matrix.RotationMatrix(2, self.lon) * matrix.RotationMatrix(1, -self.lat) * pvec
    @property
    def alt(self):
        return self.rvec.mag - self.pbody.rad
    @property
    def downrange(self):
        return (self.rvec - self.init_rvec).mag
    @property
    def hv(self):
        return self.vvec.cross(self.rvec.hat)
    @property
    def hs(self):
        return self.hv.mag
    @property
    def vs(self):
        return self.vvec.dot(self.rvec.hat)
    @property
    def lon(self):
        return math.atan2(self.rvec.hat.y, self.rvec.hat.x)
    @property
    def lat(self):
        return math.asin(self.rvec.hat.z)
    @property
    def ground_lon(self):
        if self.reflon is None:
            return None
        return self.reflon - self.lon
    @property
    def local_ground_alt(self):
        if self.force_ground_alt:
            return self.force_ground_alt
        gl = self.ground_lon
        if self.ground_map is not None and gl is not None:
            mlat = int(round(math.degrees(self.lat) * 2))
            mlon = int(round(math.degrees(gl) * 2)) % 720
            mlat = min(mlat, 179)
            if mlon >= 360: mlon -= 720
            elif mlon < -360: mlon += 720
            return self.ground_map[mlon][mlat]
        if self.ground_alt is not None:
            return self.ground_alt
        return 0
    def encode(self):
        d = {'time': self.t, 'alt': self.alt, 'downrange': self.downrange,
             'hs': self.hs, 'vs': self.vs,
             'rvec': self.rvec, 'vvec': self.vvec,
             'lat': self.lat, 'lon': self.lon,
             'dV': self.total_dv, 'ground_lon': self.ground_lon,
             'height': self.alt - self.local_ground_alt,
             }
        return dict((k,v) for k,v in d.iteritems() if v is not None)
    def step(self):
        self.t += self.dt
        dv = self.booster.simulate(self.throttle, self.dt, stagecap=self.stagecap)
        if dv is None:
            return True
        self.total_dv += dv
        if self.act_mode in (self.MODE_INERTIAL, self.MODE_LIVE_INERTIAL):
            pass
        elif self.act_mode in (self.MODE_FIXED, self.MODE_LIVE):
            self.point(self.pit, self.hdg)
        elif self.act_mode == self.MODE_PROGRADE:
            self.pvec = self.vvec.hat
        elif self.act_mode == self.MODE_RETROGRADE:
            self.pvec = -1.0 * self.vvec.hat
        else:
            raise Exception("Unhandled mode", self.mode)
        self.rvec += self.dt * self.vvec
        avec = dv * self.pvec
        # local gravity
        if None not in (self.alt, self.pbody.gm):
            g = -self.pbody.gm / self.rvec.mag ** 2
            avec += (g * self.dt) * self.rvec.hat
        self.vvec += avec
    def compute_elements(self, key):
        if key in self.data:
            sv = self.data[key]
            if 'rvec' in sv and 'vvec' in sv:
                elts = self.pbody.compute_3d_elements(sv['rvec'], sv['vvec'])
                sv.update(elts)
            vvec = sv.get('vvec')
            lat = sv.get('lat')
            lon = sv.get('lon')
            if None not in (vvec, lat, lon):
                # compute obtHeading
                iM = matrix.RotationMatrix(1, lat) * matrix.RotationMatrix(2, -lon)
                lv = iM * vvec.hat
                oh = math.atan2(lv.y, lv.z)
                sv['oh'] = oh
