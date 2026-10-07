"""Simulated PLC <-> MES handshake over OPC UA-style tags.

On the real line, an Allen-Bradley ControlLogix/CompactLogix PLC exposes these tags
over OPC UA (via Ignition / Kepware / FactoryTalk Linx). The handshake is the same:

    1. PLC writes the scanned serial and sets  <OP>.ReqToMES = 1
    2. MES checks the route/interlock and writes <OP>.MESRelease (1 = OK, 0 = block)
       plus <OP>.MESReasonCode, then sets       <OP>.MESAck = 1
    3. PLC cycles, writes results and sets      <OP>.ResultReady = 1
    4. MES stores results and sets              <OP>.ResultAck = 1
    5. PLC clears its flags; MES clears its acks
"""
from dataclasses import dataclass, field

REASON_CODES = {
    0: "OK",
    1: "Unknown serial",
    2: "Previous operation not complete",
    3: "Operation already complete",
    4: "Unit on non-conformance hold",
    5: "Wrong part for variant",
    6: "Component lot on containment hold",
    7: "Component serial already used",
    8: "Unit scrapped",
}


@dataclass
class TagServer:
    """A dictionary of tag paths standing in for an OPC UA address space."""
    tags: dict[str, object] = field(default_factory=dict)

    def write(self, path: str, value) -> None:
        self.tags[path] = value

    def read(self, path: str, default=None):
        return self.tags.get(path, default)

    def node_id(self, path: str) -> str:
        return f"ns=2;s=[Line1]{path}"


def tag(op: str, name: str) -> str:
    return f"{op}.{name}"


def handshake(server: TagServer, mes, op: str, serial: str) -> tuple[bool, str]:
    """Run the request/release half of the handshake and return the MES decision."""
    server.write(tag(op, "Serial"), serial)
    server.write(tag(op, "ReqToMES"), 1)
    ok, code = mes.station_request(serial, op)
    server.write(tag(op, "MESRelease"), int(ok))
    server.write(tag(op, "MESReasonCode"), code)
    server.write(tag(op, "MESAck"), 1)
    server.write(tag(op, "ReqToMES"), 0)
    server.write(tag(op, "MESAck"), 0)
    return ok, REASON_CODES[code]
