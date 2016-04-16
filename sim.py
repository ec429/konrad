#!/usr/bin/python
# Simulation engine for RetroSim

import math
import booster

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
        self.has_data = False
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
        self.hs = hs
        self.vs = vs
        self.act_mode = self.mode
        # time step, in seconds
        self.dt = 1
    def encode(self):
        d = {'time': self.t, 'alt': self.alt, 'x': self.downrange,
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
            if self.orbitals and self.bgm is not None:
                # Vcirc at current altitude
                sma = self.brad + self.alt
                self.tgt_obt_vel = math.sqrt(self.bgm / sma)
        if self.surface:
            if self.ground_map is not None:
                mlat = int(round(math.degrees(self.lat) * 2))
                mlon = int(round(math.degrees(self.lon) * 2)) % 720
                if mlon >= 360: mlon -= 720
                elif mlon < -360: mlon += 720
                self.local_ground_alt = self.ground_map[mlon][mlat]
            elif self.ground_alt is not None:
                self.local_ground_alt = self.ground_alt
            else:
                self.local_ground_alt = 0
        if self.hs <= 0 and self.act_mode == self.MODE_RETROGRADE:
            self.act_mode = self.MODE_VL
