import logging
from queue import Queue
from typing import Optional

from .packet import Packet
from .wire import Wire

logger = logging.getLogger(__name__)


class Interface:
    """
    A network port on a node.

    Has a single Wire attached via Connect(). The TX queue holds packets
    waiting to be sent; the RX queue holds packets that have arrived.

    Tick() currently only flushes the TX queue onto the wire.
    Duplex (reading from the wire into the RX queue) is left for you to implement.
    """

    def __init__(self, Name: str):
        self.Name = Name
        self._Wire: Optional[Wire] = None
        self._TxQueue: Queue[Packet] = Queue()
        self._RxQueue: Queue[Packet] = Queue()
        logger.debug("[%s] created", self.Name)

    def Connect(self, Wire_: Wire):
        """Attach this interface to a wire."""
        self._Wire = Wire_
        logger.info("[%s] connected to wire '%s'", self.Name, Wire_.Name)

    def Send(self, Packet_: Packet) -> bool:
        """Enqueue a packet for transmission. Returns False if no wire is attached."""
        if self._Wire is None:
            logger.warning("[%s] Send failed — no wire attached", self.Name)
            return False
        self._TxQueue.put(Packet_)
        logger.debug("[%s] queued for TX: %s", self.Name, Packet_)
        return True

    def Receive(self) -> Optional[Packet]:
        """Return the next received packet, or None if the RX queue is empty."""
        if self._RxQueue.empty():
            return None
        Packet_ = self._RxQueue.get_nowait()
        logger.debug("[%s] application read: %s", self.Name, Packet_)
        return Packet_

    def SendIpPacket(self, Packet_: Packet, NextHop: Optional[str] = None) -> bool:
        """
        Forward an IP packet through this interface.

        Base implementation just calls Send() — the NextHop hint is
        ignored. Subclasses with L3 awareness (IPInterface,
        EthernetIPInterface) override this to do route-aware sending
        and ARP resolution.
        """
        _ = NextHop  # not used at this layer
        return self.Send(Packet_)

    def FlushTx(self):
        """
        Phase 1 of a tick: move every pending TX packet onto the wire,
        tagged with this interface's name so we won't read it back.
        """
        if self._Wire is None:
            return
        while not self._TxQueue.empty():
            Packet_ = self._TxQueue.get_nowait()
            logger.info("[%s] TX -> [%s]: %s", self.Name, self._Wire.Name, Packet_)
            self._Wire.Put(Packet_, Sender=self.Name)

    def DrainRx(self):
        """
        Phase 2 of a tick: pull every frame on the wire we did NOT
        originate into the local RX queue.
        """
        if self._Wire is None:
            return
        for Frame_ in self._Wire.Frames():
            Packet_ = Frame_[0]
            Sender = Frame_[1]
            if Sender == self.Name:
                continue
            logger.info("[%s] RX <- [%s]: %s", self.Name, self._Wire.Name, Packet_)
            self._RxQueue.put(Packet_)
            self._Wire.Consume(Frame_)

    def Tick(self):
        """
        Convenience: run both phases on this interface.

        Calling this on a single interface in isolation gives you the
        old one-phase behaviour. Inside an Internet, Internet.Tick()
        calls FlushTx and DrainRx across ALL interfaces in two passes
        so simultaneous bidirectional delivery works in one tick.
        """
        self.FlushTx()
        self.DrainRx()

    @property
    def Connected(self) -> bool:
        return self._Wire is not None

    @property
    def TxSize(self) -> int:
        return self._TxQueue.qsize()

    @property
    def RxSize(self) -> int:
        return self._RxQueue.qsize()

    @property
    def WireName(self) -> str:
        return self._Wire.Name if self._Wire else "<none>"
