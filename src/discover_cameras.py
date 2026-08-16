"""Discover ONVIF cameras and print an RTSP URI as JSON."""

from __future__ import annotations

import argparse
import json
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


def discover(timeout: float) -> list[dict[str, Any]]:
    from onvif import ONVIFDiscovery

    return [_json_value(device) for device in ONVIFDiscovery(timeout=timeout).discover()]


def rtsp_uri(host: str, port: int, username: str, password: str) -> dict[str, Any]:
    from onvif import ONVIFClient
    from onvif.operator import CacheMode

    media = ONVIFClient(host, port, username, password, cache=CacheMode.NONE).media()
    profiles = media.GetProfiles()
    if not profiles:
        raise RuntimeError("camera returned no media profiles")

    profile = profiles[0]
    token = _value(profile, "token") or _value(profile, "Token")
    if not token:
        raise RuntimeError("first media profile has no token")

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
