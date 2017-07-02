#!/usr/bin/python

import time
import downlink
import gauge
import curses, curses.ascii
import optparse
import booster
import burns
import orbit
import konrad

class TransferConsole(konrad.Console):
    title = "Transfer Window"
    def __init__(self, opts, scr, dl):
        self.frm = orbit.celestial_bodies[opts.body]
        self.to = orbit.celestial_bodies[opts.target_body]
        opts.body = 0
        opts.target_body = 1
        super(TransferConsole, self).__init__(opts, scr, dl)
        self.mode = burns.ManeuverSim.MODE_FIXED
        self.vars = {'PIT': 0, 'HDG': 90}
        mode = gauge.VariableLabel(dl, scr.derwin(3, 15, 4, 25), self.vars, 'mode', centered=True)
        self.ms = burns.ManeuverSim(mode=self.mode)
        self.ms.stagecap = -1
        self.ms.burn_dur = 0
        sim = gauge.UpdateManeuverSim(dl, scr, opts.body, opts.booster, False, self.ms, want=self.vars)
        oriwant = scr.derwin(3, 26, 19, 1)
        owgroup = gauge.GaugeGroup(oriwant, [
            gauge.PitchGauge(dl, oriwant.derwin(1, 11, 1, 1), want=self.vars),
            gauge.VLine(dl, oriwant.derwin(1, 1, 1, 12)),
            gauge.HeadingGauge(dl, oriwant.derwin(1, 12, 1, 13), want=self.vars),
            gauge.VariableLabel(dl, oriwant.derwin(1, 6, 0, 19), self.vars, 'fineness', centered=True),
            ], 'Orient')
        body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
        time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
        ## Outputs
        elts = gauge.UpdateSimElements(dl, scr, self.ms, '0b')
        appr = gauge.UpdateTgtCloseApproach(dl, scr, self.ms, opts.target_body, 'b', 'e')
        ris = gauge.UpdateTgtRI(dl, scr, self.ms, 'be', opts.target_body)
        entry = gauge.UpdateSoiEntry(dl, scr, self.ms, opts.target_body, 'e', 's')
        zwin = scr.derwin(6, 14, 7, 1)
        z = gauge.GaugeGroup(zwin, [gauge.RSTime(dl, zwin.derwin(1, 12, 1, 1), '0', self.ms),
                                    gauge.RSAlt(dl, zwin.derwin(1, 12, 2, 1), '0', self.ms),
                                    gauge.RSAngleParam(dl, zwin.derwin(1, 12, 3, 1), '0', self.ms, 'oh', 'hdg'),
                                    gauge.RSAngleParam(dl, zwin.derwin(1, 12, 4, 1), '0', self.ms, 'inc', 'i'),
                                    ],
                             "Start")
        bwin = scr.derwin(10, 16, 7, 15)
        b = gauge.GaugeGroup(bwin, [gauge.RSTime(dl, bwin.derwin(1, 14, 1, 1), 'b', self.ms),
                                    gauge.RSAlt(dl, bwin.derwin(1, 14, 2, 1), 'b', self.ms),
                                    gauge.RSVSpeed(dl, bwin.derwin(1, 14, 3, 1), 'b', self.ms),
                                    gauge.RSApoapsis(dl, bwin.derwin(1, 14, 4, 1), 'b', self.ms),
                                    gauge.RSPeriapsis(dl, bwin.derwin(1, 14, 5, 1), 'b', self.ms),
                                    gauge.RSObtPeriod(dl, bwin.derwin(1, 14, 6, 1), 'b', self.ms),
                                    gauge.RSAngleParam(dl, bwin.derwin(1, 14, 7, 1), 'b', self.ms, 'ri', 'ri'),
                                    gauge.RSSIParam(dl, bwin.derwin(1, 14, 8, 1), 'b', self.ms, 'dV', 'dV', 'm/s'),
                                    ],
                             "End")
        ewin = scr.derwin(8, 16, 7, 47)
        e = gauge.GaugeGroup(ewin, [gauge.RSTime(dl, ewin.derwin(1, 14, 1, 1), 'e', self.ms),
                                    gauge.RSSIParam(dl, ewin.derwin(1, 14, 2, 1), 'e', self.ms, 'edrvec', 'Re', 'm'),
                                    gauge.RSSIParam(dl, ewin.derwin(1, 14, 3, 1), 'e', self.ms, 'drvec', 'd', 'm'),
                                    gauge.RSSIParam(dl, ewin.derwin(1, 14, 4, 1), 'e', self.ms, 'dvvec', 'v', 'm/s'),
                                    gauge.RSAngleParam(dl, ewin.derwin(1, 14, 5, 1), 'e', self.ms, 'ri', 'i'),
                                    gauge.RSTimeParam(dl, ewin.derwin(1, 14, 6, 1), 'e', self.ms, 'lss', 'w'),
                                    ],
                             "Approach")
        swin = scr.derwin(9, 16, 7, 63)
        s = gauge.GaugeGroup(swin, [gauge.RSTime(dl, swin.derwin(1, 14, 1, 1), 's', self.ms),
                                    gauge.RSSIParam(dl, swin.derwin(1, 14, 2, 1), 's', self.ms, 'edrvec', 'Re', 'm'),
                                    gauge.RSApoapsis(dl, swin.derwin(1, 14, 3, 1), 's', self.ms),
                                    gauge.RSPeriapsis(dl, swin.derwin(1, 14, 4, 1), 's', self.ms),
                                    gauge.RSAngleParam(dl, swin.derwin(1, 14, 5, 1), 's', self.ms, 'inc', 'i'),
                                    gauge.RSAngleParam(dl, swin.derwin(1, 14, 6, 1), 's', self.ms, 'lan', 'L'),
                                    gauge.RSTimeParam(dl, swin.derwin(1, 14, 7, 1), 's', self.ms, 'lss', 'w'),
                                    ],
                             "SOI Entry")
        tgt = gauge.BodyNameGauge(dl, scr.derwin(3, 16, 16, 63), opts.target_body, label='Tgt:')
        self.group = gauge.GaugeGroup(scr,
                                      [mode, sim, owgroup,
                                       elts, appr, ris, entry, z, b, e, s, tgt,
                                       self.status, body, time],
                                      "KONRAD: %s"%(self.title,))
        self.update_vars()
        self.setfine(1)
        self.thou = False
        self.UT = 0
    def update_bodies(self):
        self.dl.put('t.universalTime', self.UT)
        self.dl.put('b.radius[0]', self.frm.parent_body.rad)
        self.dl.put('b.o.gravParameter[0]', self.frm.parent_body.gm)
        self.dl.put('b.radius[1]', self.to.rad)
        self.dl.put('b.o.gravParameter[1]', self.to.gm)
        self.dl.put('o.inclination', self.frm.elts['inc'])
        self.dl.put('o.lan', self.frm.elts['lan'])
        self.dl.put('o.trueAnomaly', self.frm.tan_at_ut(self.UT))
        self.dl.put('o.argumentOfPeriapsis', self.frm.elts['ape'])
        self.dl.put('o.eccentricity', self.frm.elts['ecc'])
        self.dl.put('o.sma', self.frm.elts['sma'])
        self.dl.put('n.pitch2', 0)
        self.dl.put('n.heading2', 0)
    def setfine(self, value):
        self.fine = value
        self.vars['fineness'] = {0: 'COARSE', 1: 'NORMAL', 2: 'FINE'}.get(value, 'Error?')
    def update_vars(self):
        self.vars['mode'] = 'Mode: %s'%(self.ms.modename(self.mode),)
        if self.ms is not None:
            self.ms.mode = self.mode
    def steer(self, what, base):
        old = self.vars[what]
        old = math.floor(old * 100.0 + 0.5) / 100.0
        sf = 10 ** -self.fine
        delta = base * sf
        if what == 'PIT':
            new = min(max(old + delta, -90), 90)
        else:
            new = (old + delta) % 360
        self.vars[what] = new
    def dbt(self, base):
        sf = 5 ** -self.fine
        self.ms.burn_dur = max(self.ms.burn_dur + base * sf, 0)
        self.update_vars()
    def input(self, key):
        if key == ord('f'):
            self.mode = self.ms.MODE_FIXED
            self.update_vars()
            return
        if key == ord('p'):
            self.mode = self.ms.MODE_PROGRADE
            self.update_vars()
            return
        if key == ord('r'):
            self.mode = self.ms.MODE_RETROGRADE
            self.update_vars()
            return
        if key == ord('#'):
            self.thou = not self.thou
            self.update_vars()
            return
        thou = 1000 if self.thou else 1
        if key == ord(')'):
            self.ms.burnUT += thou
            return
        if key == ord('('):
            self.ms.burnUT -= thou
            return
        if key == ord(']'):
            self.ms.burnUT += 10 * thou
            return
        if key == ord('['):
            self.ms.burnUT -= 10 * thou
            return
        if key == ord('}'):
            self.ms.burnUT += 100 * thou
            return
        if key == ord('{'):
            self.ms.burnUT -= 100 * thou
            return
        if key == ord('0'):
            self.ms.burn_dur = 0
            self.update_vars()
            return
        if key == ord(','):
            self.dbt(-5.0)
            return
        if key == ord('.'):
            self.dbt(5.0)
            return
        if key == ord('<'):
            self.dbt(-50.0)
            return
        if key == ord('>'):
            self.dbt(50.0)
            return
        # Input Orientation, for Fixed mode
        steering = {'d': ('HDG', 1),
                    'a': ('HDG', -1),
                    's': ('PIT', 1),
                    'w': ('PIT', -1)}
        if key < 256 and chr(key) in steering:
            what, base = steering[chr(key)]
            self.steer(what, base * 10)
            return
        if key < 256 and chr(key).lower() in steering:
            what, base = steering[chr(key).lower()]
            self.steer(what, base)
            return
        # Toggle fine controls
        if key == ord('`'):
            self.setfine((self.fine + 1) % 3)
            return
        return super(TransferConsole, self).input(key)

def parse_opts():
    x = optparse.OptionParser()
    x.add_option('--refresh-rate', type='float', help='Refresh interval in ms', default=500)
    x.add_option('-f', '--fallover', action="store_true", help='Fall over when exceptions encountered')
    x.add_option('-b', '--body', type='string', help="Name of body to assume we're at", default=1)
    x.add_option('-t', '--target-body', type='string', help="Name of body we want to intercept")
    opts, args = x.parse_args()
    if args:
        x.error("Excess arguments")
    return opts

if __name__ == '__main__':
    opts = parse_opts()
    gauge.fallover = opts.fallover
    opts.booster = booster.FakeBooster()
    dl = downlink.FakeDownlink()
    scr = curses.initscr()
    try:
        curses.noecho()
        curses.cbreak()
        scr.keypad(1)
        scr.nodelay(1)
        gauge.initialise()
        console = TransferConsole(opts, scr, dl)
        console.status.push("Planner active")
        end = False
        st = 0
        while not end:
            key = -1
            while time.time() < st + opts.refresh_rate / 1000.0:
                key = scr.getch()
                if key >= 0:
                    break
            if key >= 0:
                if console.input(key):
                    end = True
            console.update_bodies()
            ml = console.group.draw()
            console.group.post_draw()
            if ml is not None:
                for m in ml:
                    console.status.push(m)
            scr.refresh()
            st = time.time()
    finally:
        curses.endwin()
