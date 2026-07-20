#!/bin/bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  bootstrap-macos.sh --device LABEL --host HOSTNAME --user USER --project ABSOLUTE_PATH [--alias NAME] [--prepare-only | --skip-register]

Example:
  bootstrap-macos.sh --device macbook --host devbox.example.ts.net --user developer --project /home/developer/project
EOF
}

fail() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

DEVICE=""
REMOTE_HOST=""
REMOTE_USER=""
REMOTE_PROJECT=""
HOST_ALIAS="linear-dev"
PREPARE_ONLY=0
SKIP_REGISTER=0

while [ "$#" -gt 0 ]; do
    case "$1" in
        --device) [ "$#" -ge 2 ] || fail "--device needs a value"; DEVICE="$2"; shift 2 ;;
        --host) [ "$#" -ge 2 ] || fail "--host needs a value"; REMOTE_HOST="$2"; shift 2 ;;
        --user) [ "$#" -ge 2 ] || fail "--user needs a value"; REMOTE_USER="$2"; shift 2 ;;
        --project) [ "$#" -ge 2 ] || fail "--project needs a value"; REMOTE_PROJECT="$2"; shift 2 ;;
        --alias) [ "$#" -ge 2 ] || fail "--alias needs a value"; HOST_ALIAS="$2"; shift 2 ;;
        --prepare-only) PREPARE_ONLY=1; shift ;;
        --skip-register) SKIP_REGISTER=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; fail "unknown argument: $1" ;;
    esac
done

[ -n "$DEVICE" ] || { usage >&2; fail "--device is required"; }
[ -n "$REMOTE_HOST" ] || { usage >&2; fail "--host is required"; }
[ -n "$REMOTE_USER" ] || { usage >&2; fail "--user is required"; }
[ -n "$REMOTE_PROJECT" ] || { usage >&2; fail "--project is required"; }

case "$DEVICE" in [!A-Za-z0-9]*|*[!A-Za-z0-9_-]*|*[-_]|'') fail "device must start and end with an alphanumeric character and use only letters, digits, _ or -" ;; esac
case "$REMOTE_HOST" in [!A-Za-z0-9]*|*[!A-Za-z0-9.-]*|*[.-]|'') fail "host name contains unsupported characters" ;; esac
case "$REMOTE_USER" in [!A-Za-z_]*|*[!A-Za-z0-9_-]*|'') fail "user name contains unsupported characters" ;; esac
case "$HOST_ALIAS" in [!A-Za-z0-9]*|*[!A-Za-z0-9._-]*|*[._-]|'') fail "host alias contains unsupported characters" ;; esac
[ "${#DEVICE}" -le 32 ] || fail "device label is too long"
[ "${#REMOTE_HOST}" -le 253 ] || fail "host name is too long"
[ "${#REMOTE_USER}" -le 32 ] || fail "user name is too long"
[ "${#HOST_ALIAS}" -le 63 ] || fail "host alias is too long"
case "$REMOTE_PROJECT" in /*) ;; *) fail "project must be an absolute Linux path" ;; esac
case "$REMOTE_PROJECT" in *"'"*|*$'\n'*|*$'\r'*) fail "project path cannot contain quotes or line breaks" ;; esac
[ "$PREPARE_ONLY" -eq 0 ] || [ "$SKIP_REGISTER" -eq 0 ] || fail "use only one of --prepare-only and --skip-register"

DEVICE="$(printf '%s' "$DEVICE" | tr '[:upper:]' '[:lower:]')"
REMOTE_HOST="$(printf '%s' "$REMOTE_HOST" | tr '[:upper:]' '[:lower:]')"
HOST_ALIAS="$(printf '%s' "$HOST_ALIAS" | tr '[:upper:]' '[:lower:]')"

SSH="/usr/bin/ssh"
SSH_KEYGEN="/usr/bin/ssh-keygen"
SSH_ADD="/usr/bin/ssh-add"
[ -x "$SSH" ] || fail "macOS OpenSSH ssh is required"
[ -x "$SSH_KEYGEN" ] || fail "macOS OpenSSH ssh-keygen is required"
[ -x "$SSH_ADD" ] || fail "macOS OpenSSH ssh-add is required"

TAILSCALE=""
if command -v tailscale >/dev/null 2>&1; then
    TAILSCALE="$(command -v tailscale)"
elif [ -x /Applications/Tailscale.app/Contents/MacOS/Tailscale ]; then
    TAILSCALE="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
fi
[ -n "$TAILSCALE" ] || fail "Install and sign in to Tailscale first: https://tailscale.com/download/mac"

printf 'Checking Tailscale connection...\n'
TAILSCALE_BE_CLI=1 "$TAILSCALE" status >/dev/null || fail "Sign in to Tailscale and connect this Mac first"

SSH_DIR="$HOME/.ssh"
KEY_ALIAS="$(printf '%s' "$HOST_ALIAS" | tr '.-' '__')"
if [ "$HOST_ALIAS" != "linear-dev" ]; then
    command -v shasum >/dev/null 2>&1 || fail "shasum is required for a custom host alias"
    ALIAS_HASH="$(printf '%s' "$HOST_ALIAS" | shasum -a 256 | awk '{ print substr($1, 1, 12) }')"
    KEY_ALIAS="${KEY_ALIAS}_${ALIAS_HASH}"
fi
KEY_NAME="id_ed25519_${KEY_ALIAS}_${DEVICE}"
KEY_PATH="$SSH_DIR/$KEY_NAME"
PUBLIC_KEY_PATH="$KEY_PATH.pub"
CONFIG_PATH="$SSH_DIR/config"
BEGIN_MARKER="# BEGIN CODEX SSH HOST $HOST_ALIAS"
END_MARKER="# END CODEX SSH HOST $HOST_ALIAS"

mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [ ! -e "$KEY_PATH" ] && [ -e "$PUBLIC_KEY_PATH" ]; then
    fail "public key exists without its private key: $PUBLIC_KEY_PATH"
elif [ ! -f "$KEY_PATH" ]; then
    printf '\nCreating a dedicated SSH key for %s. A passphrase is recommended.\n' "$DEVICE"
    "$SSH_KEYGEN" -t ed25519 -a 64 -f "$KEY_PATH" -C "macos-$DEVICE-to-$HOST_ALIAS"
elif [ ! -f "$PUBLIC_KEY_PATH" ]; then
    printf 'Rebuilding the missing public key: %s\n' "$PUBLIC_KEY_PATH"
    "$SSH_KEYGEN" -y -f "$KEY_PATH" > "$PUBLIC_KEY_PATH"
else
    printf 'Reusing the existing key: %s\n' "$KEY_PATH"
fi

PRIVATE_FINGERPRINT="$("$SSH_KEYGEN" -lf "$KEY_PATH" -E sha256 | awk '{ print $2; exit }')" || fail "could not inspect the private key"
PUBLIC_FINGERPRINT="$("$SSH_KEYGEN" -lf "$PUBLIC_KEY_PATH" -E sha256 | awk '{ print $2; exit }')" || fail "could not inspect the public key"
[ "$PRIVATE_FINGERPRINT" = "$PUBLIC_FINGERPRINT" ] || fail "private and public keys do not match"
chmod 600 "$KEY_PATH"
chmod 644 "$PUBLIC_KEY_PATH"

REMAINING_CONFIG=""
CONFIG_TEMP=""
EMPTY_CONFIG=""
cleanup() {
    [ -z "${REMAINING_CONFIG:-}" ] || rm -f "$REMAINING_CONFIG"
    [ -z "${CONFIG_TEMP:-}" ] || rm -f "$CONFIG_TEMP"
    [ -z "${EMPTY_CONFIG:-}" ] || rm -f "$EMPTY_CONFIG"
}
trap cleanup EXIT
trap 'exit 130' HUP INT TERM

REMAINING_CONFIG="$(mktemp "${TMPDIR:-/tmp}/codex-ssh-remaining.XXXXXX")"
CONFIG_TEMP="$(mktemp "$SSH_DIR/config.codex-tmp.XXXXXX")"

if [ -L "$CONFIG_PATH" ]; then
    fail "SSH config is a symlink; update it manually instead of replacing it: $CONFIG_PATH"
elif [ -e "$CONFIG_PATH" ] && [ ! -f "$CONFIG_PATH" ]; then
    fail "SSH config is not a regular file: $CONFIG_PATH"
elif [ -f "$CONFIG_PATH" ]; then
    if ! awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
        BEGIN { skipping = 0; seen_begin = 0; seen_end = 0 }
        $0 == begin {
            if (skipping || seen_begin) exit 41
            skipping = 1
            seen_begin = 1
            next
        }
        $0 == end {
            if (!skipping || seen_end) exit 42
            skipping = 0
            seen_end = 1
            next
        }
        !skipping { print }
        END {
            if (skipping || seen_begin != seen_end) exit 43
        }
    ' "$CONFIG_PATH" > "$REMAINING_CONFIG"; then
        fail "managed SSH config markers are malformed in $CONFIG_PATH"
    fi
else
    : > "$REMAINING_CONFIG"
fi

{
    printf '%s\n' "$BEGIN_MARKER"
    printf 'Host %s\n' "$HOST_ALIAS"
    printf '    HostName %s\n' "$REMOTE_HOST"
    printf '    User %s\n' "$REMOTE_USER"
    printf '    IdentityFile ~/.ssh/%s\n' "$KEY_NAME"
    printf '    IdentitiesOnly yes\n'
    printf '    ForwardAgent no\n'
    printf '    ServerAliveInterval 30\n'
    printf '    ServerAliveCountMax 3\n'
    printf '    IgnoreUnknown UseKeychain\n'
    printf '    UseKeychain yes\n'
    printf '    AddKeysToAgent yes\n'
    printf 'Host *\n'
    printf '%s\n' "$END_MARKER"
    [ ! -s "$REMAINING_CONFIG" ] || cat "$REMAINING_CONFIG"
} > "$CONFIG_TEMP"

BACKUP_PATH=""
if [ -f "$CONFIG_PATH" ]; then
    BACKUP_PATH="$(mktemp "$CONFIG_PATH.bak.$(date +%Y%m%d-%H%M%S).XXXXXX")"
    cp -p "$CONFIG_PATH" "$BACKUP_PATH"
    printf 'Existing SSH config backup: %s\n' "$BACKUP_PATH"
fi
mv -f "$CONFIG_TEMP" "$CONFIG_PATH"
CONFIG_TEMP=""
chmod 600 "$CONFIG_PATH"

restore_config_and_fail() {
    if [ -n "$BACKUP_PATH" ]; then
        cp -p "$BACKUP_PATH" "$CONFIG_PATH"
    else
        rm -f "$CONFIG_PATH"
    fi
    fail "$*"
}

RESOLVED_CONFIG="$("$SSH" -G "$HOST_ALIAS" 2>/dev/null)" || restore_config_and_fail "could not resolve SSH config"
RESOLVED_HOST="$(printf '%s\n' "$RESOLVED_CONFIG" | awk '$1 == "hostname" { print $2; exit }')"
RESOLVED_USER="$(printf '%s\n' "$RESOLVED_CONFIG" | awk '$1 == "user" { print $2; exit }')"
RESOLVED_IDENTITIES_ONLY="$(printf '%s\n' "$RESOLVED_CONFIG" | awk '$1 == "identitiesonly" { print $2; exit }')"
RESOLVED_IDENTITY="$(printf '%s\n' "$RESOLVED_CONFIG" | awk '$1 == "identityfile" { print $2; exit }')"
[ "$RESOLVED_HOST" = "$REMOTE_HOST" ] || restore_config_and_fail "resolved HostName does not match"
[ "$RESOLVED_USER" = "$REMOTE_USER" ] || restore_config_and_fail "resolved User does not match"
[ "$RESOLVED_IDENTITIES_ONLY" = "yes" ] || restore_config_and_fail "IdentitiesOnly is not enabled"
case "$RESOLVED_IDENTITY" in "$KEY_PATH"|"~/.ssh/$KEY_NAME") ;; *) restore_config_and_fail "resolved IdentityFile does not match" ;; esac

printf '\nAdding the key to the macOS Keychain and ssh-agent...\n'
if "$SSH_ADD" --apple-use-keychain "$KEY_PATH" 2>/dev/null; then
    :
elif "$SSH_ADD" "$KEY_PATH" 2>/dev/null; then
    :
else
    printf 'Warning: ssh-add failed. The key still works, but its passphrase may be requested again.\n' >&2
fi

if [ "$PREPARE_ONLY" -eq 1 ]; then
    printf '\nLocal key and SSH config are ready.\n'
    printf 'Public key: %s\n' "$PUBLIC_KEY_PATH"
    printf 'Register that .pub line from an already approved client, then rerun this command with --skip-register.\n'
    exit 0
fi

REGISTER_COMMAND='umask 077
mkdir -p ~/.ssh
touch ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
IFS= read -r key
case "$key" in ssh-ed25519\ *) ;; *) exit 64 ;; esac
if ! grep -qxF -- "$key" ~/.ssh/authorized_keys; then
    if [ -s ~/.ssh/authorized_keys ]; then printf "\n" >> ~/.ssh/authorized_keys; fi
    printf "%s\n" "$key" >> ~/.ssh/authorized_keys
fi'

EMPTY_CONFIG="$(mktemp "${TMPDIR:-/tmp}/codex-ssh-empty.XXXXXX")"
if [ "$SKIP_REGISTER" -eq 0 ] && "$SSH" \
    -F "$EMPTY_CONFIG" \
    -i "$KEY_PATH" \
    -o IdentityAgent=none \
    -o IdentitiesOnly=yes \
    -o PreferredAuthentications=publickey \
    -o PasswordAuthentication=no \
    -o KbdInteractiveAuthentication=no \
    "$REMOTE_USER@$REMOTE_HOST" true; then
    printf '\nThe exact key is already authorized; skipping password registration.\n'
elif [ "$SKIP_REGISTER" -eq 0 ]; then
    printf '\nRegistering the public key. Enter the remote Linux account password once.\n'
    "$SSH" \
        -F "$EMPTY_CONFIG" \
        -o PreferredAuthentications=password \
        -o PasswordAuthentication=yes \
        -o PubkeyAuthentication=no \
        -o KbdInteractiveAuthentication=no \
        -o IdentitiesOnly=yes \
        "$REMOTE_USER@$REMOTE_HOST" \
        "$REGISTER_COMMAND" < "$PUBLIC_KEY_PATH" || fail "public-key registration failed; use --prepare-only if password SSH is disabled"
else
    printf '\nSkipping password registration; the public key must already be authorized on the host.\n'
fi

printf '\nVerifying the exact key, remote Codex, and repository...\n'
"$SSH" \
    -F "$EMPTY_CONFIG" \
    -i "$KEY_PATH" \
    -o IdentityAgent=none \
    -o IdentitiesOnly=yes \
    -o PreferredAuthentications=publickey \
    -o PasswordAuthentication=no \
    -o KbdInteractiveAuthentication=no \
    "$REMOTE_USER@$REMOTE_HOST" \
    "codex --version && cd '$REMOTE_PROJECT' && git status --short --branch" || fail "exact-key verification failed"

printf '\nSetup complete: %s -> %s\n' "$DEVICE" "$HOST_ALIAS"
printf 'Desktop app: Settings > Connections > %s\n' "$HOST_ALIAS"
printf 'Remote project: %s\n' "$REMOTE_PROJECT"
