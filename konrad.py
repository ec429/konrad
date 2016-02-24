#!/usr/bin/python

import downlink
import gauge
import curses
import optparse

def fd_main(opts, scr, dl):
    """Flight Director's console"""
    fuel = scr.derwin(5, 27, 10, 52)
    fuelgroup = gauge.GaugeGroup(fuel, [
        gauge.FuelGauge(dl, fuel.derwin(1, 25, 1, 1), 'LiquidFuel'),
        gauge.FuelGauge(dl, fuel.derwin(1, 25, 2, 1), 'Oxidizer'),
        gauge.FuelGauge(dl, fuel.derwin(1, 25, 3, 1), 'SolidFuel'),
        ], 'Stage Propellant')
    status = gauge.StatusReadout(dl, scr.derwin(1, 78, 22, 1), 'status:')
    status.push("Nominal")
    obt = scr.derwin(5, 27, 15, 52)
    obtgroup = gauge.GaugeGroup(obt, [
        gauge.AltitudeGauge(dl, obt.derwin(1, 25, 1, 1)),
        gauge.PeriapsisGauge(dl, obt.derwin(1, 25, 2, 1)),
        gauge.ApoapsisGauge(dl, obt.derwin(1, 25, 3, 1)),
        ], 'Orbital')
    time = gauge.TimeGauge(dl, scr.derwin(3, 12, 0, 68))
    return (status, gauge.GaugeGroup(scr, [fuelgroup, status, obtgroup, time], "KONRAD: FD Console"))

consoles = {'fd': fd_main,}

def parse_opts():
    x = optparse.OptionParser(usage='%prog consname')
    x.add_option('-f', '--fallover', action="store_true", help='Fall over when exceptions encountered')
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
