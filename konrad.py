#!/usr/bin/python

import downlink
import gauge
import curses
import optparse

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
    capsys = scr.derwin(4, 27, 14, 1)
    capsysgroup = gauge.GaugeGroup(capsys, [
        gauge.FuelGauge(dl, capsys.derwin(1, 25, 1, 1), 'ElectricCharge'),
        gauge.FuelGauge(dl, capsys.derwin(1, 25, 2, 1), 'Ablator'),
        ], 'CapSys')
    orient = scr.derwin(12, 24, 10, 28)
    origroup = gauge.GaugeGroup(orient, [], 'Orientation')
    body = gauge.BodyGauge(dl, scr.derwin(3, 12, 0, 0), opts.body)
    time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
    return (status, gauge.GaugeGroup(scr,
                [fuelgroup, status, obtgroup, strsgroup, capsysgroup, origroup, body, time],
                "KONRAD: FD Console"))

consoles = {'fd': fd_main,}

def parse_opts():
    x = optparse.OptionParser(usage='%prog consname')
    x.add_option('-f', '--fallover', action="store_true", help='Fall over when exceptions encountered')
    x.add_option('-b', '--body', type='int', help="ID of body to assume we're at", default=1)
    opts, args = x.parse_args()
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
