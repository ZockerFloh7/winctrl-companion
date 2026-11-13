"""Command-server IP policy. Uses TCP peer IP; never trusts forwarded headers."""
import ipaddress
import threading
from collections import OrderedDict
from datetime import datetime, timezone

_lock = threading.Lock()
_seen = OrderedDict()


def normalize_entries(entries):
    if isinstance(entries, str):
        entries = entries.replace(",", "\n").splitlines()
    if not isinstance(entries, list):
        raise ValueError("IP-Whitelist muss eine Liste oder zeilenweiser Text sein.")
    result = []
    for raw in entries:
        item = str(raw).strip()
        if not item:
            continue
        try:
            network = ipaddress.ip_network(item, strict=False)
        except ValueError as exc:
            raise ValueError(f"Ungültige IP-Adresse oder CIDR-Netz: {item}") from exc
        normalized = str(network) if "/" in item else str(network.network_address)
        if normalized not in result:
            result.append(normalized)
    return result


def allowed(peer, config):
    address = ipaddress.ip_address(peer)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if not config.get("ip_whitelist_enabled", False):
        return True
    entries = normalize_entries(config.get("ip_whitelist", []))
    for item in entries:
        net = ipaddress.ip_network(item, strict=False)
        if address.version == net.version and address in net:
            return True
    return False


def observe(peer, permitted, authenticated=False):
    with _lock:
        previous = _seen.pop(peer, {})
        _seen[peer] = dict(ip=peer, last_seen=datetime.now(timezone.utc).isoformat(),
                           allowed=bool(permitted), authenticated=bool(authenticated),
                           requests=previous.get("requests", 0) + 1)
        while len(_seen) > 100:
            _seen.popitem(last=False)


def clients():
    with _lock:
        return [dict(value) for value in reversed(list(_seen.values()))]
