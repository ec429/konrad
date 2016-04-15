#!/usr/bin/python
# Simulation engine for RetroSim

import math
import booster

class RocketSim(object):
    MODE_FIXED = 0
    MODE_PROGRADE = 1
    MODE_RETROGRADE = 2
    MODE_VL = 3
    def __init__(self, ground_alt=None, ground_map=None, mode=0, debug=False):
        self.has_data = False
        self.ground_alt = ground_alt
        self.ground_map = ground_map
        self.mode = mode
        self.stagecap = 0
        self.debug = debug
    def sim_setup(self, bstr, hs, vs, alt, throttle, pit, hdg, lat, lon, brad, bgm):
        self.booster = booster.Booster.clone(bstr)
        self.alt = alt
        # components of unit thrust
        pitch = math.radians(pit)
        self.cy = math.sin(pitch)
        self.cx = -math.cos(pitch)
        # components of unit 'x', assumes hdg is retrograde
        heading = math.radians(hdg)
        self.clat = -math.cos(heading)
        self.clong = -math.sin(heading)
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
        # time step, in seconds
        self.dt = 1
    def encode(self):
        return {'time': self.t, 'alt': self.alt - self.local_ground_alt, 'x': self.downrange,
                'hs': self.hs, 'vs': self.vs,
                'lat': math.degrees(self.lat), 'lon': math.degrees(self.lon)}
    def step(self):
        hs0 = self.hs
        vs0 = self.vs
        alt0 = self.alt
        self.t += self.dt
        dv = self.booster.simulate(self.throttle, self.dt, stagecap=self.stagecap)
        if self.mode != self.MODE_FIXED:
            vel = math.hypot(self.hs, self.vs)
            if vel > 0:
                if self.mode == self.MODE_PROGRADE:
                    self.cx = self.hs / vel
                    self.cy = self.vs / vel
                elif self.mode == self.MODE_RETROGRADE:
                    self.cx = -self.hs / vel
                    self.cy = -self.vs / vel
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
        if self.hs <= 0 and self.mode == self.MODE_RETROGRADE:
            self.mode = self.MODE_VL
        if self.mode == self.MODE_VL:
            # Pitch for vertical descent
            twr = self.booster.twr
            if twr > abs(self.hs):
                self.cx = -self.hs / twr
                self.cy = math.sqrt(1 - self.cx*self.cx)
            else:
                self.cx = 0
                self.cy = 1
