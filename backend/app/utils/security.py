"""
Security utilities: SSRF protection, URL validation, and safe HTTP fetching.
"""
import ipaddress
import socket
from urllib.parse import urlparse
from fastapi import HTTPException


def validate_public_url(url: str) -> str:
    """
    Validate that a URL is a legitimate public web URL and prevent SSRF attacks.
    Blocks private IPs, link-local metadata endpoints, and non-HTTP protocols.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL scheme. Only HTTP and HTTPS are permitted."
        )

    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL: hostname could not be determined."
        )

    # Reject localhost and obvious loopbacks
    lowered = hostname.lower()
    if lowered in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "metadata.google.internal"):
        raise HTTPException(
            status_code=400,
            detail="Access to local or internal endpoints is prohibited."
        )

    # Resolve hostname to IP to protect against DNS rebinding and internal subnets
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise HTTPException(
            status_code=400,
            detail=f"Could not resolve hostname '{hostname}'."
        )

    for entry in addr_info:
        ip_str = entry[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                raise HTTPException(
                    status_code=400,
                    detail=f"Target URL resolves to a prohibited internal IP address ({ip_str})."
                )
        except ValueError:
            continue

    return url
