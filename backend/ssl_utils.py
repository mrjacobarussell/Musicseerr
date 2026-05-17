"""
SSL certificate utilities for MusicSeerr.

Generates a self-signed certificate when SSL_AUTO=true, so the server can
run HTTPS out of the box without any manual openssl commands.

The cert is stored in the config directory and reused across restarts.
When switching to real certs (Let's Encrypt, Cloudflare Origin, etc.),
just set SSL_CERTFILE and SSL_KEYFILE instead.
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_CERT_FILE = "cert.pem"
_KEY_FILE  = "key.pem"


def ensure_self_signed_cert(cert_dir: str, hostname: str = "musicseerr") -> tuple[str, str]:
    """
    Return (certfile_path, keyfile_path), generating a self-signed cert
    if one does not already exist in cert_dir.

    The certificate is valid for 10 years and includes the hostname plus
    common LAN/Tailscale alternatives as Subject Alternative Names so
    browsers don't complain about mismatched hostnames.
    """
    dir_path  = Path(cert_dir)
    cert_path = dir_path / _CERT_FILE
    key_path  = dir_path / _KEY_FILE

    if cert_path.exists() and key_path.exists():
        logger.info("SSL: reusing existing cert at %s", cert_path)
        return str(cert_path), str(key_path)

    dir_path.mkdir(parents=True, exist_ok=True)
    logger.info("SSL: generating self-signed certificate for '%s' in %s", hostname, cert_path)

    san = (
        f"DNS:{hostname},"
        f"DNS:localhost,"
        f"DNS:*.local,"
        f"IP:127.0.0.1,"
        f"IP:0.0.0.0"
    )
    subject = f"/CN={hostname}/O=MusicSeerr/OU=Self-Signed"

    cmd = [
        "openssl", "req",
        "-x509",
        "-newkey", "rsa:4096",
        "-keyout", str(key_path),
        "-out",    str(cert_path),
        "-days",   "3650",
        "-nodes",
        "-subj",   subject,
        "-addext", f"subjectAltName={san}",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        logger.info("SSL: certificate generated successfully")
    except FileNotFoundError:
        raise RuntimeError(
            "openssl not found. Install openssl or provide SSL_CERTFILE + SSL_KEYFILE manually."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("openssl timed out generating certificate")

    # Lock down key permissions
    os.chmod(key_path, 0o600)

    return str(cert_path), str(key_path)


def resolve_ssl_config(
    ssl_auto: bool,
    ssl_auto_dir: str,
    ssl_auto_hostname: str,
    ssl_certfile: str | None,
    ssl_keyfile:  str | None,
) -> tuple[str | None, str | None]:
    """
    Return (certfile, keyfile) based on environment config, or (None, None)
    for plain HTTP.
    """
    if ssl_certfile and ssl_keyfile:
        logger.info("SSL: using provided cert files")
        return ssl_certfile, ssl_keyfile

    if ssl_auto:
        return ensure_self_signed_cert(ssl_auto_dir, ssl_auto_hostname)

    return None, None
