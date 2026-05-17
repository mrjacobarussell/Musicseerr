#!/bin/sh
set -e
umask 027

PUID=${PUID:-1000}
PGID=${PGID:-1000}

case "$PUID" in ''|*[!0-9]*) echo "[init] FATAL: PUID='$PUID' is not a valid numeric UID."; exit 1;; esac
case "$PGID" in ''|*[!0-9]*) echo "[init] FATAL: PGID='$PGID' is not a valid numeric GID."; exit 1;; esac

check_writable() {
    _dir="$1"
    _identity="$2"
    _probe="$_dir/.musicseerr_write_test_$$"
    if [ -n "$_identity" ]; then
        gosu "$_identity" touch "$_probe" 2>/dev/null; _rc=$?
        gosu "$_identity" rm -f "$_probe" 2>/dev/null
    else
        touch "$_probe" 2>/dev/null; _rc=$?
        rm -f "$_probe" 2>/dev/null
    fi
    return "$_rc"
}

if [ "$(id -u)" -ne 0 ]; then
    echo "[init] Running as uid=$(id -u) gid=$(id -g) (non-root); skipping user/group setup."
    for dir in /app/cache /app/config; do
        mkdir -p "$dir" 2>/dev/null || true
        if ! check_writable "$dir"; then
            echo "[init] FATAL: $dir is not writable by uid=$(id -u)."
            echo "[init]   Ensure the host directory is owned by this UID/GID."
            echo "[init]   Run: chown $(id -u):$(id -g) <host-path>"
            exit 1
        fi
    done
    exec "$@"
fi

if ! groupmod -o -g "$PGID" musicseerr 2>/dev/null; then
    echo "[init] WARNING: Could not set musicseerr group to GID=$PGID."
fi
if ! usermod -o -u "$PUID" musicseerr 2>/dev/null; then
    echo "[init] WARNING: Could not set musicseerr user to UID=$PUID."
fi

TARGET_UID=$(id -u musicseerr)
TARGET_GID=$(id -g musicseerr)
echo "[init] Runtime user: musicseerr (uid=$TARGET_UID gid=$TARGET_GID)"

if [ "$TARGET_UID" != "$PUID" ]; then
    echo "[init] WARNING: Requested PUID=$PUID but running as uid=$TARGET_UID (usermod may have failed)."
fi
if [ "$TARGET_GID" != "$PGID" ]; then
    echo "[init] WARNING: Requested PGID=$PGID but running as gid=$TARGET_GID (groupmod may have failed)."
fi

for dir in /app/cache /app/config; do
    mkdir -p "$dir" 2>/dev/null || true

    if check_writable "$dir" "$TARGET_UID:$TARGET_GID"; then
        continue
    fi

    if chown musicseerr:musicseerr "$dir" 2>/dev/null; then
        echo "[init] Adjusted ownership of $dir - verifying write access."
    else
        echo "[init] WARNING: Could not chown $dir (mount may not support ownership changes)."
    fi

    if ! check_writable "$dir" "$TARGET_UID:$TARGET_GID"; then
        echo "[init] FATAL: $dir is not writable by uid=$TARGET_UID gid=$TARGET_GID."
        echo "[init]   Common causes: FUSE/shfs (Unraid), NFS root_squash, CIFS/SMB, dropped CAP_CHOWN."
        echo "[init]   Fix: ensure the host directory is writable by uid=$TARGET_UID gid=$TARGET_GID."
        exit 1
    fi
done

# ── SSL cert generation ───────────────────────────────────────────────────────
if [ "${SSL_AUTO:-false}" = "true" ] && [ -z "$SSL_CERTFILE" ]; then
    SSL_DIR="${SSL_AUTO_DIR:-/app/config/ssl}"
    SSL_HOST="${SSL_AUTO_HOSTNAME:-musicseerr}"
    mkdir -p "$SSL_DIR" 2>/dev/null || true
    chown musicseerr:musicseerr "$SSL_DIR" 2>/dev/null || true

    if [ ! -f "$SSL_DIR/cert.pem" ] || [ ! -f "$SSL_DIR/key.pem" ]; then
        echo "[init] SSL: generating self-signed certificate for '$SSL_HOST' ..."
        gosu musicseerr:musicseerr openssl req -x509 -newkey rsa:4096 \
            -keyout "$SSL_DIR/key.pem" \
            -out    "$SSL_DIR/cert.pem" \
            -days 3650 -nodes \
            -subj "/CN=$SSL_HOST/O=MusicSeerr/OU=Self-Signed" \
            -addext "subjectAltName=DNS:$SSL_HOST,DNS:localhost,DNS:*.local,IP:127.0.0.1" \
            2>/dev/null \
        && echo "[init] SSL: certificate generated at $SSL_DIR/cert.pem" \
        || echo "[init] SSL: WARNING - certificate generation failed; falling back to HTTP"
    else
        echo "[init] SSL: reusing existing certificate at $SSL_DIR/cert.pem"
    fi

    if [ -f "$SSL_DIR/cert.pem" ] && [ -f "$SSL_DIR/key.pem" ]; then
        export SSL_CERTFILE="$SSL_DIR/cert.pem"
        export SSL_KEYFILE="$SSL_DIR/key.pem"
    fi
fi

exec gosu musicseerr:musicseerr "$@"
