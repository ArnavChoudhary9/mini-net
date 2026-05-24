"""
Dynamic routing — a tiny distance-vector protocol (RIP-style).

Real internets discover routes by exchanging them between routers
rather than configuring them by hand. There are two big families:

  - distance-vector (RIP, EIGRP, BGP):
        "tell my neighbours what I know, learn the same from them,
         keep the shortest path"
  - link-state (OSPF, IS-IS):
        "flood the whole topology, run Dijkstra locally"

mini-net implements the distance-vector flavour because it is the
shortest path to a working dynamic routing demo. A `DynamicRouter`
is just a `Router` that also:

  1. installs a connected route for every interface that has an IP
  2. periodically advertises its routing table to every neighbour as
     a `RoutingUpdate` packet (a special IPPacket subclass)
  3. processes incoming RoutingUpdates: for each (subnet, metric+1)
     pair, install or update a route — but only if it's a better
     metric than what we already have

Metric here is just hop count. Real RIP adds split horizon, poison
reverse, holddown timers, etc. — those are great follow-on exercises.
"""

import logging
from dataclasses import dataclass, field

from .packet import Packet
from .ip import IP, IPPacket, Route, Router

logger = logging.getLogger(__name__)


# ── Routing update message ───────────────────────────────────────────────────

@dataclass(frozen=True)
class RoutingUpdate(IPPacket):
    """
    A distance-vector advertisement.

    Carries a list of (subnet, metric) pairs the sender claims to know
    how to reach. Sent to a hard-coded multicast-like address; in
    mini-net we just deliver it directly to peer routers.
    """
    # IPPacket already has Data/Src/Dst/TTL/Protocol/Seq; we add Routes.
    # We must give Routes a default for the frozen-dataclass-with-defaults
    # rule. Use field(default_factory=...) for the mutable default.
    Entries: tuple = field(default_factory=tuple)

    def __repr__(self) -> str:
        Body = ", ".join(f"{S}={M}" for S, M in self.Entries)
        return f"RoutingUpdate(Src={self.Src} Dst={self.Dst} [{Body}])"


# ── Tracked route (with metric and origin) ───────────────────────────────────

@dataclass
class TrackedRoute:
    Subnet: str
    IfaceIndex: int
    NextHop: str
    Metric: int             # hop count
    Connected: bool = False # True = directly attached, never overridden

    def AsRoute(self) -> Route:
        return Route(Subnet=self.Subnet, IfaceIndex=self.IfaceIndex,
                     NextHop=self.NextHop)


# ── Dynamic router ───────────────────────────────────────────────────────────

# Reserved protocol number for routing updates (real RIP uses UDP/520;
# mini-net just borrows a free Protocol value to identify the packet).
PROTOCOL_ROUTING = 200


class DynamicRouter(Router):
    """
    Router that learns routes from its neighbours instead of (or in
    addition to) hand-configured ones.

    Call InstallConnectedRoutes() once after wiring up interfaces;
    that seeds the table with directly-attached subnets. Each call to
    Tick() also runs AdvertiseInterval logic — every N ticks the router
    broadcasts its full table to every interface.
    """

    def __init__(self, Name: str, AdvertiseInterval: int = 5):
        super().__init__(Name)
        self._Tracked: dict[str, TrackedRoute] = {}      # keyed by subnet
        self._AdvertiseInterval = AdvertiseInterval
        self._Counter = 0

    # ── connected routes ──────────────────────────────────────────────────

    def InstallConnectedRoutes(self):
        """Add one route per interface that has an IP (directly attached)."""
        for I, Iface in enumerate(self._Interfaces):
            Ip = getattr(Iface, "Ip", "")
            PrefixLen = getattr(Iface, "PrefixLen", 0)
            if not Ip:
                continue
            Subnet = f"{IP.NetworkOf(Ip, PrefixLen)}/{PrefixLen}"
            T = TrackedRoute(Subnet=Subnet, IfaceIndex=I, NextHop="",
                             Metric=0, Connected=True)
            self._Install(T)

    def _Install(self, T: TrackedRoute):
        """Insert or replace a tracked route, and rebuild the base table."""
        Existing = self._Tracked.get(T.Subnet)
        if Existing and Existing.Connected:
            return  # never replace a connected route
        if Existing and Existing.Metric <= T.Metric and not T.Connected:
            return  # we already have an equal-or-better path
        self._Tracked[T.Subnet] = T
        # Rebuild the parent Router's _Routes list from _Tracked
        self._Routes = [Tr.AsRoute() for Tr in self._Tracked.values()]
        logger.info("[%s] install route %s -> port%d metric=%d%s",
                    self.Name, T.Subnet, T.IfaceIndex, T.Metric,
                    " (connected)" if T.Connected else f" via {T.NextHop}")

    # ── advertise + receive ───────────────────────────────────────────────

    def FlushTx(self):
        """
        Hook periodic route advertisements onto FlushTx — the first
        phase of Internet.Tick(). This is what actually runs every
        global tick (Node.Tick() is the standalone-only path).
        """
        self._Counter += 1
        if self._Counter % self._AdvertiseInterval == 0:
            self._Advertise()
        super().FlushTx()

    def _Advertise(self):
        """Send our current routing table to every neighbour."""
        Entries = tuple((T.Subnet, T.Metric) for T in self._Tracked.values())
        if not Entries:
            return
        for I, Iface in enumerate(self._Interfaces):
            Ip = getattr(Iface, "Ip", "")
            if not Ip:
                continue
            # Use the subnet broadcast convention: send to 255.255.255.255
            # and let peer EthernetIP interfaces accept it. For mini-net
            # we set Dst="0.0.0.0" and rely on neighbours to inspect by
            # Protocol number rather than addressing.
            Update = RoutingUpdate(
                Data=b"", Src=Ip, Dst="0.0.0.0", TTL=1,
                Protocol=PROTOCOL_ROUTING, Entries=Entries,
            )
            logger.info("[%s] ADV port%d %s", self.Name, I, Entries)
            # Send directly out the interface (don't go through routing).
            # All Interfaces implement SendIpPacket — for the broadcast
            # destination "0.0.0.0" the EthernetIPInterface will wrap in
            # a broadcast Ethernet frame and skip ARP.
            Iface.SendIpPacket(Update)

    def _Forward(self, Pkt: Packet, InPort: int):
        """Intercept RoutingUpdate before normal forwarding."""
        if isinstance(Pkt, RoutingUpdate):
            self._ProcessUpdate(Pkt, InPort)
            return
        super()._Forward(Pkt, InPort)

    def _ProcessUpdate(self, Pkt: RoutingUpdate, InPort: int):
        """A neighbour told us what they know — install better routes."""
        NextHop = Pkt.Src
        logger.info("[%s] recv ADV from %s on port%d: %d entr%s",
                    self.Name, NextHop, InPort,
                    len(Pkt.Entries), "y" if len(Pkt.Entries) == 1 else "ies")
        for Subnet, Metric in Pkt.Entries:
            # Don't install routes for subnets we are part of —
            # connected routes always win.
            Existing = self._Tracked.get(Subnet)
            if Existing and Existing.Connected:
                continue
            NewMetric = Metric + 1
            if NewMetric >= 16:
                continue  # RIP's count-to-infinity guard
            if Existing and Existing.Metric <= NewMetric:
                continue
            T = TrackedRoute(Subnet=Subnet, IfaceIndex=InPort,
                             NextHop=NextHop, Metric=NewMetric)
            self._Install(T)

    # ── inspection ────────────────────────────────────────────────────────

    @property
    def TrackedRoutes(self) -> list[TrackedRoute]:
        return list(self._Tracked.values())
