"""Discover ONVIF cameras and print an RTSP URI as JSON."""

from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import socket
import sys
from typing import Any


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _json_value(item: Any) -> Any:
    """Convert the small set of library response objects used by this CLI."""
    if item is None or isinstance(item, (str, int, float, bool)):
        return item
    if isinstance(item, dict):
        return {str(key): _json_value(value) for key, value in item.items()}
    if isinstance(item, (list, tuple)):
        return [_json_value(value) for value in item]
    return {
        name: _json_value(value)
        for name in ("host", "port", "scopes", "xaddrs", "token", "Name", "Uri")
        if (value := _value(item, name)) is not None
    }


_ONVIF_PORTS = (80, 8000, 8080, 8899, 5000, 3702)


def _local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def _is_onvif(host: str, port: int, timeout: float) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.sendall(
            f"GET /onvif/device_service HTTP/1.0\r\nHost: {host}\r\n\r\n".encode()
        )
        response = s.recv(256).decode(errors="ignore")
        # gSOAP / ONVIF endpoints answer with XML (even a SOAP fault) instead
        # of an HTML 404, so only treat XML responses as ONVIF devices.
        return any(
            "text/xml" in line or "soap+xml" in line
            for line in response.split("\r\n")
        )
    except OSError:
        return False
    finally:
        s.close()


def _scan_subnet(timeout: float) -> list[dict[str, Any]]:
    """Scan the local /24 for hosts answering on an ONVIF device service.

    ponytail: assumes /24 netmask (covers typical LANs); hosts on other masks
    can still be handled with --host. WS-Discovery is unreliable here, so a
    TCP scan is the fallback that actually finds the camera.
    """
    local = _local_ip()
    network = ipaddress.ip_network(f"{local}/24", strict=False)

    def probe(host: str) -> list[dict[str, Any]]:
        found = []
        for port in _ONVIF_PORTS:
            if _is_onvif(host, port, timeout):
                found.append({"host": host, "port": port})
        return found

    devices = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as pool:
        futures = [pool.submit(probe, str(ip)) for ip in network.hosts()]
        for future in concurrent.futures.as_completed(futures):
            devices.extend(future.result())
    return devices


def discover(timeout: float) -> list[dict[str, Any]]:
    from onvif import ONVIFDiscovery

    devices = [
        _json_value(device) for device in ONVIFDiscovery(timeout=timeout).discover()
    ]
    # Many cameras ignore WS-Discovery probes; fall back to a subnet scan.
    if not devices:
        devices = _scan_subnet(timeout)
    return devices


def list_profiles(host: str, port: int, username: str, password: str) -> list[dict[str, Any]]:
    from onvif import ONVIFClient
    from onvif.operator import CacheMode

    media = ONVIFClient(host, port, username, password, cache=CacheMode.NONE).media()
    profiles = media.GetProfiles()
    if not profiles:
        raise RuntimeError("camera returned no media profiles")

    result = []
    for profile in profiles:
        token = _value(profile, "token") or _value(profile, "Token")
        if not token:
            continue
        name = _value(profile, "Name") or _value(profile, "name")
        result.append({"token": str(token), "name": str(name or token)})
    return result


def rtsp_uri(
    host: str,
    port: int,
    username: str,
    password: str,
    profile_token: str | None = None,
) -> dict[str, Any]:
    from onvif import ONVIFClient
    from onvif.operator import CacheMode

    media = ONVIFClient(host, port, username, password, cache=CacheMode.NONE).media()
    profiles = media.GetProfiles()
    if not profiles:
        raise RuntimeError("camera returned no media profiles")

    if profile_token is None:
        profile = profiles[0]
    else:
        profile = next(
            (
                p
                for p in profiles
                if str(_value(p, "token") or _value(p, "Token")) == str(profile_token)
            ),
            None,
        )
        if not profile:
            raise RuntimeError(f"media profile '{profile_token}' not found")

    token = _value(profile, "token") or _value(profile, "Token")
    if not token:
        raise RuntimeError("media profile has no token")

    stream = media.GetStreamUri(
        ProfileToken=token,
        StreamSetup={"Stream": "RTP-Unicast", "Transport": {"Protocol": "RTSP"}},
    )
    uri = _value(stream, "Uri") or _value(stream, "uri")
    if not uri:
        raise RuntimeError("camera returned no RTSP URI")

    return {
        "host": host,
        "port": port,
        "profile": {
            "token": token,
            "name": _value(profile, "Name") or _value(profile, "name"),
        },
        "rtsp_uri": uri,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=5, help="discovery timeout in seconds")
    parser.add_argument("--host", help="camera IP address or hostname")
    parser.add_argument("--port", type=int, default=80, help="camera ONVIF port")
    parser.add_argument("--username", help="camera username")
    parser.add_argument("--password", help="camera password")
    parser.add_argument("--rtsp", action="store_true", help="look up an RTSP URI for --host")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.rtsp:
            if not args.host or args.username is None or args.password is None:
                raise ValueError("--rtsp requires --host, --username, and --password")
            result = rtsp_uri(args.host, args.port, args.username, args.password)
        else:
            result = {"devices": discover(args.timeout)}
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
