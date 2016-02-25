#!/usr/bin/python

import downlink
import gauge
import curses
import optparse
import math

def fd_main(opts, scr, dl):
    """Flight Director's console"""
    fuel = scr.derwin(6, 27, 10, 52)
    fuelgroup = gauge.GaugeGroup(fuel, [
        gauge.FuelGauge(dl, fuel.derwin(1, 25, 1, 1), 'LiquidFuel'),
        gauge.FuelGauge(dl, fuel.derwin(1, 25, 2, 1), 'Oxidizer'),
        gauge.FuelGauge(dl, fuel.derwin(1, 25, 3, 1), 'SolidFuel'),
        gauge.FuelGauge(dl, fuel.derwin(1, 25, 4, 1), 'MonoPropellant'),
        ], 'Propellants')
    status = gauge.StatusReadout(dl, scr.derwin(1, 78, 22, 1), 'status:')
    status.push("Telemetry active")
    obt = scr.derwin(6, 27, 16, 52)
    obtgroup = gauge.GaugeGroup(obt, [
        gauge.AltitudeGauge(dl, obt.derwin(1, 25, 1, 1), opts.body),
        gauge.PeriapsisGauge(dl, obt.derwin(1, 25, 2, 1), opts.body),
        gauge.ApoapsisGauge(dl, obt.derwin(1, 25, 3, 1)),
        gauge.ObtVelocityGauge(dl, obt.derwin(1, 25, 4, 1)),
        ], 'Orbital')
    strs = scr.derwin(4, 27, 10, 1)
    strsgroup = gauge.GaugeGroup(strs, [
        gauge.GeeGauge(dl, strs.derwin(1, 25, 1, 1)),
        gauge.DynPresGauge(dl, strs.derwin(1, 25, 2, 1)),
        ], 'Stresses')
    capsys = scr.derwin(8, 27, 14, 1)
    capsysgroup = gauge.GaugeGroup(capsys, [
        gauge.FuelGauge(dl, capsys.derwin(1, 25, 1, 1), 'ElectricCharge'),
        gauge.FuelGauge(dl, capsys.derwin(1, 25, 2, 1), 'Ablator'),
        gauge.FuelGauge(dl, capsys.derwin(1, 25, 3, 1), 'Food'),
        gauge.FuelGauge(dl, capsys.derwin(1, 25, 4, 1), 'Water'),
        gauge.FuelGauge(dl, capsys.derwin(1, 25, 5, 1), 'Oxygen'),
        gauge.Light(dl, capsys.derwin(1, 6, 6, 1), 'SAS', 'v.sasValue'),
        gauge.Light(dl, capsys.derwin(1, 6, 6, 7), 'RCS', 'v.rcsValue'),
        gauge.VLine(dl, capsys.derwin(1, 1, 6, 13)),
        gauge.Light(dl, capsys.derwin(1, 6, 6, 14), 'GEAR', 'v.gearValue'),
        gauge.Light(dl, capsys.derwin(1, 6, 6, 20), 'BRK', 'v.brakeValue'),
        ], 'CapSys')
    orient = scr.derwin(12, 24, 10, 28)
    origroup = gauge.GaugeGroup(orient, [], 'Orientation')
    body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
    time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
    return (status, gauge.GaugeGroup(scr,
                [fuelgroup, status, obtgroup, strsgroup, capsysgroup, origroup, body, time],
                "KONRAD: FD Console"))

def traj_main(opts, scr, dl):
    """Trajectory console"""
    status = gauge.StatusReadout(dl, scr.derwin(1, 78, 22, 1), 'status:')
    status.push("Telemetry active")
    loxn = scr.derwin(4, 27, 12, 52)
    loxngroup = gauge.GaugeGroup(loxn, [
        gauge.LongitudeGauge(dl, loxn.derwin(1, 12, 1, 1)),
        gauge.LatitudeGauge(dl, loxn.derwin(1, 12, 1, 14)),
        gauge.DownrangeGauge(dl, loxn.derwin(1, 25, 2, 1), opts.body),
        ], 'Location')
    obt = scr.derwin(6, 27, 16, 52)
    obtgroup = gauge.GaugeGroup(obt, [
        gauge.AltitudeGauge(dl, obt.derwin(1, 25, 1, 1), opts.body, target=opts.target_alt),
        gauge.PeriapsisGauge(dl, obt.derwin(1, 25, 2, 1), opts.body, target=opts.target_peri),
        gauge.ApoapsisGauge(dl, obt.derwin(1, 25, 3, 1), target=opts.target_apo),
        gauge.ObtVelocityGauge(dl, obt.derwin(1, 25, 4, 1), target=opts.target_obt_vel, tmu=opts.target_obt_mu, tsma=opts.target_obt_sma, trad=opts.target_obt_rad),
        ], 'Orbital')
    orient = scr.derwin(3, 34, 19, 1)
    origroup = gauge.GaugeGroup(orient, [
        gauge.PitchGauge(dl, orient.derwin(1, 10, 1, 1)),
        gauge.VLine(dl, orient.derwin(1, 1, 1, 11)),
        gauge.HeadingGauge(dl, orient.derwin(1, 10, 1, 12)),
        gauge.VLine(dl, orient.derwin(1, 1, 1, 22)),
        gauge.RollGauge(dl, orient.derwin(1, 10, 1, 23)),
        ], 'Orientation')
    body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
    time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
    return (status, gauge.GaugeGroup(scr,
                [status, loxngroup, obtgroup, origroup, body, time],
                "KONRAD: Trajectory"))

consoles = {'fd': fd_main, 'traj': traj_main}

def parse_opts():
    x = optparse.OptionParser(usage='%prog consname')
    x.add_option('-f', '--fallover', action="store_true", help='Fall over when exceptions encountered')
    x.add_option('-b', '--body', type='int', help="ID of body to assume we're at", default=1)
    x.add_option('--target-alt', type='int', help="Target altitude above MSL (m)")
    x.add_option('--target-peri', type='int', help="Target periapsis altitude (m)")
    x.add_option('--target-apo', type='int', help="Target apoapsis altitude (m)")
    x.add_option('--target-obt-vel', type='int', help="Target orbital velocity (m/s)")
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
    return (opts, console)

if __name__ == '__main__':
    opts, console = parse_opts()
    gauge.fallover = opts.fallover
    dl = downlink.connect_default()
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
        gauge.initialise()
        status, group = console(opts, scr, dl)
        while True:
            dl.update()
            vname = dl.get('v.name')
            if vname != vessel:
                status.push("Tracking %s"%(vname,))
                vessel = vname
            ml = group.draw()
            group.post_draw()
            if ml is not None:
                for m in ml:
                    status.push(m)
            scr.refresh()
    finally:
        curses.endwin()
