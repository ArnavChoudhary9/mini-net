"""
Layer-3 IP building blocks.

Adds IP addresses, IPPackets with TTL, an IPInterface (Interface + IP +
subnet), a Route, and a Router (Node that forwards IPPackets based on a
routing table with longest-prefix matching and TTL decrement).
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .packet import Packet
from .interface import Interface
from .node import Node

logger = logging.getLogger(__name__)


# ── IP namespace ─────────────────────────────────────────────────────────────

class IP:
    """
    Helpers for IPv4 addresses (stored as 'a.b.c.d' strings) and CIDR
    subnets (stored as 'a.b.c.d/p' strings).
    """

    BROADCAST = "255.255.255.255"
    DEFAULT_ROUTE = "0.0.0.0/0"

    @staticmethod
    def IsValid(Addr: str) -> bool:
        Parts = Addr.split(".")
        if len(Parts) != 4:
            return False
        try:
            return all(P.isdigit() and 0 <= int(P) <= 255 for P in Parts)
        except ValueError:
            return False

    @staticmethod
    def ToInt(Addr: str) -> int:
        A, B, C, D = (int(P) for P in Addr.split("."))
        return (A << 24) | (B << 16) | (C << 8) | D

    @staticmethod
    def FromInt(N: int) -> str:
        return f"{(N >> 24) & 0xFF}.{(N >> 16) & 0xFF}.{(N >> 8) & 0xFF}.{N & 0xFF}"

    @staticmethod
    def InSubnet(Addr: str, Cidr: str) -> bool:
        """True if Addr falls inside the CIDR subnet (e.g. '10.0.0.0/24')."""
        NetStr, PrefixStr = Cidr.split("/")
        Prefix = int(PrefixStr)
        if Prefix == 0:
            return True
        Mask = (0xFFFFFFFF << (32 - Prefix)) & 0xFFFFFFFF
        return (IP.ToInt(Addr) & Mask) == (IP.ToInt(NetStr) & Mask)

    @staticmethod
    def PrefixLenOf(Cidr: str) -> int:
        return int(Cidr.split("/")[1])

    @staticmethod
    def NetworkOf(Addr: str, PrefixLen: int) -> str:
        """Return the network address for Addr with PrefixLen bits."""
        Mask = (0xFFFFFFFF << (32 - PrefixLen)) & 0xFFFFFFFF
        return IP.FromInt(IP.ToInt(Addr) & Mask)


# ── IP packet ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class IPPacket(Packet):
    """
    Layer-3 packet.

    Reuses Packet.Src / Packet.Dst as IP addresses, and adds TTL plus a
    Protocol number (analogous to Ethernet's EtherType — 1=ICMP, 6=TCP,
    17=UDP, etc.; mini-net doesn't interpret it).
    """
    TTL: int = 64
    Protocol: int = 0

    def __repr__(self) -> str:
        return (f"IP(Src={self.Src}, Dst={self.Dst}, TTL={self.TTL}, "
                f"Seq={self.Seq}, Data={self.Data!r})")


# ── IP interface ─────────────────────────────────────────────────────────────

class IPInterface(Interface):
    """An Interface with an IP address and subnet (CIDR prefix length)."""

    def __init__(self, Name: str, Ip: str, PrefixLen: int = 24):
        super().__init__(Name)
        if not IP.IsValid(Ip):
            raise ValueError(f"Invalid IP: {Ip!r}")
        if not (0 <= PrefixLen <= 32):
            raise ValueError(f"Invalid prefix length: {PrefixLen}")
        self.Ip = Ip
        self.PrefixLen = PrefixLen
        logger.info("[%s] IP %s/%d", self.Name, self.Ip, self.PrefixLen)

    @property
    def Subnet(self) -> str:
        """The CIDR subnet this interface is on, e.g. '10.0.1.0/24'."""
        return f"{IP.NetworkOf(self.Ip, self.PrefixLen)}/{self.PrefixLen}"

    def SendIp(self, DstIp: str, Data: bytes, TTL: int = 64,
               Protocol: int = 0, Seq: int = 0) -> bool:
        """Build an IPPacket with Src=self.Ip and queue it for transmission."""
        Pkt = IPPacket(Data=Data, Src=self.Ip, Dst=DstIp,
                       Seq=Seq, TTL=TTL, Protocol=Protocol)
        return self.Send(Pkt)

    def SendIpPacket(self, Packet_: Packet, NextHop: Optional[str] = None) -> bool:
        """Forward an already-built IPPacket. NextHop is ignored at this
        layer — there's no L2 to resolve. Override in subclasses that
        wrap IP in Ethernet (see EthernetIPInterface)."""
        _ = NextHop
        return self.Send(Packet_)

    def ReceiveIp(self) -> Optional[Packet]:
        """Pop the next received IP packet, or None."""
        return self.Receive()


# ── Route ────────────────────────────────────────────────────────────────────

@dataclass
class Route:
    """One entry in a routing table."""
    Subnet: str            # CIDR like '10.0.0.0/24' or '0.0.0.0/0' for default
    IfaceIndex: int        # which interface to send out
    NextHop: str = ""      # purely informational

    def __repr__(self) -> str:
        Via = f" via {self.NextHop}" if self.NextHop else ""
        return f"{self.Subnet} -> port{self.IfaceIndex}{Via}"


# ── Router ───────────────────────────────────────────────────────────────────

class Router(Node):
    """
    A Node that forwards IPPackets between its interfaces.

    For each IPPacket received on any port:
      - if the destination is one of our own IPs, accept (do not forward)
      - decrement TTL; drop if it reaches zero
      - look up Dst in the routing table using longest-prefix match
      - if a route is found, build a new IPPacket with the new TTL and
        send it out the route's interface

    Routes are added by the user with AddRoute(); there are no automatic
    "connected" routes so you can see exactly what the router knows.
    """

    def __init__(self, Name: str):
        super().__init__(Name)
        self._Routes: list[Route] = []

    def AddRoute(self, Subnet: str, IfaceIndex: int, NextHop: str = "") -> Route:
        if "/" not in Subnet:
            raise ValueError(f"Subnet must be CIDR, got {Subnet!r}")
        if IfaceIndex >= len(self._Interfaces):
            raise IndexError(f"Router '{self.Name}' has no port{IfaceIndex}")
        R = Route(Subnet=Subnet, IfaceIndex=IfaceIndex, NextHop=NextHop)
        self._Routes.append(R)
        logger.info("[%s] add route %s", self.Name, R)
        return R

    def DrainRx(self):
        """Drain wires into RX, then forward every IP packet we received."""
        super().DrainRx()
        for InPort, Iface in enumerate(self._Interfaces):
            while True:
                Pkt = Iface.Receive()
                if Pkt is None:
                    break
                self._Forward(Pkt, InPort)

    def _Forward(self, Pkt: Packet, InPort: int):
        if not isinstance(Pkt, IPPacket):
            logger.warning("[%s] drop non-IP %s", self.Name, Pkt)
            return

        # Accept locally if Dst is one of our own IPs
        OwnIps = self._OwnIps()
        if Pkt.Dst in OwnIps:
            self._AcceptLocal(Pkt, InPort)
            return

        # Decrement TTL
        NewTTL = Pkt.TTL - 1
        if NewTTL <= 0:
            logger.warning("[%s] TTL expired at port%d, drop %s",
                           self.Name, InPort, Pkt)
            self._SendIcmpTimeExceeded(Pkt, InPort)
            return

        # Longest-prefix match
        Best = self._Lookup(Pkt.Dst)

        if Best is None:
            logger.warning("[%s] no route for %s, drop %s",
                           self.Name, Pkt.Dst, Pkt)
            self._SendIcmpDestUnreachable(Pkt, InPort)
            return

        if Best.IfaceIndex == InPort:
            logger.warning("[%s] would forward back on same port, drop %s",
                           self.Name, Pkt)
            return

        # Preserve subclass (e.g. IcmpMessage) by replacing only TTL.
        # dataclasses.replace works on frozen dataclasses and returns
        # the same concrete type.
        from dataclasses import replace
        Fwd = replace(Pkt, TTL=NewTTL)
        logger.info("[%s] fwd  port%d -> port%d  ttl %d->%d  %s -> %s",
                    self.Name, InPort, Best.IfaceIndex,
                    Pkt.TTL, NewTTL, Pkt.Src, Pkt.Dst)
        OutIface = self._Interfaces[Best.IfaceIndex]
        # If the outgoing wire has an MTU and the packet's data exceeds
        # it, fragment first. Local import to avoid a hard dependency.
        Mtu = getattr(getattr(OutIface, "_Wire", None), "Mtu", 0)
        if (Mtu and isinstance(Fwd.Data, (bytes, bytearray))
                and len(Fwd.Data) > Mtu):
            from .frag import Fragment
            Frags = Fragment(Fwd, Mtu)
            logger.info("[%s] fragment %d bytes -> %d frags (MTU=%d)",
                        self.Name, len(Fwd.Data), len(Frags), Mtu)
            for F in Frags:
                self._SendOut(OutIface, F, Best.NextHop)
            return
        self._SendOut(OutIface, Fwd, Best.NextHop)

    def _SendOut(self, OutIface: Interface, Pkt: IPPacket, NextHop: str):
        """Hand a packet to an outgoing interface, passing the next-hop
        IP so EthernetIPInterface can ARP correctly even on
        router-to-router links where Pkt.Dst isn't on the local subnet.

        All Interfaces implement SendIpPacket — the base version just
        delegates to Send().
        """
        OutIface.SendIpPacket(Pkt, NextHop or None)

    def _OwnIps(self) -> list[str]:
        """Every IP this router has across all of its interfaces."""
        Ips = []
        for I in self._Interfaces:
            Ip = getattr(I, "Ip", "")
            if Ip:
                Ips.append(Ip)
        return Ips

    def _AcceptLocal(self, Pkt: IPPacket, InPort: int):
        """A packet destined for one of our IPs — auto-reply to ICMP echo."""
        from .icmp import IcmpMessage, IcmpType, EchoReply
        if isinstance(Pkt, IcmpMessage) and Pkt.Type == IcmpType.ECHO_REQUEST:
            logger.info("[%s] ICMP echo from %s -> reply", self.Name, Pkt.Src)
            Reply = EchoReply(Src=Pkt.Dst, Dst=Pkt.Src,
                              Identifier=Pkt.Identifier,
                              SeqNumber=Pkt.SeqNumber, Data=Pkt.Data)
            self._Interfaces[InPort].SendIpPacket(Reply)
        else:
            logger.info("[%s] accept (for me) %s", self.Name, Pkt)

    def _Lookup(self, DstIp: str) -> Optional[Route]:
        """Longest-prefix match in our routing table."""
        Best: Optional[Route] = None
        BestLen = -1
        for R in self._Routes:
            Prefix = IP.PrefixLenOf(R.Subnet)
            if Prefix > BestLen and IP.InSubnet(DstIp, R.Subnet):
                Best = R
                BestLen = Prefix
        return Best

    def _SendIcmpTimeExceeded(self, Pkt: IPPacket, InPort: int):
        if self._IsIcmpError(Pkt):
            return  # RFC 792 — no ICMP errors in response to ICMP errors
        from .icmp import TimeExceeded
        InIface = self._Interfaces[InPort]
        SrcIp = getattr(InIface, "Ip", "")
        if not SrcIp or not Pkt.Src:
            return
        Msg = TimeExceeded(Src=SrcIp, Dst=Pkt.Src)
        InIface.SendIpPacket(Msg)

    def _SendIcmpDestUnreachable(self, Pkt: IPPacket, InPort: int):
        if self._IsIcmpError(Pkt):
            return  # RFC 792 — no ICMP errors in response to ICMP errors
        from .icmp import DestUnreachable
        InIface = self._Interfaces[InPort]
        SrcIp = getattr(InIface, "Ip", "")
        if not SrcIp or not Pkt.Src:
            return
        Msg = DestUnreachable(Src=SrcIp, Dst=Pkt.Src, Code=0)
        InIface.SendIpPacket(Msg)

    @staticmethod
    def _IsIcmpError(Pkt: IPPacket) -> bool:
        """RFC 792: ICMP error messages must not themselves trigger
        ICMP errors. Otherwise a single misrouted error can cascade
        into an infinite storm."""
        from .icmp import IcmpMessage, IcmpType
        if not isinstance(Pkt, IcmpMessage):
            return False
        return Pkt.Type in (IcmpType.DEST_UNREACHABLE, IcmpType.TIME_EXCEEDED)

    @property
    def Routes(self) -> list[Route]:
        """Snapshot of the current routing table."""
        return list(self._Routes)
