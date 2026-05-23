import logging
from typing import Optional, Type, TypeVar

from .packet import Packet
from .interface import Interface

logger = logging.getLogger(__name__)

IfaceT = TypeVar("IfaceT", bound=Interface)


class Node:
    """A network node (host, router, switch) with one or more interfaces."""

    def __init__(self, Name: str):
        self.Name = Name
        self._Interfaces: list[Interface] = []
        logger.debug("[%s] created", self.Name)

    def AddInterface(self, Name: str = "",
                     Cls: Type[IfaceT] = Interface, **Kwargs) -> IfaceT:
        """
        Create an interface, attach it to this node, and return it.

        Pass `Cls=EthernetInterface` (or any other Interface subclass) plus
        its keyword arguments to upgrade from a plain Interface, e.g.

            node.AddInterface("eth0", Cls=EthernetInterface, Mac="aa:bb:...")
        """
        Label = Name or f"eth{len(self._Interfaces)}"
        Iface = Cls(f"{self.Name}/{Label}", **Kwargs)
        self._Interfaces.append(Iface)
        logger.info("[%s] added interface '%s' (%s)",
                    self.Name, Iface.Name, Cls.__name__)
        return Iface

    def FlushTx(self):
        """Phase 1: flush TX queues of every interface onto their wires."""
        for Iface in self._Interfaces:
            Iface.FlushTx()

    def DrainRx(self):
        """Phase 2: drain every interface's wire into its RX queue."""
        for Iface in self._Interfaces:
            Iface.DrainRx()

    def Tick(self):
        """Convenience: run both phases on this node's interfaces."""
        logger.debug("[%s] Tick", self.Name)
        self.FlushTx()
        self.DrainRx()

    def Send(self, Packet_: Packet, IfaceIndex: int = 0) -> bool:
        """Send a packet out through the interface at IfaceIndex."""
        self._CheckIndex(IfaceIndex)
        return self._Interfaces[IfaceIndex].Send(Packet_)

    def Receive(self, IfaceIndex: int = 0) -> Optional[Packet]:
        """Return the next received packet on IfaceIndex, or None."""
        self._CheckIndex(IfaceIndex)
        return self._Interfaces[IfaceIndex].Receive()

    def _CheckIndex(self, Index: int):
        if Index >= len(self._Interfaces):
            raise IndexError(
                f"Node '{self.Name}' has {len(self._Interfaces)} interface(s); "
                f"index {Index} is out of range."
            )

    @property
    def Interfaces(self) -> list[Interface]:
        return list(self._Interfaces)
