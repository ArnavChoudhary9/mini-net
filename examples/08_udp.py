"""
08_udp.py - UDP Datagrams and Sockets
=======================================

Demonstrates UDP on top of mini-net's IP stack:

  - A server binds port 8080 and echoes whatever it receives.
  - Two clients send to the server; both get their own replies.
  - A client sends to an unbound port and gets back ICMP
    Destination Unreachable (Code=3, "port unreachable").

Topology:

    alice (10.0.0.1)
        \\
         [switch] ── server (10.0.0.10)
        /
    bob   (10.0.0.2)

All three speak the same LAN, so ARP resolves directly.
"""

import logging
from network import Internet, Controller, EthernetIPInterface, Switch
from network.log import EnableLogging

EnableLogging(logging.WARNING)

# ── Build the topology ───────────────────────────────────────────────────────

world = Internet("udp-lan")

alice  = world.AddNode("alice")
bob    = world.AddNode("bob")
server = world.AddNode("server")
sw     = world.AddNode("sw", Cls=Switch, Ports=4)

wa = world.AddWire("wa")
wb = world.AddWire("wb")
ws = world.AddWire("ws")

alice_eth  = alice.AddInterface("eth0", Cls=EthernetIPInterface,
                                Mac="aa:00:00:00:00:01",
                                Ip="10.0.0.1", PrefixLen=24)
bob_eth    = bob.AddInterface("eth0", Cls=EthernetIPInterface,
                              Mac="bb:00:00:00:00:01",
                              Ip="10.0.0.2", PrefixLen=24)
server_eth = server.AddInterface("eth0", Cls=EthernetIPInterface,
                                 Mac="cc:00:00:00:00:01",
                                 Ip="10.0.0.10", PrefixLen=24)

alice_eth.Connect(wa);   sw.Interfaces[0].Connect(wa)
bob_eth.Connect(wb);     sw.Interfaces[1].Connect(wb)
server_eth.Connect(ws);  sw.Interfaces[2].Connect(ws)

ctrl = Controller(world)

# ── Bind sockets ─────────────────────────────────────────────────────────────

server_sock = server_eth.BindUdp(8080)
alice_sock  = alice_eth.BindUdp(40000)
bob_sock    = bob_eth.BindUdp(40001)


# ── Helper: tiny echo-server loop ────────────────────────────────────────────

def EchoOnce(Sock, Label):
    """If a datagram is waiting, echo it back with a tag and print what happened."""
    msg = Sock.Receive()
    if msg is None:
        return
    SrcIp, SrcPort, Data = msg
    print(f"  [{Label}] got {Data!r} from {SrcIp}:{SrcPort}")
    Reply = b"echo: " + Data
    Sock.Send(DstIp=SrcIp, DstPort=SrcPort, Data=Reply)
    print(f"  [{Label}] echoed {Reply!r} -> {SrcIp}:{SrcPort}")


# ── Step 1: alice -> server -> alice ─────────────────────────────────────────

print("\n######## STEP 1 - alice sends to server, server echoes ########")
alice_sock.Send(DstIp=server_eth.Ip, DstPort=8080, Data=b"hello")
ctrl.Tick(10, ShowState=False)         # ARP + request reaches server
EchoOnce(server_sock, "server")
ctrl.Tick(10, ShowState=False)         # echo flies back to alice
print(f"  alice got: {alice_sock.Receive()}")


# ── Step 2: bob also pings the server ────────────────────────────────────────

print("\n######## STEP 2 - bob sends too (ARP for server already cached) ########")
bob_sock.Send(DstIp=server_eth.Ip, DstPort=8080, Data=b"bob here")
ctrl.Tick(10, ShowState=False)
EchoOnce(server_sock, "server")
ctrl.Tick(10, ShowState=False)
print(f"  bob got: {bob_sock.Receive()}")


# ── Step 3: alice sends to an unbound port ───────────────────────────────────

print("\n######## STEP 3 - alice sends to port 9999 (nobody listening) ########")
alice_sock.Send(DstIp=server_eth.Ip, DstPort=9999, Data=b"anybody?")
ctrl.Tick(10, ShowState=False)
print(f"  server's UDP queue: {server_sock.Receive()}  (expected: None)")
print(f"  alice's generic RX: {alice.Receive()}  (expected: ICMP port-unreachable)")


# ── Step 4: SrcPort != DstPort — server replies to the right caller ──────────

print("\n######## STEP 4 - two clients, two replies, demuxed by port ########")
alice_sock.Send(DstIp=server_eth.Ip, DstPort=8080, Data=b"from-alice")
bob_sock.Send(  DstIp=server_eth.Ip, DstPort=8080, Data=b"from-bob")
ctrl.Tick(10, ShowState=False)
EchoOnce(server_sock, "server")
EchoOnce(server_sock, "server")
ctrl.Tick(10, ShowState=False)
print(f"  alice got: {alice_sock.Receive()}")
print(f"  bob   got: {bob_sock.Receive()}")
