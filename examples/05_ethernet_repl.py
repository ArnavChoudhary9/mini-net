"""
05_ethernet_repl.py - Interactive Switched LAN
================================================

Same topology as example 04 — three hosts behind a learning switch —
but instead of running a scripted scenario it drops you into the
interactive Controller REPL.

      alice ─── wa ─── [port0]
                       [port1] ─── wb ─── bob
                       [port2] ─── wc ─── charlie
                       [port3]
                          switch (4-port learning)

Try inside the REPL:

    mactable sw
    frame alice bb:bb:bb:bb:bb:bb "ping bob" 1
    tick 2
    drain bob
    mactable sw

    frame bob aa:aa:aa:aa:aa:aa "pong alice" 1
    tick 2
    drain alice
    mactable sw

    frame alice broadcast "anybody home?" 2
    tick 2
    drain bob
    drain charlie

    inspect
    log info
    tick

Tip: `python -m network ethernet` builds the same topology without
this file — useful for ad-hoc exploration.
"""

from network import Internet, Controller, EthernetInterface, Switch

# ── Build the LAN ────────────────────────────────────────────────────────────

world = Internet("lan")

alice   = world.AddNode("alice")
bob     = world.AddNode("bob")
charlie = world.AddNode("charlie")
sw      = world.AddNode("sw", Cls=Switch, Ports=4)

wa = world.AddWire("wa")
wb = world.AddWire("wb")
wc = world.AddWire("wc")

alice.AddInterface("eth0",   Cls=EthernetInterface, Mac="aa:aa:aa:aa:aa:aa").Connect(wa)
bob.AddInterface("eth0",     Cls=EthernetInterface, Mac="bb:bb:bb:bb:bb:bb").Connect(wb)
charlie.AddInterface("eth0", Cls=EthernetInterface, Mac="cc:cc:cc:cc:cc:cc").Connect(wc)

sw.Interfaces[0].Connect(wa)
sw.Interfaces[1].Connect(wb)
sw.Interfaces[2].Connect(wc)

# ── Drop into the REPL ───────────────────────────────────────────────────────

Controller(world).Repl()
