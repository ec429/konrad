#!/usr/bin/python

import downlink
import gauge
import curses, curses.ascii
import optparse
import math
import booster
import retro

class Console(object):
    group = None
    def __init__(self, opts, scr, dl):
        self.dl = dl
        self.status = gauge.StatusReadout(dl, scr.derwin(1, 78, 22, 1), 'status:')
    def input(self, key):
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
            gauge.ObtVelocityGauge(dl, obt.derwin(1, 24, 4, 1)),
            ], 'Orbital')
        xcons = len(opts.consumable)
        strs = scr.derwin(4, 27, 14 if opts.unmanned else 10 - xcons, 1)
        strsgroup = gauge.GaugeGroup(strs, [
            gauge.GeeGauge(dl, strs.derwin(1, 25, 1, 1)),
            gauge.DynPresGauge(dl, strs.derwin(1, 25, 2, 1)),
            ], 'Stresses')
        if opts.unmanned:
            capsys = scr.derwin(4, 27, 18, 1)
            capsysgroup = gauge.GaugeGroup(capsys, [
                gauge.FuelGauge(dl, capsys.derwin(1, 25, 1, 1), 'ElectricCharge'),
                gauge.Light(dl, capsys.derwin(1, 6, 2, 1), 'SAS', 'v.sasValue'),
                gauge.Light(dl, capsys.derwin(1, 6, 2, 7), 'RCS', 'v.rcsValue'),
                gauge.VLine(dl, capsys.derwin(1, 1, 2, 13)),
                gauge.Light(dl, capsys.derwin(1, 6, 2, 14), 'GEAR', 'v.gearValue'),
                gauge.Light(dl, capsys.derwin(1, 6, 2, 20), 'BRK', 'v.brakeValue'),
                ], 'Avionics')
        else:
            capsys = scr.derwin(8 + xcons, 27, 14 - xcons, 1)
            capsysgroup = gauge.GaugeGroup(capsys, [
                gauge.FuelGauge(dl, capsys.derwin(1, 25, 1, 1), 'ElectricCharge'),
                gauge.FuelGauge(dl, capsys.derwin(1, 25, 2, 1), 'Ablator'),
                gauge.FuelGauge(dl, capsys.derwin(1, 25, 3, 1), 'Food'),
                gauge.FuelGauge(dl, capsys.derwin(1, 25, 4, 1), 'Water'),
                gauge.FuelGauge(dl, capsys.derwin(1, 25, 5, 1), 'Oxygen')] +
                [gauge.FuelGauge(dl, capsys.derwin(1, 25, 6 + i, 1), c) for i,c in enumerate(opts.consumable)] + [
                gauge.Light(dl, capsys.derwin(1, 6, 6 + xcons, 1), 'SAS', 'v.sasValue'),
                gauge.Light(dl, capsys.derwin(1, 6, 6 + xcons, 7), 'RCS', 'v.rcsValue'),
                gauge.VLine(dl, capsys.derwin(1, 1, 6 + xcons, 13)),
                gauge.Light(dl, capsys.derwin(1, 6, 6 + xcons, 14), 'GEAR', 'v.gearValue'),
                gauge.Light(dl, capsys.derwin(1, 6, 6 + xcons, 20), 'BRK', 'v.brakeValue'),
                ], 'CapSys')
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
        loxn = scr.derwin(4, 27, 10, 52)
        loxngroup = gauge.GaugeGroup(loxn, [
            gauge.LongitudeGauge(dl, loxn.derwin(1, 12, 1, 1)),
            gauge.LatitudeGauge(dl, loxn.derwin(1, 12, 1, 14)),
            gauge.DownrangeGauge(dl, loxn.derwin(1, 25, 2, 1), opts.body, opts.init_lat, opts.init_long),
            ], 'Location')
        obt = scr.derwin(8, 27, 14, 52)
        obtgroup = gauge.GaugeGroup(obt, [
            gauge.AltitudeGauge(dl, obt.derwin(1, 25, 1, 1), opts.body, target=opts.target_alt),
            gauge.PeriapsisGauge(dl, obt.derwin(1, 25, 2, 1), opts.body, target=opts.target_peri),
            gauge.ApoapsisGauge(dl, obt.derwin(1, 25, 3, 1), target=opts.target_apo),
            gauge.ObtVelocityGauge(dl, obt.derwin(1, 25, 4, 1), target=opts.target_obt_vel, tmu=opts.target_obt_mu, tsma=opts.target_obt_sma, trad=opts.target_obt_rad),
            gauge.ObtPeriodGauge(dl, obt.derwin(1, 25, 5, 1)),
            gauge.InclinationGauge(dl, obt.derwin(1, 25, 6, 1)),
            ], 'Orbital')
        shift = 3 if opts.mj else 0
        motion = scr.derwin(4, 34, 15 - shift, 1)
        mogroup = gauge.GaugeGroup(motion, [
            gauge.ClimbAngleGauge(dl, motion.derwin(1, 16, 1, 1)),
            gauge.HSpeedGauge(dl, motion.derwin(1, 16, 2, 1)),
            gauge.VLine(dl, motion.derwin(2, 1, 1, 17)),
            gauge.AoAGauge(dl, motion.derwin(1, 15, 1, 18), opts.retrograde),
            gauge.VSpeedGauge(dl, motion.derwin(1, 15, 2, 18)),
            ], 'Motion-(Surface)')
        orient = scr.derwin(3, 34, 19 - shift, 1)
        origroup = gauge.GaugeGroup(orient, [
            gauge.PitchGauge(dl, orient.derwin(1, 10, 1, 1)),
            gauge.VLine(dl, orient.derwin(1, 1, 1, 11)),
            gauge.HeadingGauge(dl, orient.derwin(1, 10, 1, 12)),
            gauge.VLine(dl, orient.derwin(1, 1, 1, 22)),
            gauge.RollGauge(dl, orient.derwin(1, 10, 1, 23)),
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
    def input(self, key):
        if key == ord('<'):
            self.group.changeopt(gauge.AoAGauge, retro=True)
            return
        if key == ord('>'):
            self.group.changeopt(gauge.AoAGauge, retro=False)
            return
        # Input Orientation, for AP Fixed
        if key == ord('d'):
            self.want['HDG'] = (self.want['HDG'] + 10) % 360
            return self.maybe_push_mj()
        if key == ord('a'):
            self.want['HDG'] = (self.want['HDG'] + 350) % 360
            return self.maybe_push_mj()
        if key == ord('s'):
            self.want['PIT'] = min(self.want['PIT'] + 10, 90)
            return self.maybe_push_mj()
        if key == ord('w'):
            self.want['PIT'] = max(self.want['PIT'] - 10, -90)
            return self.maybe_push_mj()
        if key == ord('e'):
            self.want['RLL'] = (self.want['RLL'] + 10) % 360
            return self.maybe_push_mj()
        if key == ord('q'):
            self.want['RLL'] = (self.want['RLL'] + 350) % 360
            return self.maybe_push_mj()
        if key == ord('D'):
            self.want['HDG'] = (self.want['HDG'] + 1) % 360
            return self.maybe_push_mj()
        if key == ord('A'):
            self.want['HDG'] = (self.want['HDG'] + 359) % 360
            return self.maybe_push_mj()
        if key == ord('S'):
            self.want['PIT'] = min(self.want['PIT'] + 1, 90)
            return self.maybe_push_mj()
        if key == ord('W'):
            self.want['PIT'] = max(self.want['PIT'] - 1, -90)
            return self.maybe_push_mj()
        if key == ord('E'):
            self.want['RLL'] = (self.want['RLL'] + 1) % 360
            return self.maybe_push_mj()
        if key == ord('Q'):
            self.want['RLL'] = (self.want['RLL'] + 359) % 360
            return self.maybe_push_mj()
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
        update = gauge.UpdateBooster(dl, scr, opts.booster)
        props = len(opts.propellant)
        fuel = scr.derwin(2 + props, 26, 20 - props, 53)
        fuelgroup = gauge.GaugeGroup(fuel, [
            gauge.FuelGauge(dl, fuel.derwin(1, 24, i + 1, 1), p)
            for i,p in enumerate(opts.propellant)
            ], 'Propellants')
        deltav = gauge.DeltaVGauge(dl, scr.derwin(3, 23, 1, 28), opts.booster)
        throttle = gauge.ThrottleGauge(dl, scr.derwin(3, 17, 1, 51))
        stages = scr.derwin(18, 40, 4, 1)
        stagesgroup = gauge.GaugeGroup(stages, [
            gauge.StagesGauge(dl, stages.derwin(16, 38, 1, 1), opts.booster),
            ], 'Stages')
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        self.group = gauge.GaugeGroup(scr,
                                      [update, fuelgroup, deltav, throttle, stagesgroup,
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
        return super(BoosterConsole, self).input(key)

class RetroConsole(Console):
    """Retrograde Propulsion console"""
    def __init__(self, opts, scr, dl):
        super(RetroConsole, self).__init__(opts, scr, dl)
        update = gauge.UpdateBooster(dl, scr, opts.booster)
        deltav = gauge.DeltaVGauge(dl, scr.derwin(3, 23, 1, 28), opts.booster)
        throttle = gauge.ThrottleGauge(dl, scr.derwin(3, 17, 1, 51))
        self.rs = retro.RetroSim()
        sim = gauge.UpdateRetroSim(dl, scr, opts.booster, self.rs)
        hwin = scr.derwin(5, 16, 4, 1)
        h = gauge.GaugeGroup(hwin, [gauge.RSTime(dl, hwin.derwin(1, 14, 1, 1), 'h', self.rs),
                                    gauge.RSAlt(dl, hwin.derwin(1, 14, 2, 1), 'h', self.rs),
                                    gauge.RSDownrange(dl, hwin.derwin(1, 14, 3, 1), 'h', self.rs)],
                             "Horizontal")
        vwin = scr.derwin(5, 16, 4, 17)
        v = gauge.GaugeGroup(vwin, [gauge.RSTime(dl, vwin.derwin(1, 14, 1, 1), 'v', self.rs),
                                    gauge.RSAlt(dl, vwin.derwin(1, 14, 2, 1), 'v', self.rs),
                                    gauge.RSDownrange(dl, vwin.derwin(1, 14, 3, 1), 'v', self.rs)],
                             "Vertical")
        swin = scr.derwin(6, 16, 4, 33)
        s = gauge.GaugeGroup(swin, [gauge.RSTime(dl, swin.derwin(1, 14, 1, 1), 's', self.rs),
                                    gauge.RSDownrange(dl, swin.derwin(1, 14, 3, 1), 's', self.rs),
                                    gauge.RSVSpeed(dl, swin.derwin(1, 14, 2, 1), 's', self.rs),
                                    gauge.RSHSpeed(dl, swin.derwin(1, 14, 4, 1), 's', self.rs)],
                             "Surface")
        bwin = scr.derwin(6, 16, 4, 49)
        b = gauge.GaugeGroup(bwin, [gauge.RSTime(dl, bwin.derwin(1, 14, 1, 1), 'b', self.rs),
                                    gauge.RSAlt(dl, bwin.derwin(1, 14, 2, 1), 'b', self.rs),
                                    gauge.RSVSpeed(dl, bwin.derwin(1, 14, 3, 1), 'b', self.rs),
                                    gauge.RSHSpeed(dl, bwin.derwin(1, 14, 4, 1), 'b', self.rs)],
                             "Burnout")
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        self.group = gauge.GaugeGroup(scr,
                                      [update, deltav, throttle,
                                       sim, h, v, s, b,
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
        return super(RetroConsole, self).input(key)
    @classmethod
    def connect_params(cls):
        return {'rate': 1000} # update once per second

consoles = {'fd': FDConsole, 'traj': TrajConsole, 'boost': BoosterConsole, 'retro': RetroConsole}

def parse_opts():
    x = optparse.OptionParser(usage='%prog consname')
    x.add_option('-f', '--fallover', action="store_true", help='Fall over when exceptions encountered')
    x.add_option('-b', '--body', type='int', help="ID of body to assume we're at", default=1)
    x.add_option('--target-alt', type='int', help="Target altitude above MSL (m)")
    x.add_option('--target-peri', type='int', help="Target periapsis altitude (m)")
    x.add_option('--target-apo', type='int', help="Target apoapsis altitude (m)")
    x.add_option('--target-obt-vel', type='int', help="Target orbital velocity (m/s)")
    x.add_option('-p', '--propellant', action='append', help="Propellants to track")
    x.add_option('-c', '--consumable', action='append', help="Additional consumables to track (CapSys)", default=[])
    x.add_option('-u', '--unmanned', action='store_true', help='Replace CapSys with Avionics')
    x.add_option('-r', '--retrograde', action='store_true', help='Assume vessel travelling blunt end first')
    x.add_option('--init-lat', type='float', help="Latitude of launch (or target) site")
    x.add_option('--init-long', type='float', help="Longitude of launch (or target) site")
    x.add_option('--ccafs', action='store_true', help="Set --init-{lat,long} to Cape Canaveral")
    x.add_option('--dry-run', action='store_true', help="Don't connect to telemetry, just show layout") # for testing
    x.add_option('-L', '--log-to', type='string', help="File path to write telemetry logs to")
    x.add_option('--booster', type='string', help="Path to JSON Booster spec file")
    x.add_option('--mj', action='store_true', help='Enable control via MechJeb (Trajectory console)')
    opts, args = x.parse_args()
    # Magic for the magic target_obt_vel
    opts.target_obt_mu = None
    opts.target_obt_sma = None
    opts.target_obt_rad = None
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
    if not opts.propellant:
        opts.propellant = ["LiquidFuel", "Oxidizer", "SolidFuel", "MonoPropellant"]
    if len(opts.propellant) > 13:
        x.error("Too many propellants!  Max is 13")
    if len(opts.consumable) > 9:
        x.error("Too many consumables!  Max is 9")
    if opts.ccafs:
        opts.init_lat = 28.608389
        opts.init_long = -80.604333
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
        dl = downlink.connect_default(logf=logf)
    vessel = None
    dl.subscribe('v.name')
    if opts.target_alt and not (opts.target_peri or opts.target_apo):
        # Assume they want circular at target alt
        opts.target_peri = opts.target_alt
        opts.target_apo = opts.target_alt
    if opts.target_peri and opts.target_apo and not opts.target_obt_vel:
        # Supply GM and sma, so we can compute v on-the-fly
        brad = "b.radius[%d]"%(opts.body,)
        bgm = "b.o.gravParameter[%d]"%(opts.body,)
        dl.subscribe(brad)
        dl.subscribe(bgm)
        dl.update()
        r = dl.get(brad, None)
        gm = dl.get(bgm, None)
        if None not in (r, gm):
            sma = r + (opts.target_peri + opts.target_apo) / 2.0
            if opts.target_peri == opts.target_apo:
                # Circular, just find v_0 ~= sqrt(mu/a)
                opts.target_obt_vel = math.sqrt(gm / sma)
            else:
                opts.target_obt_mu = gm
                opts.target_obt_sma = sma
                opts.target_obt_rad = r
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
            ml = console.group.draw()
            console.group.post_draw()
            if ml is not None:
                for m in ml:
                    console.status.push(m)
            scr.refresh()
    finally:
        curses.endwin()
