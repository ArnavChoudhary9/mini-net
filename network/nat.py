"""
NAT — Network Address Translation.

The whole internet only has ~4 billion IPv4 addresses, so most homes
and offices get one (or a handful) of public addresses and use private
ones (RFC 1918: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16) internally.
A NAT router at the edge translates between the two.

This module implements **source NAT** (a.k.a. masquerading):

  - On packets going OUT (private side -> public side) the source IP
    is rewritten to the router's public IP. A (orig_src_ip, dst_ip,
    icmp_id) tuple is remembered so we can reverse it later.

  - On packets coming IN (public -> private) we look up the
    (our_public_ip, src_ip, icmp_id) tuple and rewrite dst_ip back
    to the original private address.

Real NAT also tracks TCP/UDP source ports — mini-net uses ICMP's
Identifier field instead because that's all we have at L4. The
concept is identical.
"""

import logging
from dataclasses import dataclass, replace
from typing import Optional

from .packet import Packet
from .ip import IPPacket, Router
from .icmp import IcmpMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NatEntry:
    """One row of a NAT table."""
    PrivateIp: str       # original src
    PublicIp: str        # what we rewrote it to
    DstIp: str           # peer (used to disambiguate)
    Identifier: int      # ICMP id (or "port" in real NAT)


class NatRouter(Router):
    """
    A Router that does source-NAT at one of its interfaces.

    Configure with SetPrivateSide(IfaceIndex) and SetPublicSide(IfaceIndex, PublicIp).
    Any packet forwarded from the private side toward the public side
    is rewritten; any return traffic is rewritten back.

    Hosts on the private side still see their own private IPs; hosts
    on the public side see only the router's public IP.
    """

    def __init__(self, Name: str):
        super().__init__(Name)
        self._PrivatePort: Optional[int] = None
        self._PublicPort: Optional[int] = None
        self._PublicIp: str = ""
        self._Table: dict[tuple, NatEntry] = {}

    def SetPrivateSide(self, IfaceIndex: int):
        self._PrivatePort = IfaceIndex
        logger.info("[%s] NAT private side = port%d", self.Name, IfaceIndex)

    def SetPublicSide(self, IfaceIndex: int, PublicIp: str):
        self._PublicPort = IfaceIndex
        self._PublicIp = PublicIp
        logger.info("[%s] NAT public side = port%d (%s)",
                    self.Name, IfaceIndex, PublicIp)

    def _Forward(self, Pkt: Packet, InPort: int):
        # Order matters:
        #
        #   1. Non-IP traffic — delegate.
        #   2. TTL would expire — delegate WITH the original packet so
        #      the generated ICMP Time Exceeded uses the pre-NAT source
        #      (otherwise traceroute through a NAT is a black hole).
        #   3. Otherwise — translate (NAT handles "skip if Dst is mine"
        #      internally), then delegate for normal forwarding which
        #      will accept-locally or route as appropriate.
        if not isinstance(Pkt, IPPacket):
            super()._Forward(Pkt, InPort)
            return
        if Pkt.TTL - 1 <= 0:
            super()._Forward(Pkt, InPort)
            return
        Translated = self._Translate(Pkt, InPort)
        if Translated is not None:
            Pkt = Translated
        super()._Forward(Pkt, InPort)

    def _Translate(self, Pkt: IPPacket, InPort: int) -> Optional[IPPacket]:
        # Outbound: private -> public.  But not if the packet is destined
        # to one of our own IPs (that's a local-delivery case — never NAT).
        if InPort == self._PrivatePort and self._PublicIp:
            if Pkt.Dst in self._OwnIps():
                return None
            return self._RewriteOutbound(Pkt)
        # Inbound: public -> private (rewrite Dst back to the private IP)
        if InPort == self._PublicPort and Pkt.Dst == self._PublicIp:
            return self._RewriteInbound(Pkt)
        return None

    def _RewriteOutbound(self, Pkt: IPPacket) -> IPPacket:
        Ident = Pkt.Identifier if isinstance(Pkt, IcmpMessage) else 0
        Key = (self._PublicIp, Pkt.Dst, Ident)
        self._Table[Key] = NatEntry(
            PrivateIp=Pkt.Src, PublicIp=self._PublicIp,
            DstIp=Pkt.Dst, Identifier=Ident,
        )
        New = replace(Pkt, Src=self._PublicIp)
        logger.info("[%s] NAT out  %s -> %s (dst %s id=%d)",
                    self.Name, Pkt.Src, self._PublicIp, Pkt.Dst, Ident)
        return New

    def _RewriteInbound(self, Pkt: IPPacket) -> Optional[IPPacket]:
        Ident = Pkt.Identifier if isinstance(Pkt, IcmpMessage) else 0
        Key = (Pkt.Dst, Pkt.Src, Ident)
        Entry = self._Table.get(Key)
        if Entry is None:
            logger.warning("[%s] NAT no mapping for %s (from %s id=%d)",
                           self.Name, Pkt.Dst, Pkt.Src, Ident)
            return None
        New = replace(Pkt, Dst=Entry.PrivateIp)
        logger.info("[%s] NAT in   %s -> %s (from %s id=%d)",
                    self.Name, Pkt.Dst, Entry.PrivateIp, Pkt.Src, Ident)
        return New

    @property
    def NatTable(self) -> list[NatEntry]:
        return list(self._Table.values())
