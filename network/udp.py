"""
UDP — User Datagram Protocol.

Adds source/destination ports on top of IP for process-level
multiplexing. UDP is connectionless: each datagram stands alone,
no retransmits, no ordering guarantees, no flow control.

This module adds:

  - PROTOCOL_UDP: the standard IP Protocol number (17).
  - UdpDatagram: an IPPacket subclass carrying SrcPort/DstPort.
  - UdpSocket: an application-level socket bound to a port on an
    EthernetIPInterface. Send() builds and dispatches datagrams;
    Receive() drains incoming ones the interface has demuxed to us.

Inbound demultiplexing lives on EthernetIPInterface — when it
sees a UdpDatagram for one of its IPs, it looks up the destination
port in its bindings table and delivers to the right socket. With
no listener, it generates an ICMP Destination Unreachable
(Code=3, "port unreachable") back to the sender.
"""

import logging
from dataclasses import dataclass
from queue import Queue
from typing import TYPE_CHECKING, Optional

from .ip import IPPacket

if TYPE_CHECKING:
    from .arp import EthernetIPInterface

logger = logging.getLogger(__name__)

PROTOCOL_UDP = 17


# ── UDP datagram ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class UdpDatagram(IPPacket):
    """
    A UDP datagram carried inside an IP packet (Protocol=17).

    Reuses Packet.Src / Packet.Dst as IP addresses and adds the two
    port numbers. Real UDP also has Length and Checksum fields —
    mini-net omits them (length is implicit from Data; corruption
    isn't modelled).
    """
    SrcPort: int = 0
    DstPort: int = 0

    def __repr__(self) -> str:
        return (f"UDP({self.Src}:{self.SrcPort} -> {self.Dst}:{self.DstPort}"
                f" TTL={self.TTL} Data={self.Data!r})")


# ── UdpSocket ────────────────────────────────────────────────────────────────

class UdpSocket:
    """
    Application-level socket bound to a port on an EthernetIPInterface.

    Usage:
        sock = iface.BindUdp(8080)
        sock.Send(DstIp="10.0.0.2", DstPort=53, Data=b"query")
        msg = sock.Receive()
        if msg:
            SrcIp, SrcPort, Data = msg

    Receive() returns None when there's nothing waiting (it does not
    block — this is a tick-based simulator).
    """

    def __init__(self, Iface: "EthernetIPInterface", Port: int):
        self._Iface = Iface
        self.Port = Port
        self._RxQueue: Queue = Queue()
        self._Closed = False
        logger.info("[%s] UDP bind port %d", Iface.Name, Port)

    def Send(self, DstIp: str, DstPort: int, Data: bytes,
             TTL: int = 64) -> bool:
        """Build a UdpDatagram and hand it to the interface for transmission."""
        if self._Closed:
            return False
        Pkt = UdpDatagram(
            Data=Data, Src=self._Iface.Ip, Dst=DstIp,
            TTL=TTL, Protocol=PROTOCOL_UDP,
            SrcPort=self.Port, DstPort=DstPort,
        )
        return self._Iface.SendIpPacket(Pkt)

    def Receive(self) -> Optional[tuple[str, int, bytes]]:
        """Pop the next datagram. Returns (src_ip, src_port, data) or None."""
        if self._RxQueue.empty():
            return None
        Pkt: UdpDatagram = self._RxQueue.get_nowait()
        return (Pkt.Src, Pkt.SrcPort, Pkt.Data)

    def Close(self):
        """Unbind from the interface. Subsequent Send returns False."""
        if self._Closed:
            return
        self._Iface.UnbindUdp(self.Port)
        self._Closed = True

    # Called by the interface when a matching datagram arrives.
    def _Deliver(self, Pkt: UdpDatagram):
        self._RxQueue.put(Pkt)

    @property
    def RxSize(self) -> int:
        return self._RxQueue.qsize()
