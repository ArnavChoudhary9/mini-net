"""
Layer-2 Ethernet building blocks.

Adds MAC addressing, EthernetFrames (a Packet subclass), an
EthernetInterface (Interface + MAC), and a learning Switch (Node that
forwards frames based on destination MAC).

Switch behaviour:
    - learns Src MAC -> incoming port on every frame it receives
    - forwards to the known port when Dst is in the table
    - floods to all other ports when Dst is unknown or broadcast
"""

import logging
import random
from dataclasses import dataclass
from typing import Optional

from .packet import Packet
from .interface import Interface
from .node import Node

logger = logging.getLogger(__name__)


# ── MAC addresses ────────────────────────────────────────────────────────────

class MAC:
    """
    Helpers for working with MAC addresses.

    MACs are stored as lowercase 'xx:xx:xx:xx:xx:xx' strings — no class
    instance needed. This keeps them trivially serialisable into Packet.Src
    / Packet.Dst fields.
    """

    BROADCAST = "ff:ff:ff:ff:ff:ff"

    @staticmethod
    def Random() -> str:
        """Generate a random MAC address."""
        return ":".join(f"{random.randint(0, 255):02x}" for _ in range(6))

    @staticmethod
    def IsValid(Addr: str) -> bool:
        Parts = Addr.split(":")
        if len(Parts) != 6:
            return False
        try:
            return all(len(P) == 2 and 0 <= int(P, 16) <= 255 for P in Parts)
        except ValueError:
            return False

    @staticmethod
    def IsBroadcast(Addr: str) -> bool:
        return Addr.lower() == MAC.BROADCAST


# ── Ethernet frames ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EthernetFrame(Packet):
    """
    A Layer-2 Ethernet frame.

    Inherits Data, Src, Dst, Seq from Packet, where Src / Dst are MAC
    addresses. Adds EtherType (the protocol indicator that real Ethernet
    uses to tell IPv4 from ARP from IPv6 ...).
    """
    EtherType: int = 0x0800   # IPv4 by default

    def __repr__(self) -> str:
        return (f"Frame(EtherType=0x{self.EtherType:04x}, "
                f"Src={self.Src!r}, Dst={self.Dst!r}, "
                f"Seq={self.Seq}, Data={self.Data!r})")


# ── Ethernet interface ───────────────────────────────────────────────────────

class EthernetInterface(Interface):
    """An Interface with a MAC address and frame-building helpers."""

    def __init__(self, Name: str, Mac: Optional[str] = None):
        super().__init__(Name)
        self.Mac = Mac if Mac is not None else MAC.Random()
        if not MAC.IsValid(self.Mac):
            raise ValueError(f"Invalid MAC address: {self.Mac!r}")
        logger.info("[%s] MAC %s", self.Name, self.Mac)

    def SendFrame(self, DstMac: str, Payload: bytes,
                  EtherType: int = 0x0800, Seq: int = 0) -> bool:
        """Build an EthernetFrame and queue it for transmission."""
        Frame_ = EthernetFrame(Data=Payload, Src=self.Mac, Dst=DstMac,
                               Seq=Seq, EtherType=EtherType)
        return self.Send(Frame_)

    def ReceiveFrame(self) -> Optional[Packet]:
        """Pop the next received frame from the RX queue, or None."""
        return self.Receive()


# ── Learning switch ──────────────────────────────────────────────────────────

class Switch(Node):
    """
    A learning Layer-2 switch.

    On every tick, frames received on any port are inspected:
      - the (Src MAC, in-port) pair is added to the MAC table
      - if the Dst MAC is broadcast or unknown, the frame is flooded
        to every other port
      - otherwise it is forwarded out the single port that the table
        associates with Dst MAC

    Switch ports are plain Interfaces — they don't need their own MAC
    because a switch is transparent at L2.
    """

    def __init__(self, Name: str, Ports: int = 4):
        super().__init__(Name)
        self._MacTable: dict[str, int] = {}
        for I in range(Ports):
            self.AddInterface(f"port{I}")

    def DrainRx(self):
        """Drain wires into RX queues, then forward each received frame."""
        super().DrainRx()
        for InPort, Iface in enumerate(self._Interfaces):
            while True:
                Frame_ = Iface.Receive()
                if Frame_ is None:
                    break
                self._Process(Frame_, InPort)

    def _Process(self, Frame_: Packet, InPort: int):
        # 1. Learn the source MAC against the incoming port
        if Frame_.Src:
            Old = self._MacTable.get(Frame_.Src)
            self._MacTable[Frame_.Src] = InPort
            if Old is None:
                logger.info("[%s] learn  %s -> port%d",
                            self.Name, Frame_.Src, InPort)
            elif Old != InPort:
                logger.info("[%s] move   %s: port%d -> port%d",
                            self.Name, Frame_.Src, Old, InPort)

        # 2. Decide where to send the frame
        if MAC.IsBroadcast(Frame_.Dst):
            logger.info("[%s] flood  broadcast %s (in=port%d)",
                        self.Name, Frame_, InPort)
            self._Flood(Frame_, ExcludePort=InPort)
        elif Frame_.Dst in self._MacTable:
            OutPort = self._MacTable[Frame_.Dst]
            if OutPort == InPort:
                logger.info("[%s] drop   %s (dst on same port)",
                            self.Name, Frame_)
                return
            logger.info("[%s] fwd    port%d -> port%d %s",
                        self.Name, InPort, OutPort, Frame_)
            self._Interfaces[OutPort].Send(Frame_)
        else:
            logger.info("[%s] flood  unknown dst %s (in=port%d)",
                        self.Name, Frame_.Dst, InPort)
            self._Flood(Frame_, ExcludePort=InPort)

    def _Flood(self, Frame_: Packet, ExcludePort: int):
        for I, Iface in enumerate(self._Interfaces):
            if I != ExcludePort:
                Iface.Send(Frame_)

    @property
    def MacTable(self) -> dict[str, int]:
        """Snapshot of the current MAC -> port mapping."""
        return dict(self._MacTable)
