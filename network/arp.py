"""
ARP (Address Resolution Protocol) + the combined Ethernet/IP interface.

In real networks IP packets cannot just be put on the wire — they have to
be wrapped in an Ethernet frame addressed to the next-hop's MAC. ARP is
the broadcast mechanism that resolves an IP address to a MAC address on
the same LAN.

This module adds:

  - ArpMessage: a request or reply carried inside an EthernetFrame
    (EtherType 0x0806).
  - EthernetIPInterface: an Interface that has both a MAC and an IP.
    SendIp() builds an IPPacket, looks up the next-hop MAC in the ARP
    cache (or sends an ARP request and queues the packet), then wraps
    the IP packet in an EthernetFrame.

EthernetIPInterface also auto-responds to ICMP echo requests so that
ping just works end-to-end.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .packet import Packet
from .interface import Interface
from .ethernet import MAC, EthernetFrame
from .ip import IP, IPPacket
from .icmp import IcmpMessage, IcmpType

logger = logging.getLogger(__name__)


# ── ARP message ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ArpMessage:
    """
    An ARP request or reply.

    Travels as the payload of an EthernetFrame with EtherType=0x0806.
    For a request, TargetMac is empty and the frame's Dst MAC is broadcast.
    For a reply, TargetMac is filled and the frame's Dst MAC is the
    original requester's MAC.
    """
    Op: str = "request"          # "request" or "reply"
    SenderMac: str = ""
    SenderIp: str = ""
    TargetMac: str = ""
    TargetIp: str = ""

    def __repr__(self) -> str:
        if self.Op == "request":
            return f"ARP(req who-has {self.TargetIp}? tell {self.SenderIp})"
        return f"ARP(reply {self.SenderIp} is at {self.SenderMac})"


# ── Combined Ethernet + IP interface ─────────────────────────────────────────

ETHERTYPE_IPV4 = 0x0800
ETHERTYPE_ARP = 0x0806


class EthernetIPInterface(Interface):
    """
    An interface with both a MAC address and an IP address.

    Sends IP packets wrapped in Ethernet frames, resolving the next-hop
    MAC via ARP. Maintains an ARP cache (IP -> MAC) and an ARP-pending
    queue for packets waiting on resolution.

    Auto-replies to ARP requests addressed to its own IP, and to ICMP
    echo requests addressed to its own IP (so ping just works).
    """

    def __init__(self, Name: str, Mac: Optional[str] = None,
                 Ip: str = "", PrefixLen: int = 24,
                 Gateway: Optional[str] = None):
        super().__init__(Name)
        self.Mac = Mac if Mac is not None else MAC.Random()
        if not MAC.IsValid(self.Mac):
            raise ValueError(f"Invalid MAC: {self.Mac!r}")
        if Ip and not IP.IsValid(Ip):
            raise ValueError(f"Invalid IP: {Ip!r}")
        self.Ip = Ip
        self.PrefixLen = PrefixLen
        self.Gateway = Gateway
        self._ArpCache: dict[str, str] = {}
        self._ArpPending: dict[str, list[IPPacket]] = {}
        # UDP port -> UdpSocket. Bound via BindUdp().
        self._UdpPorts: dict = {}
        # Lazy-imported to avoid a hard frag dependency
        from .frag import Reassembler
        self._Reassembler = Reassembler()
        logger.info("[%s] MAC %s IP %s/%d gw=%s",
                    self.Name, self.Mac, self.Ip, self.PrefixLen, self.Gateway)

    # ── subnet helpers ────────────────────────────────────────────────────

    @property
    def Subnet(self) -> str:
        return f"{IP.NetworkOf(self.Ip, self.PrefixLen)}/{self.PrefixLen}"

    def NextHopFor(self, DstIp: str) -> Optional[str]:
        """Return the IP we should ARP for to reach DstIp from this interface."""
        if self.Ip and IP.InSubnet(DstIp, self.Subnet):
            return DstIp
        return self.Gateway

    # ── application-level send ────────────────────────────────────────────

    def SendIp(self, DstIp: str, Data: bytes, TTL: int = 64,
               Protocol: int = 0, Seq: int = 0) -> bool:
        """Build an IPPacket and send it (with ARP resolution if needed)."""
        Pkt = IPPacket(Data=Data, Src=self.Ip, Dst=DstIp,
                       Seq=Seq, TTL=TTL, Protocol=Protocol)
        return self.SendIpPacket(Pkt)

    def SendUdp(self, DstIp: str, DstPort: int, Data: bytes,
                SrcPort: int = 0, TTL: int = 64) -> bool:
        """Build a UdpDatagram and send it. Stateless — no socket needed."""
        from .udp import UdpDatagram, PROTOCOL_UDP
        Pkt = UdpDatagram(
            Data=Data, Src=self.Ip, Dst=DstIp,
            TTL=TTL, Protocol=PROTOCOL_UDP,
            SrcPort=SrcPort, DstPort=DstPort,
        )
        return self.SendIpPacket(Pkt)

    # ── UDP port bindings ─────────────────────────────────────────────────

    def BindUdp(self, Port: int):
        """Create a UdpSocket bound to Port on this interface. Returns the socket."""
        if Port in self._UdpPorts:
            raise ValueError(f"port {Port} already bound on {self.Name}")
        from .udp import UdpSocket
        Sock = UdpSocket(self, Port)
        self._UdpPorts[Port] = Sock
        return Sock

    def UnbindUdp(self, Port: int):
        """Remove a UDP port binding (called by UdpSocket.Close)."""
        self._UdpPorts.pop(Port, None)

    def SendIpPacket(self, Packet_: Packet, NextHop: Optional[str] = None) -> bool:
        """
        Send an IP packet, resolving the next-hop MAC via ARP.

        Non-IP packets fall through to the base Interface.Send (raw).
        If NextHop is given (typically by a Router that just looked up
        a route with an explicit next hop), ARP for that. Otherwise
        fall back to: ARP for Pkt.Dst if it's on our subnet, else our
        Gateway.
        """
        if not isinstance(Packet_, IPPacket):
            return super().Send(Packet_)
        Pkt: IPPacket = Packet_

        if Pkt.Dst in ("255.255.255.255", "0.0.0.0"):
            return self.SendIpBroadcast(Pkt)

        if NextHop is None or NextHop == "":
            NextHop = self.NextHopFor(Pkt.Dst)
        if NextHop is None:
            logger.warning("[%s] no route to %s (no gateway), drop",
                           self.Name, Pkt.Dst)
            return False

        if NextHop in self._ArpCache:
            DstMac = self._ArpCache[NextHop]
            return self._SendFrame(Pkt, DstMac, ETHERTYPE_IPV4)

        # ARP cache miss — queue the packet and ask
        self._ArpPending.setdefault(NextHop, []).append(Pkt)
        return self._SendArpRequest(NextHop)

    def SendIpBroadcast(self, Pkt: IPPacket) -> bool:
        """Send an IP packet as a broadcast Ethernet frame (skips ARP)."""
        return self._SendFrame(Pkt, MAC.BROADCAST, ETHERTYPE_IPV4)

    def _SendFrame(self, Payload, DstMac: str, EtherType: int) -> bool:
        Frame = EthernetFrame(Data=Payload, Src=self.Mac, Dst=DstMac,
                              EtherType=EtherType)
        return super().Send(Frame)

    def _SendArpRequest(self, TargetIp: str) -> bool:
        Msg = ArpMessage(Op="request", SenderMac=self.Mac,
                         SenderIp=self.Ip, TargetIp=TargetIp)
        logger.info("[%s] ARP req who-has %s", self.Name, TargetIp)
        return self._SendFrame(Msg, MAC.BROADCAST, ETHERTYPE_ARP)

    def _SendArpReply(self, TargetIp: str, TargetMac: str) -> bool:
        Msg = ArpMessage(Op="reply", SenderMac=self.Mac, SenderIp=self.Ip,
                         TargetMac=TargetMac, TargetIp=TargetIp)
        logger.info("[%s] ARP rep %s is-at %s -> %s",
                    self.Name, self.Ip, self.Mac, TargetIp)
        return self._SendFrame(Msg, TargetMac, ETHERTYPE_ARP)

    # ── receive pipeline ──────────────────────────────────────────────────

    def DrainRx(self):
        # We override the base DrainRx entirely so we don't disturb
        # IPPackets already sitting in _RxQueue from previous ticks.
        # Pull each frame off the wire, process it (which may extract
        # an IPPacket and append to _RxQueue, or handle ARP / auto-reply
        # to ICMP echo), then consume it from the wire.
        if self._Wire is None:
            return
        IfaceLog = logging.getLogger("network.interface")
        for Frame_ in self._Wire.Frames():
            Packet_ = Frame_[0]
            Sender = Frame_[1]
            if Sender == self.Name:
                continue
            IfaceLog.info("[%s] RX <- [%s]: %s",
                          self.Name, self._Wire.Name, Packet_)
            self._Wire.Consume(Frame_)
            self._Process(Packet_)

    def _Process(self, Pkt: Packet):
        # Raw IP packet on wire (e.g. someone using IPInterface) — accept
        if isinstance(Pkt, IPPacket):
            self._DeliverIp(Pkt)
            return

        if not isinstance(Pkt, EthernetFrame):
            return  # unknown traffic, ignore

        # Drop frames not for us (unless broadcast)
        if Pkt.Dst and Pkt.Dst != self.Mac and not MAC.IsBroadcast(Pkt.Dst):
            return

        # Passive ARP learning — record sender MAC from any frame
        if isinstance(Pkt.Data, IPPacket) and Pkt.Src and Pkt.Data.Src:
            self._ArpCache[Pkt.Data.Src] = Pkt.Src

        if Pkt.EtherType == ETHERTYPE_ARP:
            Msg = Pkt.Data
            if isinstance(Msg, ArpMessage):
                self._HandleArp(Msg)
            return

        if Pkt.EtherType == ETHERTYPE_IPV4:
            if isinstance(Pkt.Data, IPPacket):
                self._DeliverIp(Pkt.Data)
            return

    def _HandleArp(self, Msg: ArpMessage):
        # Always learn from observed ARP traffic
        if Msg.SenderIp and Msg.SenderMac:
            self._ArpCache[Msg.SenderIp] = Msg.SenderMac

        if Msg.Op == "request" and Msg.TargetIp == self.Ip:
            self._SendArpReply(TargetIp=Msg.SenderIp, TargetMac=Msg.SenderMac)
        elif Msg.Op == "reply":
            # Flush any pending packets waiting on this resolution
            Pending = self._ArpPending.pop(Msg.SenderIp, [])
            for IpPkt in Pending:
                self._SendFrame(IpPkt, Msg.SenderMac, ETHERTYPE_IPV4)

    def _DeliverIp(self, IpPkt: IPPacket):
        """Put an IP packet in the application RX queue and run host-level handlers."""
        # If this is a fragment, run it through the reassembler first.
        from .frag import FragmentedIPPacket
        if isinstance(IpPkt, FragmentedIPPacket):
            Reassembled = self._Reassembler.Add(IpPkt)
            if Reassembled is None:
                return  # still waiting for more fragments
            IpPkt = Reassembled

        # UDP port demux. A datagram for one of our IPs goes to the
        # bound socket; with no listener we send back ICMP Port
        # Unreachable. Either way the datagram does NOT land in the
        # generic RX queue (real sockets work the same — only the
        # bound listener sees it).
        from .udp import UdpDatagram
        if isinstance(IpPkt, UdpDatagram) and IpPkt.Dst == self.Ip:
            Sock = self._UdpPorts.get(IpPkt.DstPort)
            if Sock is not None:
                logger.info("[%s] UDP -> port %d (%d bytes)",
                            self.Name, IpPkt.DstPort, len(IpPkt.Data))
                Sock._Deliver(IpPkt)
            else:
                logger.warning("[%s] UDP port %d unbound, ICMP unreachable",
                               self.Name, IpPkt.DstPort)
                self._SendIcmpPortUnreachable(IpPkt)
            return

        self._RxQueue.put(IpPkt)
        # ICMP echo auto-reply
        if (isinstance(IpPkt, IcmpMessage)
                and IpPkt.Dst == self.Ip
                and IpPkt.Type == IcmpType.ECHO_REQUEST):
            Reply = IcmpMessage(
                Data=IpPkt.Data, Src=self.Ip, Dst=IpPkt.Src, TTL=64,
                Protocol=1, Type=IcmpType.ECHO_REPLY,
                Identifier=IpPkt.Identifier, SeqNumber=IpPkt.SeqNumber,
            )
            logger.info("[%s] ICMP echo reply -> %s", self.Name, IpPkt.Src)
            self.SendIpPacket(Reply)

    def _SendIcmpPortUnreachable(self, Pkt: IPPacket):
        """Send ICMP Destination Unreachable, Code=3 (port unreachable)."""
        from .icmp import DestUnreachable
        if not Pkt.Src:
            return
        Msg = DestUnreachable(Src=self.Ip, Dst=Pkt.Src, Code=3)
        self.SendIpPacket(Msg)

    # ── inspection ────────────────────────────────────────────────────────

    @property
    def ArpCache(self) -> dict[str, str]:
        return dict(self._ArpCache)

    @property
    def ArpPendingCount(self) -> int:
        return sum(len(L) for L in self._ArpPending.values())

    @property
    def UdpPorts(self) -> list[int]:
        """Sorted list of UDP ports currently bound on this interface."""
        return sorted(self._UdpPorts.keys())
