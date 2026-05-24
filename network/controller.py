import logging
import shlex

from .packet import Packet
from .internet import Internet
from .ethernet import EthernetInterface, Switch, MAC
from .ip import IPInterface, Router, IP
from .arp import EthernetIPInterface
from .icmp import EchoRequest
from .nat import NatRouter

logger = logging.getLogger(__name__)


class Controller:
    """
    A debugger / inspector for an Internet.

    Wraps a world and exposes high-level commands you can drive from
    code or a REPL:

        ctrl.Send("alice", b"hi", Dst="bob")  # queue a packet
        ctrl.Tick()                            # advance one tick
        ctrl.Inspect()                         # print wire + queue state
        ctrl.Drain("bob")                      # read everything in RX

    Every command prints what it did so you can watch the simulation
    flow on the console.
    """

    def __init__(self, Internet_: Internet, Name: str = "ctrl"):
        self.Name = Name
        self._Internet = Internet_
        logger.info("[%s] attached to '%s'", self.Name, Internet_.Name)

    # ── actions ──────────────────────────────────────────────────────────────

    def Send(self, NodeName: str, Data: bytes, Dst: str = "",
             Seq: int = 0, IfaceIndex: int = 0) -> bool:
        """Build a Packet and queue it on the named node's interface."""
        N = self._Internet.FindNode(NodeName)
        Pkt = Packet(Data=Data, Src=NodeName, Dst=Dst, Seq=Seq)
        print(f"[{self.Name}] -> {NodeName} eth{IfaceIndex}.Send  {Pkt}")
        return N.Send(Pkt, IfaceIndex)

    def Tick(self, Times: int = 1, ShowState: bool = True):
        """Advance the world by Times ticks, then print the resulting state."""
        print(f"[{self.Name}] tick x{Times}")
        self._Internet.Tick(Times)
        if ShowState:
            self.Inspect()

    def Drain(self, NodeName: str, IfaceIndex: int = 0) -> int:
        """Read every packet in a node's RX queue and print each one."""
        N = self._Internet.FindNode(NodeName)
        Count = 0
        while True:
            Pkt = N.Receive(IfaceIndex)
            if Pkt is None:
                break
            print(f"[{self.Name}] <- {NodeName} eth{IfaceIndex} got    {Pkt}")
            Count += 1
        if Count == 0:
            print(f"[{self.Name}] <- {NodeName} eth{IfaceIndex} RX empty")
        return Count

    # ── inspection ───────────────────────────────────────────────────────────

    def Inspect(self):
        """Print a complete snapshot of the world (nodes, interfaces,
        MAC/routing/NAT tables). Wires are skipped — with two-phase
        ticking they're always drained by the end of a tick, so they
        only ever show as empty. Use `peek <wire>` to inspect a wire
        mid-tick (e.g. from logs)."""
        print(f"[{self.Name}] ----- state @ tick {self._Internet.TickCount} -----")
        self._PrintNodes()
        print(f"[{self.Name}] ---------------------------")

    def PeekWire(self, WireName: str) -> list[Packet]:
        """Return (and print) every packet currently in transit on a wire."""
        W = self._Internet.FindWire(WireName)
        Buf = W.Peek()
        if Buf:
            print(f"[{self.Name}] wire {WireName!r} carries {len(Buf)}:")
            for P in Buf:
                print(f"      - {P}")
        else:
            print(f"[{self.Name}] wire {WireName!r} is empty")
        return Buf

    # ── helpers ──────────────────────────────────────────────────────────────

    def _PrintNodes(self):
        for N in self._Internet.Nodes:
            Tag = f" ({type(N).__name__})" if type(N).__name__ != "Node" else ""
            print(f"      node  {N.Name}{Tag}")
            for Iface in N.Interfaces:
                Extras = ""
                if isinstance(Iface, EthernetInterface):
                    Extras = f" MAC={Iface.Mac}"
                if isinstance(Iface, IPInterface):
                    Extras = f" IP={Iface.Ip}/{Iface.PrefixLen}"
                if isinstance(Iface, EthernetIPInterface) and Iface.UdpPorts:
                    Extras += f" UDP={Iface.UdpPorts}"
                print(f"            iface {Iface.Name:<20} "
                      f"TX={Iface.TxSize} RX={Iface.RxSize} "
                      f"wire={Iface.WireName!r}{Extras}")
            if isinstance(N, Switch):
                if N.MacTable:
                    Entries = ", ".join(f"{M}->port{P}" for M, P in N.MacTable.items())
                    print(f"            MAC table: {Entries}")
                else:
                    print(f"            MAC table: (empty)")
            if isinstance(N, Router):
                if N.Routes:
                    print(f"            routes:")
                    for R in N.Routes:
                        print(f"              {R}")
                else:
                    print(f"            routes: (empty)")
            if isinstance(N, NatRouter) and N.NatTable:
                print(f"            NAT mappings:")
                for E in N.NatTable:
                    print(f"              {E.PrivateIp} <-> {E.PublicIp} "
                          f"peer={E.DstIp} id={E.Identifier}")

    @property
    def Internet(self) -> Internet:
        return self._Internet

    # ── interactive REPL ─────────────────────────────────────────────────────

    def Repl(self):
        """
        Launch an interactive console.

        Type 'help' for the command list. Ctrl-D or 'quit' to leave.
        """
        Banner = (
            f"\nmini-net controller '{self.Name}' attached to "
            f"'{self._Internet.Name}'\n"
            f"type 'help' for commands, 'quit' to exit\n"
        )
        print(Banner)

        Dispatch = {
            "help":     self._CmdHelp,
            "?":        self._CmdHelp,
            "tick":     self._CmdTick,
            "t":        self._CmdTick,
            "send":     self._CmdSend,
            "s":        self._CmdSend,
            "frame":    self._CmdFrame,
            "f":        self._CmdFrame,
            "ip":       self._CmdIp,
            "ping":     self._CmdPing,
            "udp":      self._CmdUdp,
            "u":        self._CmdUdp,
            "drain":    self._CmdDrain,
            "d":        self._CmdDrain,
            "peek":     self._CmdPeek,
            "p":        self._CmdPeek,
            "inspect":  self._CmdInspect,
            "i":        self._CmdInspect,
            "nodes":    self._CmdNodes,
            "wires":    self._CmdWires,
            "mactable": self._CmdMacTable,
            "m":        self._CmdMacTable,
            "routes":   self._CmdRoutes,
            "r":        self._CmdRoutes,
            "arp":      self._CmdArp,
            "nat":      self._CmdNat,
            "log":      self._CmdLog,
        }

        Prompt = f"{self.Name}@{self._Internet.Name}> "

        while True:
            try:
                Line = input(Prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not Line:
                continue

            try:
                Parts = shlex.split(Line)
            except ValueError as E:
                print(f"  parse error: {E}")
                continue

            Cmd, Args = Parts[0].lower(), Parts[1:]

            if Cmd in ("quit", "exit", "q"):
                break

            Handler = Dispatch.get(Cmd)
            if Handler is None:
                print(f"  unknown command: {Cmd!r}  (try 'help')")
                continue

            try:
                Handler(Args)
            except Exception as E:
                print(f"  error: {E}")

        print(f"[{self.Name}] bye")

    # ── command implementations ──────────────────────────────────────────────

    def _CmdHelp(self, _Args):
        print("""
  commands:
    send <node> <data> [dst] [seq]         queue a raw packet on a node    (alias: s)
    frame <node> <dst_mac> <data> [seq]    queue an Ethernet frame         (alias: f)
    ip <node> <dst_ip> <data> [seq] [ttl]  queue an IP packet
    ping <node> <dst_ip> [seq] [ttl]       send an ICMP echo request
    udp <node> <dst_ip> <dst_port> <data> [src_port]
                                           send a stateless UDP datagram   (alias: u)
    tick [n]                               advance the world by n ticks    (alias: t)
    drain <node> [iface]                   read & print everything in RX   (alias: d)
    peek <wire>                            show packets in flight on wire  (alias: p)
    inspect                                full snapshot of the world      (alias: i)
    mactable <switch>                      show a switch's learned table   (alias: m)
    routes <router>                        show a router's routing table   (alias: r)
    arp <node>                             show a host's ARP cache
    nat <router>                           show a NAT router's table
    nodes                                  list all nodes & interfaces
    wires                                  list all wires
    log <level>                            set log level: debug/info/warning/off
    help                                   this message                    (alias: ?)
    quit                                   exit                            (alias: q, exit, ^D)
""")

    def _CmdTick(self, Args):
        Times = int(Args[0]) if Args else 1
        self.Tick(Times)

    def _CmdSend(self, Args):
        if len(Args) < 2:
            print("  usage: send <node> <data> [dst] [seq]")
            return
        NodeName = Args[0]
        Data = Args[1].encode()
        Dst = Args[2] if len(Args) > 2 else ""
        Seq = int(Args[3]) if len(Args) > 3 else 0
        self.Send(NodeName, Data, Dst=Dst, Seq=Seq)

    def _CmdFrame(self, Args):
        if len(Args) < 3:
            print("  usage: frame <node> <dst_mac> <data> [seq]")
            return
        NodeName, DstMac, Data = Args[0], Args[1], Args[2].encode()
        Seq = int(Args[3]) if len(Args) > 3 else 0
        N = self._Internet.FindNode(NodeName)
        if not N.Interfaces:
            print(f"  {NodeName} has no interfaces")
            return
        Iface = N.Interfaces[0]
        if not isinstance(Iface, EthernetInterface):
            print(f"  {Iface.Name} is not an EthernetInterface")
            return
        if DstMac.lower() == "broadcast":
            DstMac = MAC.BROADCAST
        if not MAC.IsValid(DstMac):
            print(f"  invalid dst MAC: {DstMac!r}")
            return
        Iface.SendFrame(DstMac=DstMac, Payload=Data, Seq=Seq)
        print(f"[{self.Name}] -> {NodeName} eth0.SendFrame  "
              f"Src={Iface.Mac} Dst={DstMac} Data={Data!r}")

    def _CmdMacTable(self, Args):
        if not Args:
            print("  usage: mactable <switch>")
            return
        N = self._Internet.FindNode(Args[0])
        if not isinstance(N, Switch):
            print(f"  {Args[0]} is not a Switch")
            return
        if not N.MacTable:
            print(f"  {N.Name} MAC table is empty")
            return
        print(f"  {N.Name} MAC table:")
        for M, P in N.MacTable.items():
            print(f"    {M} -> port{P}")

    def _CmdIp(self, Args):
        if len(Args) < 3:
            print("  usage: ip <node> <dst_ip> <data> [seq] [ttl]")
            return
        NodeName, DstIp, Data = Args[0], Args[1], Args[2].encode()
        Seq = int(Args[3]) if len(Args) > 3 else 0
        TTL = int(Args[4]) if len(Args) > 4 else 64
        N = self._Internet.FindNode(NodeName)
        if not N.Interfaces:
            print(f"  {NodeName} has no interfaces")
            return
        Iface = N.Interfaces[0]
        if not isinstance(Iface, IPInterface):
            print(f"  {Iface.Name} is not an IPInterface")
            return
        if not IP.IsValid(DstIp):
            print(f"  invalid IP: {DstIp!r}")
            return
        Iface.SendIp(DstIp=DstIp, Data=Data, TTL=TTL, Seq=Seq)
        print(f"[{self.Name}] -> {NodeName}.SendIp  "
              f"Src={Iface.Ip} Dst={DstIp} TTL={TTL} Data={Data!r}")

    def _CmdRoutes(self, Args):
        if not Args:
            print("  usage: routes <router>")
            return
        N = self._Internet.FindNode(Args[0])
        if not isinstance(N, Router):
            print(f"  {Args[0]} is not a Router")
            return
        if not N.Routes:
            print(f"  {N.Name} has no routes")
            return
        print(f"  {N.Name} routing table:")
        for R in N.Routes:
            print(f"    {R}")

    def _CmdPing(self, Args):
        if len(Args) < 2:
            print("  usage: ping <node> <dst_ip> [seq] [ttl]")
            return
        NodeName, DstIp = Args[0], Args[1]
        Seq = int(Args[2]) if len(Args) > 2 else 1
        TTL = int(Args[3]) if len(Args) > 3 else 64
        if not IP.IsValid(DstIp):
            print(f"  invalid IP: {DstIp!r}")
            return
        N = self._Internet.FindNode(NodeName)
        if not N.Interfaces:
            print(f"  {NodeName} has no interfaces")
            return
        Iface = N.Interfaces[0]
        if not isinstance(Iface, EthernetIPInterface):
            print(f"  {Iface.Name} is not an EthernetIPInterface (try plain `ip`)")
            return
        Echo = EchoRequest(Src=Iface.Ip, Dst=DstIp, SeqNumber=Seq,
                           Data=b"ping", TTL=TTL)
        Iface.SendIpPacket(Echo)
        print(f"[{self.Name}] -> {NodeName}.ping  Src={Iface.Ip} Dst={DstIp} seq={Seq} TTL={TTL}")

    def _CmdArp(self, Args):
        if not Args:
            print("  usage: arp <node>")
            return
        N = self._Internet.FindNode(Args[0])
        Lines = []
        for Iface in N.Interfaces:
            if isinstance(Iface, EthernetIPInterface):
                for Ip, Mac in Iface.ArpCache.items():
                    Lines.append(f"    {Iface.Name:<22} {Ip} -> {Mac}")
                if Iface.ArpPendingCount:
                    Lines.append(f"    {Iface.Name:<22} ({Iface.ArpPendingCount} pending)")
        if not Lines:
            print(f"  {N.Name} ARP cache is empty (or no EthernetIPInterface)")
            return
        print(f"  {N.Name} ARP cache:")
        for L in Lines:
            print(L)

    def _CmdUdp(self, Args):
        if len(Args) < 4:
            print("  usage: udp <node> <dst_ip> <dst_port> <data> [src_port]")
            return
        NodeName, DstIp, DstPortStr, Data = Args[0], Args[1], Args[2], Args[3].encode()
        SrcPort = int(Args[4]) if len(Args) > 4 else 0
        try:
            DstPort = int(DstPortStr)
        except ValueError:
            print(f"  invalid port: {DstPortStr!r}")
            return
        if not IP.IsValid(DstIp):
            print(f"  invalid IP: {DstIp!r}")
            return
        N = self._Internet.FindNode(NodeName)
        if not N.Interfaces:
            print(f"  {NodeName} has no interfaces")
            return
        Iface = N.Interfaces[0]
        if not isinstance(Iface, EthernetIPInterface):
            print(f"  {Iface.Name} is not an EthernetIPInterface")
            return
        Iface.SendUdp(DstIp=DstIp, DstPort=DstPort, Data=Data, SrcPort=SrcPort)
        print(f"[{self.Name}] -> {NodeName}.SendUdp  "
              f"{Iface.Ip}:{SrcPort} -> {DstIp}:{DstPort} Data={Data!r}")

    def _CmdNat(self, Args):
        if not Args:
            print("  usage: nat <router>")
            return
        N = self._Internet.FindNode(Args[0])
        if not isinstance(N, NatRouter):
            print(f"  {Args[0]} is not a NatRouter")
            return
        Table = N.NatTable
        if not Table:
            print(f"  {N.Name} NAT table is empty")
            return
        print(f"  {N.Name} NAT table:")
        for E in Table:
            print(f"    {E.PrivateIp} <-> {E.PublicIp}   peer={E.DstIp} id={E.Identifier}")

    def _CmdDrain(self, Args):
        if not Args:
            print("  usage: drain <node> [iface]")
            return
        IfaceIndex = int(Args[1]) if len(Args) > 1 else 0
        self.Drain(Args[0], IfaceIndex)

    def _CmdPeek(self, Args):
        if not Args:
            print("  usage: peek <wire>")
            return
        self.PeekWire(Args[0])

    def _CmdInspect(self, _Args):
        self.Inspect()

    def _CmdNodes(self, _Args):
        for N in self._Internet.Nodes:
            print(f"  {N.Name}")
            for I, Iface in enumerate(N.Interfaces):
                print(f"    [{I}] {Iface.Name}  TX={Iface.TxSize} "
                      f"RX={Iface.RxSize}  wire={Iface.WireName!r}")

    def _CmdWires(self, _Args):
        for W in self._Internet.Wires:
            print(f"  {W.Name:<20} size={W.Size}  dropped={W.Dropped}")

    def _CmdLog(self, Args):
        if not Args:
            print("  usage: log <debug|info|warning|off>")
            return
        Level = Args[0].lower()
        Log = logging.getLogger("network")
        if Level == "off":
            Log.setLevel(logging.CRITICAL + 1)
            print("  logging: off")
            return
        Map = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING}
        if Level not in Map:
            print(f"  unknown level: {Level!r}")
            return
        if not Log.handlers or all(isinstance(H, logging.NullHandler) for H in Log.handlers):
            H = logging.StreamHandler()
            H.setFormatter(logging.Formatter("%(levelname)-8s %(name)s: %(message)s"))
            Log.addHandler(H)
            Log.propagate = False
        Log.setLevel(Map[Level])
        print(f"  logging: {Level}")
