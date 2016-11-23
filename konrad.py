#!/usr/bin/python

import downlink
import gauge
import curses, curses.ascii
import optparse
import math
import csv
import booster
import retro
import ascent
import burns
from copy import copy

class Console(object):
    group = None
    def __init__(self, opts, scr, dl):
        self.dl = dl
        self.dl.subscribe('b.number')
        self.status = gauge.StatusReadout(dl, scr.derwin(1, 78, 22, 1), 'status:')
    def input(self, key):
        if key == ord('('): # prev body
            if opts.body > 0:
                opts.body -= 1
                self.group.changeopt(gauge.Gauge, body=opts.body)
            return
        if key == ord(')'): # next body
            if opts.body + 1 < self.dl.get('b.number'):
                opts.body += 1
                self.group.changeopt(gauge.Gauge, body=opts.body)
            return
        if key == ord(curses.ascii.ctrl('X')):
            return True # exit
    @classmethod
    def connect_params(cls):
        return {}

class FDConsole(Console):
    """Flight Director's console"""
    def __init__(self, opts, scr, dl):
        super(FDConsole, self).__init__(opts, scr, dl)
        props = len(opts.propellant)
        fuel = scr.derwin(2 + props, 26, 14 - props, 53)
        fuelgroup = gauge.GaugeGroup(fuel, [
            gauge.FuelGauge(dl, fuel.derwin(1, 24, i + 1, 1), p)
            for i,p in enumerate(opts.propellant)
            ], 'Propellants')
        obt = scr.derwin(6, 26, 16, 53)
        obtgroup = gauge.GaugeGroup(obt, [
            gauge.AltitudeGauge(dl, obt.derwin(1, 24, 1, 1), opts.body),
            gauge.PeriapsisGauge(dl, obt.derwin(1, 24, 2, 1), opts.body),
            gauge.ApoapsisGauge(dl, obt.derwin(1, 24, 3, 1)),
            gauge.ObtVelocityGauge(dl, obt.derwin(1, 24, 4, 1), opts.body),
            ], 'Orbital')
        xcons = len(opts.consumable)
        strs = scr.derwin(4 + opts.reentry, 27, 15 - opts.reentry - xcons, 1)
        heat = [gauge.HeatingGauge(dl, strs.derwin(1, 25, 3, 1))] if opts.reentry else []
        strsgroup = gauge.GaugeGroup(strs, [
            gauge.GeeGauge(dl, strs.derwin(1, 25, 1, 1)),
            gauge.DynPresGauge(dl, strs.derwin(1, 25, 2, 1)),
            ] + heat,
            'Stresses')
        capsystitle = 'Avionics' if opts.unmanned else 'Capsys'
        capsys = scr.derwin(3 + xcons, 27, 19 - xcons, 1)
        capsysgroup = gauge.GaugeGroup(capsys,
            [gauge.FuelGauge(dl, capsys.derwin(1, 25, 1 + i, 1), c) for i,c in enumerate(opts.consumable)] + [
            gauge.Light(dl, capsys.derwin(1, 6, 1 + xcons, 1), 'SAS', 'v.sasValue'),
            gauge.Light(dl, capsys.derwin(1, 6, 1 + xcons, 7), 'RCS', 'v.rcsValue'),
            gauge.VLine(dl, capsys.derwin(1, 1, 1 + xcons, 13)),
            gauge.Light(dl, capsys.derwin(1, 6, 1 + xcons, 14), 'GEAR', 'v.gearValue'),
            gauge.Light(dl, capsys.derwin(1, 6, 1 + xcons, 20), 'BRK', 'v.brakeValue'),
            ], capsystitle)
        orient = scr.derwin(13, 25, 9, 28)
        origroup = gauge.GaugeGroup(orient, [
            gauge.NavBall(dl, orient.derwin(11, 23, 1, 1)),
            ], 'Orientation')
        body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        self.group = gauge.GaugeGroup(scr,
                                      [fuelgroup, obtgroup, strsgroup, capsysgroup, origroup,
                                       self.status, body, time],
                                      "KONRAD: FD Console")
    def input(self, key):
        if key >= ord('0') and key <= ord('9'):
            i = int(chr(key))
            if i == 0: i = 10
            self.dl.send_msg({'run':['f.ag%d'%(i,)]})
            return
        if key == ord('t'):
            self.dl.send_msg({'run':['f.sas']})
            return
        if key == ord('r'):
            self.dl.send_msg({'run':['f.rcs']})
            return
        if key == ord('g'):
            self.dl.send_msg({'run':['f.gear']})
            return
        if key == ord('b'):
            self.dl.send_msg({'run':['f.brake']})
            return
        if key == ord('!'):
            self.dl.send_msg({'run':['f.abort']})
            return
        if key == ord(' '):
            self.dl.send_msg({'run':['f.stage']})
            return
        return super(FDConsole, self).input(key)

class TrajConsole(Console):
    """Trajectory console"""
    def __init__(self, opts, scr, dl):
        super(TrajConsole, self).__init__(opts, scr, dl)
        self.want = {'PIT': 90, 'HDG': 90, 'RLL': 0, 'mode': 'Off'}
        loxn = scr.derwin(6, 27, 8, 52)
        loxngroup = gauge.GaugeGroup(loxn, [
            gauge.LongitudeGauge(dl, loxn.derwin(1, 12, 1, 1)),
            gauge.LatitudeGauge(dl, loxn.derwin(1, 12, 1, 14)),
            gauge.DownrangeGauge(dl, loxn.derwin(1, 25, 2, 1), opts.body, opts.init_lat, opts.init_long),
            gauge.BearingGauge(dl, loxn.derwin(1, 12, 3, 1), opts.body, opts.init_lat, opts.init_long),
            gauge.LandingPointGauge(dl, loxn.derwin(1, 12, 3, 14)),
            gauge.TerrainAltitudeGauge(dl, loxn.derwin(1, 25, 4, 1)),
            ], 'Location')
        obt = scr.derwin(8, 27, 14, 52)
        obtgroup = gauge.GaugeGroup(obt, [
            gauge.AltitudeGauge(dl, obt.derwin(1, 25, 1, 1), opts.body, target=opts.target_alt),
            gauge.PeriapsisGauge(dl, obt.derwin(1, 25, 2, 1), opts.body, target=opts.target_peri or opts.target_alt),
            gauge.ApoapsisGauge(dl, obt.derwin(1, 25, 3, 1), target=opts.target_apo or opts.target_alt),
            gauge.ObtVelocityGauge(dl, obt.derwin(1, 25, 4, 1), opts.body, target_alt=opts.target_alt, target_apo=opts.target_apo, target_peri=opts.target_peri),
            gauge.ObtPeriodGauge(dl, obt.derwin(1, 25, 5, 1)),
            gauge.InclinationGauge(dl, obt.derwin(1, 25, 6, 1)),
            ], 'Orbital')
        shift = 3 if opts.mj else 0
        motion = scr.derwin(5, 34, 13 - shift, 1)
        mogroup = gauge.GaugeGroup(motion, [
            gauge.ClimbAngleGauge(dl, motion.derwin(1, 16, 1, 1)),
            gauge.HSpeedGauge(dl, motion.derwin(1, 16, 2, 1)),
            gauge.SrfSpeedGauge(dl, motion.derwin(1, 16, 3, 1)),
            gauge.VLine(dl, motion.derwin(3, 1, 1, 17)),
            gauge.AoAGauge(dl, motion.derwin(1, 15, 1, 18), opts.retrograde),
            gauge.VSpeedGauge(dl, motion.derwin(1, 15, 2, 18)),
            gauge.GeeGauge(dl, motion.derwin(1, 15, 3, 18)),
            ], 'Motion-(Surface)')
        orient = scr.derwin(4, 34, 18 - shift, 1)
        origroup = gauge.GaugeGroup(orient, [
            gauge.PitchGauge(dl, orient.derwin(1, 10, 1, 1)),
            gauge.PitchRateGauge(dl, orient.derwin(1, 10, 2, 1)),
            gauge.VLine(dl, orient.derwin(2, 1, 1, 11)),
            gauge.HeadingGauge(dl, orient.derwin(1, 10, 1, 12)),
            gauge.HeadingRateGauge(dl, orient.derwin(1, 10, 2, 12)),
            gauge.VLine(dl, orient.derwin(2, 1, 1, 22)),
            gauge.RollGauge(dl, orient.derwin(1, 10, 1, 23)),
            gauge.RollRateGauge(dl, orient.derwin(1, 10, 2, 23)),
            ], 'Orientation')
        navball = scr.derwin(9, 17, 13 - shift, 35)
        navgroup = gauge.GaugeGroup(navball, [
            gauge.NavBall(dl, navball.derwin(7, 15, 1, 1)),
            ], "NavBall")
        if opts.mj:
            oriwant = scr.derwin(3, 34, 19, 1)
            owgroup = gauge.GaugeGroup(oriwant, [
                gauge.PitchGauge(dl, oriwant.derwin(1, 10, 1, 1), want=self.want),
                gauge.VLine(dl, oriwant.derwin(1, 1, 1, 11)),
                gauge.HeadingGauge(dl, oriwant.derwin(1, 10, 1, 12), want=self.want),
                gauge.VLine(dl, oriwant.derwin(1, 1, 1, 22)),
                gauge.RollGauge(dl, oriwant.derwin(1, 10, 1, 23), want=self.want),
                gauge.VariableLabel(dl, oriwant.derwin(1, 6, 0, 27), self.want, 'fineness', centered=True),
                ], 'Input Orientation')
            wm = scr.derwin(3, 17, 19, 35)
            wmgroup = gauge.GaugeGroup(wm, [
                gauge.MJMode(dl, wm.derwin(1, 15, 1, 1), self.want),
                ], 'AP Mode')
        body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        gauges = [loxngroup, obtgroup, mogroup, origroup, navgroup]
        if opts.mj:
            gauges += [owgroup, wmgroup]
        self.group = gauge.GaugeGroup(scr, gauges + [self.status, body, time], "KONRAD: Trajectory")
        self.setfine(0)
    def setfine(self, value):
        self.fine = value
        self.want['fineness'] = {0: 'COARSE', 1: 'NORMAL', 2: 'FINE'}.get(value, 'Error?')
    def maybe_push_mj(self):
        if opts.mj and self.want['mode'] == 'Fixed':
            cmd = 'mj.surface2[%f,%f,%f]'%(self.want['HDG'], self.want['PIT'], self.want['RLL'])
            self.want['reqm'] = cmd
            self.dl.send_msg({'run':[cmd]})
    def mj_mode(self, mode, api):
        self.want['mode'] = mode
        if opts.mj:
            self.want['reqm'] = api
            self.dl.send_msg({'run':[api]})
    def steer(self, what, base):
        old = self.want[what]
        sf = 10 ** -self.fine
        delta = base * sf
        if what == 'PIT':
            new = min(max(old + delta, -90), 90)
        else:
            new = (old + delta) % 360
        self.want[what] = new
    def input(self, key):
        if key == ord('<'):
            self.group.changeopt(gauge.AoAGauge, retro=True)
            return
        if key == ord('>'):
            self.group.changeopt(gauge.AoAGauge, retro=False)
            return
        # Input Orientation, for AP Fixed
        steering = {'d': ('HDG', 1),
                    'a': ('HDG', -1),
                    's': ('PIT', 1),
                    'w': ('PIT', -1),
                    'e': ('RLL', 1),
                    'q': ('RLL', -1)}
        if chr(key) in steering:
            what, base = steering[chr(key)]
            self.steer(what, base * 10)
            return self.maybe_push_mj()
        if chr(key).lower() in steering:
            what, base = steering[chr(key).lower()]
            self.steer(what, base)
            return self.maybe_push_mj()
        # Toggle fine controls
        if key == ord('`'):
            self.setfine((self.fine + 1) % 3)
            return
        # Copy from measured orientation
        if key == ord('?'):
            self.want['PIT'] = self.dl.get('n.pitch2', 90)
            self.want['HDG'] = self.dl.get('n.heading2', 90)
            self.want['RLL'] = self.dl.get('n.roll2', 0)
        # AP Modes
        if key == ord(' '):
            return self.mj_mode('None', 'mj.smartassoff')
        if key in [ord('\r'), ord('\n')]:
            self.want['mode'] = 'Fixed'
            return self.maybe_push_mj()
        if key == ord('P'):
            return self.mj_mode('Prograde', 'mj.prograde')
        if key == ord('R'):
            return self.mj_mode('Retrograde', 'mj.retrograde')
        if key == ord('O'): # 'O'utwards
            return self.mj_mode('Radial', 'mj.radialplus')
        if key == ord('I'): # 'I'nwards
            return self.mj_mode('Anti-Radial', 'mj.radialminus')
        if key == ord('+'):
            return self.mj_mode('Normal', 'mj.normalplus')
        if key == ord('-'):
            return self.mj_mode('Anti-Normal', 'mj.normalminus')

        return super(TrajConsole, self).input(key)

class BoosterConsole(Console):
    """Booster Dynamics console"""
    def __init__(self, opts, scr, dl):
        super(BoosterConsole, self).__init__(opts, scr, dl)
        self.update = gauge.UpdateBooster(dl, scr, opts.booster)
        props = len(opts.propellant)
        fuel = scr.derwin(2 + props, 26, 20 - props, 53)
        fuelgroup = gauge.GaugeGroup(fuel, [
            gauge.FuelGauge(dl, fuel.derwin(1, 24, i + 1, 1), p)
            for i,p in enumerate(opts.propellant)
            ], 'Propellants')
        ttap = gauge.TimeToApGauge(dl, scr.derwin(3, 16, 1, 12))
        deltav = gauge.DeltaVGauge(dl, scr.derwin(3, 23, 1, 28), opts.booster)
        throttle = gauge.ThrottleGauge(dl, scr.derwin(3, 17, 1, 51))
        stages = scr.derwin(18, 40, 4, 1)
        stagesgroup = gauge.GaugeGroup(stages, [
            gauge.StagesGauge(dl, stages.derwin(16, 38, 1, 1), opts.booster),
            ], 'Stages')
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        self.group = gauge.GaugeGroup(scr,
                                      [self.update, fuelgroup, ttap, deltav, throttle, stagesgroup,
                                       self.status, time],
                                      "KONRAD: Booster")
    def input(self, key):
        if key >= ord('1') and key <= ord('9'):
            i = int(chr(key))
            self.dl.send_msg({'run':['f.setThrottle[%f]'%(i/10.0,)]})
            return
        if key == ord('z'):
            self.dl.send_msg({'run':['f.setThrottle[1.0]']})
            return
        if key == ord('x'):
            self.dl.send_msg({'run':['f.setThrottle[0.0]']})
            return
        if key == ord(' '):
            self.dl.send_msg({'run':['f.stage']})
            return
        if key == ord('?'):
            self.update.reset()
            return
        return super(BoosterConsole, self).input(key)

class RetroConsole(Console):
    """Retrograde Propulsion console"""
    def __init__(self, opts, scr, dl):
        super(RetroConsole, self).__init__(opts, scr, dl)
        self.update = gauge.UpdateBooster(dl, scr, opts.booster)
        deltav = gauge.DeltaVGauge(dl, scr.derwin(3, 23, 1, 28), opts.booster)
        throttle = gauge.ThrottleGauge(dl, scr.derwin(3, 17, 1, 51))
        twr = gauge.TWRGauge(dl, scr.derwin(3, 16, 1, 12), opts.booster, opts.body)
        self.stagecap = 0
        self.mode = retro.RetroSim.MODE_FIXED
        self.vars = {}
        mode = gauge.VariableLabel(dl, scr.derwin(3, 15, 4, 25), self.vars, 'mode', centered=True)
        scap = gauge.VariableLabel(dl, scr.derwin(3, 15, 4, 40), self.vars, 'stagecap', centered=True)
        sim_blocks = []
        self.rs = [None, None]
        for i in xrange(2):
            y = i * 6
            use_throttle = not i
            rs = retro.RetroSim(ground_map=opts.ground_map, ground_alt=opts.ground_alt, mode=self.mode)
            self.rs[i] = rs
            sim = gauge.UpdateRocketSim(dl, scr, opts.body, opts.booster, use_throttle, False, rs)
            wtext = "At 100% throttle" if i else "At current throttle"
            wt = gauge.FixedLabel(dl, scr.derwin(1, 32, 7 + y, 1), wtext, centered=True)
            hwin = scr.derwin(5, 16, 8 + y, 1)
            h = gauge.GaugeGroup(hwin, [gauge.RSTime(dl, hwin.derwin(1, 14, 1, 1), 'h', rs),
                                        gauge.RSAlt(dl, hwin.derwin(1, 14, 2, 1), 'h', rs),
                                        gauge.RSDownrange(dl, hwin.derwin(1, 14, 3, 1), 'h', rs)],
                                 "Horizontal")
            vwin = scr.derwin(5, 16, 8 + y, 17)
            v = gauge.GaugeGroup(vwin, [gauge.RSTime(dl, vwin.derwin(1, 14, 1, 1), 'v', rs),
                                        gauge.RSAlt(dl, vwin.derwin(1, 14, 2, 1), 'v', rs),
                                        gauge.RSDownrange(dl, vwin.derwin(1, 14, 3, 1), 'v', rs)],
                                 "Vertical")
            swin = scr.derwin(6, 16, 7 + y, 33)
            s = gauge.GaugeGroup(swin, [gauge.RSTime(dl, swin.derwin(1, 14, 1, 1), 's', rs),
                                        gauge.RSDownrange(dl, swin.derwin(1, 14, 3, 1), 's', rs),
                                        gauge.RSVSpeed(dl, swin.derwin(1, 14, 2, 1), 's', rs),
                                        gauge.RSHSpeed(dl, swin.derwin(1, 14, 4, 1), 's', rs)],
                                 "Surface")
            bwin = scr.derwin(6, 16, 7 + y, 49)
            b = gauge.GaugeGroup(bwin, [gauge.RSTime(dl, bwin.derwin(1, 14, 1, 1), 'b', rs),
                                        gauge.RSAlt(dl, bwin.derwin(1, 14, 2, 1), 'b', rs),
                                        gauge.RSVSpeed(dl, bwin.derwin(1, 14, 3, 1), 'b', rs),
                                        gauge.RSHSpeed(dl, bwin.derwin(1, 14, 4, 1), 'b', rs)],
                                 "Burnout")
            twin = scr.derwin(4, 14, 7 + y, 65)
            t = gauge.GaugeGroup(twin, [gauge.RSLatitude(dl, twin.derwin(1, 12, 1, 1), 'sh', rs),
                                        gauge.RSLongitude(dl, twin.derwin(1, 12, 2, 1), 'sh', rs)],
                                 "Touchdown")
            sim_blocks.extend([sim, wt, h, v, s, b, t])
        alt = gauge.TerrainAltitudeGauge(dl, scr.derwin(3, 22, 19, 8))
        dh = gauge.DeltaHGauge(dl, scr.derwin(3, 22, 19, 30), opts.ground_map, opts.ground_alt)
        vs = gauge.VSpeedGauge(dl, scr.derwin(3, 21, 19, 52))
        body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        self.group = gauge.GaugeGroup(scr,
                                      [self.update, deltav, throttle, twr, mode, scap, alt, dh, vs] +
                                      sim_blocks +
                                      [self.status, body, time],
                                      "KONRAD: Retro")
        self.update_vars()
    def update_vars(self):
        self.vars['stagecap'] = 'Rsvd. Stg.: %d'%(self.stagecap,)
        self.vars['mode'] = 'Mode: %s'%(retro.RetroSim.modename(self.mode),)
        for i in xrange(2):
            if self.rs[i] is not None:
                self.rs[i].mode = self.mode
                self.rs[i].stagecap = self.stagecap
    def input(self, key):
        if key >= ord('1') and key <= ord('9'):
            i = int(chr(key))
            self.dl.send_msg({'run':['f.setThrottle[%f]'%(i/10.0,)]})
            return
        if key == ord('z'):
            self.dl.send_msg({'run':['f.setThrottle[1.0]']})
            return
        if key == ord('x'):
            self.dl.send_msg({'run':['f.setThrottle[0.0]']})
            return
        if key == ord(' '):
            self.dl.send_msg({'run':['f.stage']})
            return
        if key == ord('f'):
            self.mode = retro.RetroSim.MODE_FIXED
            self.update_vars()
            return
        if key == ord('r'):
            self.mode = retro.RetroSim.MODE_RETROGRADE
            self.update_vars()
            return
        if key == curses.KEY_PPAGE:
            self.stagecap += 1
            self.update_vars()
            return
        if key == curses.KEY_NPAGE:
            self.stagecap = max(self.stagecap - 1, 0)
            self.update_vars()
            return
        if key == ord('?'):
            self.update.reset()
            return
        return super(RetroConsole, self).input(key)
    @classmethod
    def connect_params(cls):
        return {'rate': 500} # update twice per second

class AscentConsole(Console):
    """Ascent Guidance console"""
    def __init__(self, opts, scr, dl):
        super(AscentConsole, self).__init__(opts, scr, dl)
        self.update = gauge.UpdateBooster(dl, scr, opts.booster)
        deltav = gauge.DeltaVGauge(dl, scr.derwin(3, 23, 1, 28), opts.booster)
        throttle = gauge.ThrottleGauge(dl, scr.derwin(3, 17, 1, 51))
        twr = gauge.TWRGauge(dl, scr.derwin(3, 16, 1, 12), opts.booster, opts.body)
        self.stagecap = 0
        self.mode = ascent.AscentSim.MODE_FIXED
        self.vars = {}
        mode = gauge.VariableLabel(dl, scr.derwin(3, 15, 4, 25), self.vars, 'mode', centered=True)
        scap = gauge.VariableLabel(dl, scr.derwin(3, 15, 4, 40), self.vars, 'stagecap', centered=True)
        sim_blocks = []
        self.rs = [None, None]
        for i in xrange(2):
            y = i * 6
            use_throttle = not i
            rs = ascent.AscentSim(mode=self.mode)
            self.rs[i] = rs
            sim = gauge.UpdateRocketSim(dl, scr, opts.body, opts.booster, use_throttle, True, rs)
            wtext = "At 100% throttle" if i else "At current throttle"
            wt = gauge.FixedLabel(dl, scr.derwin(1, 32, 7 + y, 1), wtext, centered=True)
            owin = scr.derwin(5, 16, 8 + y, 1)
            o = gauge.GaugeGroup(owin, [gauge.RSTime(dl, owin.derwin(1, 14, 1, 1), 'o', rs),
                                        gauge.RSAlt(dl, owin.derwin(1, 14, 2, 1), 'o', rs),
                                        gauge.RSVSpeed(dl, owin.derwin(1, 14, 3, 1), 'o', rs)],
                                 "Orb-Vel")
            vwin = scr.derwin(5, 16, 8 + y, 17)
            v = gauge.GaugeGroup(vwin, [gauge.RSTime(dl, vwin.derwin(1, 14, 1, 1), 'v', rs),
                                        gauge.RSAlt(dl, vwin.derwin(1, 14, 2, 1), 'v', rs),
                                        gauge.RSHSpeed(dl, vwin.derwin(1, 14, 3, 1), 'v', rs)],
                                 "Vertical")
            bwin = scr.derwin(6, 16, 7 + y, 33)
            b = gauge.GaugeGroup(bwin, [gauge.RSTime(dl, bwin.derwin(1, 14, 1, 1), 'b', rs),
                                        gauge.RSAlt(dl, bwin.derwin(1, 14, 2, 1), 'b', rs),
                                        gauge.RSVSpeed(dl, bwin.derwin(1, 14, 3, 1), 'b', rs),
                                        gauge.RSHSpeed(dl, bwin.derwin(1, 14, 4, 1), 'b', rs)],
                                 "Burnout")
            sim_blocks.extend([sim, wt, o, v, b])
        stages = scr.derwin(12, 30, 7, 49)
        stagesgroup = gauge.GaugeGroup(stages, [
            gauge.StagesGauge(dl, stages.derwin(10, 28, 1, 1), opts.booster),
            ], 'Stages')
        ttap = gauge.TimeToApGauge(dl, scr.derwin(3, 16, 19, 24))
        vs = gauge.VSpeedGauge(dl, scr.derwin(3, 32, 19, 40))
        body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        self.group = gauge.GaugeGroup(scr,
                                      [self.update, deltav, throttle, twr, mode, scap, stagesgroup, ttap, vs] +
                                      sim_blocks +
                                      [self.status, body, time],
                                      "KONRAD: Ascent")
        self.update_vars()
    def update_vars(self):
        self.vars['stagecap'] = 'Rsvd. Stg.: %d'%(self.stagecap,)
        self.vars['mode'] = 'Mode: %s'%(ascent.AscentSim.modename(self.mode),)
        for i in xrange(2):
            if self.rs[i] is not None:
                self.rs[i].mode = self.mode
                self.rs[i].stagecap = self.stagecap
    def input(self, key):
        if key >= ord('1') and key <= ord('9'):
            i = int(chr(key))
            self.dl.send_msg({'run':['f.setThrottle[%f]'%(i/10.0,)]})
            return
        if key == ord('z'):
            self.dl.send_msg({'run':['f.setThrottle[1.0]']})
            return
        if key == ord('x'):
            self.dl.send_msg({'run':['f.setThrottle[0.0]']})
            return
        if key == ord(' '):
            self.dl.send_msg({'run':['f.stage']})
            return
        if key == ord('f'):
            self.mode = ascent.AscentSim.MODE_FIXED
            self.update_vars()
            return
        if key == ord('p'):
            self.mode = ascent.AscentSim.MODE_PROGRADE
            self.update_vars()
            return
        if key == curses.KEY_PPAGE:
            self.stagecap += 1
            self.update_vars()
            return
        if key == curses.KEY_NPAGE:
            self.stagecap = max(self.stagecap - 1, 0)
            self.update_vars()
            return
        if key == ord('?'):
            self.update.reset()
            return
        return super(AscentConsole, self).input(key)
    @classmethod
    def connect_params(cls):
        return {'rate': 500} # update twice per second

class AstroConsole(Console):
    """Astrogation console"""
    def __init__(self, opts, scr, dl):
        super(AstroConsole, self).__init__(opts, scr, dl)
        self.update = gauge.UpdateBooster(dl, scr, opts.booster)
        deltav = gauge.DeltaVGauge(dl, scr.derwin(3, 23, 1, 28), opts.booster)
        twr = gauge.TWRGauge(dl, scr.derwin(3, 16, 1, 12), opts.booster, opts.body)
        self.stagecap = 0
        self.mode = burns.ManeuverSim.MODE_FIXED
        self.vars = {}
        mode = gauge.VariableLabel(dl, scr.derwin(3, 15, 4, 25), self.vars, 'mode', centered=True)
        scap = gauge.VariableLabel(dl, scr.derwin(3, 15, 4, 40), self.vars, 'stagecap', centered=True)
        self.ms = burns.ManeuverSim(ground_map=opts.ground_map, ground_alt=opts.ground_alt, mode=self.mode)
        sim = gauge.UpdateManeuverSim(dl, scr, opts.body, opts.booster, False, True, self.ms)
        elts = gauge.UpdateSimElements(dl, scr, self.ms, '0b')
        tgt = gauge.UpdateTgtProximity(dl, scr, self.ms, '0b', opts.target_body)
        zwin = scr.derwin(4, 16, 7, 1)
        z = gauge.GaugeGroup(zwin, [gauge.RSTime(dl, zwin.derwin(1, 14, 1, 1), '0', self.ms),
                                    gauge.RSAlt(dl, zwin.derwin(1, 14, 2, 1), '0', self.ms)],
                             "Start")
        bwin = scr.derwin(9, 16, 7, 17)
        b = gauge.GaugeGroup(bwin, [gauge.RSTime(dl, bwin.derwin(1, 14, 1, 1), 'b', self.ms),
                                    gauge.RSAlt(dl, bwin.derwin(1, 14, 2, 1), 'b', self.ms),
                                    gauge.RSVSpeed(dl, bwin.derwin(1, 14, 3, 1), 'b', self.ms),
                                    gauge.RSApoapsis(dl, bwin.derwin(1, 14, 4, 1), 'b', self.ms),
                                    gauge.RSPeriapsis(dl, bwin.derwin(1, 14, 5, 1), 'b', self.ms),
                                    gauge.RSObtPeriod(dl, bwin.derwin(1, 14, 6, 1), 'b', self.ms),
                                    gauge.RSTrueAnom(dl, bwin.derwin(1, 14, 7, 1), 'b', self.ms)],
                             "End")
        awin = scr.derwin(9, 16, 7, 33)
        a = gauge.GaugeGroup(awin, [gauge.RSTTAp(dl, awin.derwin(1, 14, 1, 1), 'b', self.ms),
                                    gauge.RSTgtDeltaMA(dl, awin.derwin(1, 14, 2, 1), 'b', self.ms),
                                    gauge.RSTrAp(dl, awin.derwin(1, 14, 3, 1), 'b', self.ms),
                                    gauge.RSTgtAlt(dl, awin.derwin(1, 14, 4, 1), 'b', self.ms),
                                    gauge.RSTgtPy(dl, awin.derwin(1, 14, 5, 1), 'b', self.ms),
                                    gauge.RSTgtTA(dl, awin.derwin(1, 14, 6, 1), 'b', self.ms),
                                    gauge.RSTgtMA(dl, awin.derwin(1, 14, 7, 1), 'b', self.ms)],
                             "Apo")
        twin = scr.derwin(9, 16, 7, 49)
        t = gauge.GaugeGroup(twin, [gauge.BodyNameGauge(dl, twin.derwin(1, 14, 1, 1), opts.target_body),
                                    gauge.PhaseAngleGauge(dl, twin.derwin(1, 14, 5, 1), opts.target_body),
                                    gauge.RelLanGauge(dl, twin.derwin(1, 14, 6, 1), opts.target_body),
                                    gauge.RelIncGauge(dl, twin.derwin(1, 14, 7, 1), opts.target_body)],
                             "Tgt")
        body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        self.group = gauge.GaugeGroup(scr,
                                      [self.update, deltav, twr, mode, scap,
                                       sim, elts, tgt, z, b, a, t,
                                       self.status, body, time],
                                      "KONRAD: Astrogation")
        self.update_vars()
    def update_vars(self):
        self.vars['stagecap'] = 'Rsvd. Stg.: %d'%(self.stagecap,)
        self.vars['mode'] = 'Mode: %s'%(burns.ManeuverSim.modename(self.mode),)
        if self.ms is not None:
            self.ms.mode = self.mode
            self.ms.stagecap = self.stagecap
    def input(self, key):
        if key == ord('z'):
            self.dl.send_msg({'run':['f.setThrottle[1.0]']})
            return
        if key == ord('x'):
            self.dl.send_msg({'run':['f.setThrottle[0.0]']})
            return
        if key == ord(' '):
            self.dl.send_msg({'run':['f.stage']})
            return
        if key == ord('f'):
            self.mode = burns.ManeuverSim.MODE_FIXED
            self.update_vars()
            return
        if key == ord('p'):
            self.mode = burns.ManeuverSim.MODE_PROGRADE
            self.update_vars()
            return
        if key == ord(')'):
            self.ms.burnUT += 1
            return
        if key == ord('('):
            self.ms.burnUT -= 1
            return
        if key == ord(']'):
            self.ms.burnUT += 10
            return
        if key == ord('['):
            self.ms.burnUT -= 10
            return
        if key == ord('}'):
            self.ms.burnUT += 100
            return
        if key == ord('{'):
            self.ms.burnUT -= 100
            return
        if key == curses.KEY_PPAGE:
            self.stagecap += 1
            self.update_vars()
            return
        if key == curses.KEY_NPAGE:
            self.stagecap = max(self.stagecap - 1, 0)
            self.update_vars()
            return
        if key == ord('?'):
            self.update.reset()
            return
        return super(AstroConsole, self).input(key)
    @classmethod
    def connect_params(cls):
        return {'rate': 500} # update twice per second

consoles = {'fd': FDConsole, 'traj': TrajConsole, 'boost': BoosterConsole, 'retro': RetroConsole, 'asc': AscentConsole, 'mnv': AstroConsole}

def parse_si(option, opt, value):
    prefixes = {'k': 3, 'M': 6, 'G': 9}
    l = 0
    while value and value[-1] in prefixes:
        l += prefixes[value[-1]]
        value = value[:-1]
    try:
        v = int(value)
    except ValueError:
        try:
            v = float(value)
        except ValueError:
            raise optparse.OptionValueError("%s: invalid numeric value %s"%(opt,v))
    return v * (10**l)

class Option(optparse.Option):
    TYPES = optparse.Option.TYPES + ("si",)
    TYPE_CHECKER = copy(optparse.Option.TYPE_CHECKER)
    TYPE_CHECKER["si"] = parse_si

def parse_opts():
    x = optparse.OptionParser(usage='%prog consname', option_class=Option)
    x.add_option('--server', type='string', help='Hostname or IP address of Telemachus server', default=downlink.DEFAULT_HOST)
    x.add_option('--port', type='int', help='Port number of Telemachus server', default=downlink.DEFAULT_PORT)
    x.add_option('-f', '--fallover', action="store_true", help='Fall over when exceptions encountered')
    x.add_option('-b', '--body', type='int', help="ID of body to assume we're at", default=1)
    x.add_option('--target-alt', type='si', help="Target altitude above MSL (m)")
    x.add_option('--target-peri', type='si', help="Target periapsis altitude (m)")
    x.add_option('--target-apo', type='si', help="Target apoapsis altitude (m)")
    x.add_option('-t', '--target-body', type='int', help="ID of body we want to intercept", default=10)
    x.add_option('-p', '--propellant', action='append', help="Propellants to track")
    x.add_option('-c', '--consumable', action='append', help="Additional consumables to track (CapSys) ('-c -' to clear defaults)", default=[])
    x.add_option('-u', '--unmanned', action='store_true', help='Replace CapSys with Avionics')
    x.add_option('-r', '--reentry', action='store_true', help='Show re-entry related gauges (FD).  Implied unless -u.', default=False)
    x.add_option('--retrograde', action='store_true', help='Assume vessel travelling blunt end first')
    x.add_option('--init-lat', type='float', help="Latitude of launch (or target) site")
    x.add_option('--init-long', type='float', help="Longitude of launch (or target) site")
    x.add_option('--ccafs', action='store_true', help="Set --init-{lat,long} to Cape Canaveral")
    x.add_option('-n', '--dry-run', action='store_true', help="Don't connect to telemetry, just show layout") # for testing
    x.add_option('-L', '--log-to', type='string', help="File path to write telemetry logs to")
    x.add_option('--booster', type='string', help="Path to JSON Booster spec file")
    x.add_option('--mj', action='store_true', help='Enable control via MechJeb (Trajectory console)')
    x.add_option('--ground-map', type='string', help="Path to ground map CSV (in SCANsat format)")
    x.add_option('--ground-alt', type='si', help="Constant value to use for ground altitude")
    opts, args = x.parse_args()
    if len(args) != 1:
        x.error("Missing consname (choose from %s)"%('|'.join(consoles.keys()),))
    consname = args[0]
    if consname not in consoles:
        x.error("No such consname %s"%(consname,))
    console = consoles[consname]
    if opts.booster:
        opts.booster = open(opts.booster, 'r')
        opts.booster = booster.Booster.from_json(opts.booster.read())
        if not opts.propellant:
            opts.propellant = opts.booster.all_props
    consumable = ['ElectricCharge']
    if not opts.unmanned:
        consumable += ['Food', 'Water', 'Oxygen']
        opts.reentry = True
    if opts.reentry:
        consumable.append('Ablator')
    for c in opts.consumable:
        if c == '-':
            consumable = []
        else:
            consumable.append(c)
    opts.consumable = consumable
    if not opts.propellant:
        opts.propellant = ["LiquidFuel", "Oxidizer", "SolidFuel", "MonoPropellant"]
    if len(opts.propellant) > 11:
        x.error("Too many propellants!  Max is 11")
    if len(opts.consumable) > 11:
        x.error("Too many consumables!  Max is 11")
    if opts.ccafs:
        opts.init_lat = 28.608389
        opts.init_long = -80.604333
    if opts.ground_map:
        with file(opts.ground_map, "r") as f:
            map_csv = csv.reader(f)
            opts.ground_map = {}
            for i,row in enumerate(map_csv):
                if not i:
                    assert row == ['Row','Column','Lat','Long','Height'], row
                    continue
                lat = int(float(row[2]) * 2)
                lon = int(float(row[3]) * 2)
                alt = float(row[4])
                opts.ground_map.setdefault(lon, {})[lat] = alt
    return (opts, console)

if __name__ == '__main__':
    opts, console = parse_opts()
    gauge.fallover = opts.fallover
    if opts.log_to:
        logf = open(opts.log_to, "wb")
    else:
        logf = None
    if opts.dry_run:
        dl = downlink.FakeDownlink()
    else:
        connect_opts = {'host': opts.server, 'port': opts.port, 'logf': logf}
        connect_opts.update(console.connect_params())
        dl = downlink.connect_default(**connect_opts)
    vessel = None
    dl.subscribe('v.name')
    scr = curses.initscr()
    try:
        curses.noecho()
        curses.cbreak()
        scr.keypad(1)
        scr.nodelay(1)
        gauge.initialise()
        console = console(opts, scr, dl)
        console.status.push("Telemetry active")
        end = False
        while not end:
            while True:
                key = scr.getch()
                if key < 0:
                    break
                if console.input(key):
                    end = True
            dl.update()
            vname = dl.get('v.name')
            if vname != vessel and vname is not None:
                console.status.push("Tracking %s"%(vname,))
                vessel = vname
            if dl.get('body_id', opts.body) not in [opts.body, None]:
                opts.body = dl.get('body_id')
                console.group.changeopt(gauge.Gauge, body=opts.body)
            ml = console.group.draw()
            console.group.post_draw()
            if ml is not None:
                for m in ml:
                    console.status.push(m)
            scr.refresh()
    finally:
        curses.endwin()
