#!/bin/bash
# agoge-nested-finalize: answers a NESTED_FINALIZE on a nested host's template server.
# Long-polls the instance metadata for agoge-nested-finalize = <nonce>, and for each new nonce:
#  1. ACPI-shuts down every guest that is not shut off, in parallel, and waits up to
#     @@SHUTDOWN_SECONDS@@ s. A guest still running fails the finalize; it is never force-stopped.
#  2. Drops any managed save, then (re)creates the internal agoge-pristine snapshot of every guest.
#  3. Removes the media, the secrets tmpfs, the builder's state and work directories, and the apt
#     cache, then trims the disk.
#  4. Leaves the guests shut off (the runtime starts them at the next boot) and writes
#     agoge-nested/finalize-result = ok:<nonce>, or error:<nonce>:<message> on any failure.
# The Cloud Function removes the metadata key after reading the answer; the last answered nonce is
# remembered so the same request is never answered twice.
# Must stay bash 3.2-clean: the tests run it on macOS's bash.
set -o pipefail

# The root prefix exists for the tests, which run this without root.
ROOT="${AGOGE_NESTED_ROOT:-}"
METADATA=http://metadata.google.internal/computeMetadata/v1
ATTRIBUTES_URL="$METADATA/instance/guest-attributes/agoge-nested"
NONCE_KEY=agoge-nested-finalize
HOST_JSON="$ROOT@@HOST_JSON@@"
MEDIA_DIR="$ROOT@@MEDIA_DIR@@"
RUN_DIR="$ROOT@@RUN_DIR@@"
STATE_DIR="$ROOT@@STATE_DIR@@"
WORK_DIR="$ROOT@@WORK_DIR@@"
ANSWERED="$ROOT@@ANSWERED_PATH@@"
APT_CACHE="$ROOT/var/cache/apt/archives"
LOG_FILE="$ROOT/var/log/agoge-nested-finalize.log"
SNAPSHOT=agoge-pristine
SHUTDOWN_SECONDS=@@SHUTDOWN_SECONDS@@
POLL_TIMEOUT_SECONDS=60
# Set by the tests: exit after this many polls instead of polling forever.
MAX_POLLS="${AGOGE_NESTED_FINALIZE_POLLS:-0}"

# stderr: the steps' stdout carries their failure message.
log() {
  echo "agoge-nested-finalize: $*" >&2
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG_FILE" 2>/dev/null
}

put_attribute() {
  local value=${2:0:200}
  curl -sf -X PUT -H 'Metadata-Flavor: Google' --data "$value" "$ATTRIBUTES_URL/$1" >/dev/null \
    || log "could not write guest attribute $1"
}

guests() {
  jq -r '.guests[].name' "$HOST_JSON"
}

shut_down_guests() {
  local guest waited=0 pending=""
  for guest in $(guests); do
    if [ "$(virsh domstate "$guest" 2>/dev/null)" != "shut off" ]; then
      log "shutting down $guest"
      virsh shutdown "$guest" >/dev/null 2>&1 &
      pending="$pending $guest"
    fi
  done
  wait
  while [ -n "$pending" ]; do
    local still=""
    for guest in $pending; do
      [ "$(virsh domstate "$guest" 2>/dev/null)" = "shut off" ] || still="$still $guest"
    done
    pending=$still
    [ -z "$pending" ] && return 0
    if [ "$waited" -ge "$SHUTDOWN_SECONDS" ]; then
      set -- $pending
      echo "$1: guest did not shut down"
      return 1
    fi
    sleep 5
    waited=$((waited + 5))
  done
}

snapshot_guests() {
  local guest
  for guest in $(guests); do
    virsh managedsave-remove "$guest" >/dev/null 2>&1
    if virsh snapshot-list "$guest" --name 2>/dev/null | grep -qx "$SNAPSHOT"; then
      virsh snapshot-delete "$guest" "$SNAPSHOT" >/dev/null 2>&1 || {
        echo "$guest: could not delete the old $SNAPSHOT snapshot"
        return 1
      }
    fi
    virsh snapshot-create-as "$guest" "$SNAPSHOT" --atomic >/dev/null 2>&1 || {
      echo "$guest: could not create the $SNAPSHOT snapshot"
      return 1
    }
    log "created $SNAPSHOT on $guest"
  done
}

clean_up() {
  rm -rf "$MEDIA_DIR" "$RUN_DIR" "$STATE_DIR" "$WORK_DIR"
  apt-get clean >/dev/null 2>&1 || rm -rf "$APT_CACHE"/*.deb
  fstrim -av >/dev/null 2>&1 || log "fstrim failed; the image is only larger"
}

finalize() {
  local nonce=$1 failure
  log "finalizing for nonce $nonce"
  if [ ! -s "$HOST_JSON" ]; then
    failure="$HOST_JSON is missing; the host was never built"
  elif ! failure=$(shut_down_guests); then
    :
  elif ! failure=$(snapshot_guests); then
    :
  else
    failure=
  fi
  # Recorded before the answer: once the Cloud Function reads it, the key may already be gone.
  mkdir -p "$(dirname "$ANSWERED")"
  echo "$nonce" > "$ANSWERED"
  if [ -n "$failure" ]; then
    log "finalize failed: $failure"
    put_attribute finalize-result "error:$nonce:$failure"
    return 1
  fi
  clean_up
  log "finalized"
  put_attribute finalize-result "ok:$nonce"
}

# One long poll of the metadata attributes; sets NONCE (empty when none) and ETAG.
# Called directly, never in $(...): a subshell would lose ETAG and turn the long poll into a busy loop.
ETAG=NONE
NONCE=
poll() {
  local headers body
  headers=$(mktemp) || return 1
  body=$(curl -sf -H 'Metadata-Flavor: Google' -D "$headers" \
    "$METADATA/instance/attributes/?recursive=true&wait_for_change=true&timeout_sec=$POLL_TIMEOUT_SECONDS&last_etag=$ETAG")
  local status=$?
  ETAG=$(tr -d '\r' < "$headers" | sed -n 's/^[Ee][Tt][Aa][Gg]: *//p' | tail -n 1)
  rm -f "$headers"
  [ -n "$ETAG" ] || ETAG=NONE
  [ "$status" -eq 0 ] || return 1
  NONCE=$(printf '%s' "$body" | jq -r --arg k "$NONCE_KEY" '.[$k] // empty')
}

main() {
  local polls=0
  mkdir -p "$(dirname "$LOG_FILE")"
  while :; do
    polls=$((polls + 1))
    if ! poll; then
      [ "$MAX_POLLS" -gt 0 ] && [ "$polls" -ge "$MAX_POLLS" ] && exit 1
      sleep 5
      continue
    fi
    if [ -n "$NONCE" ] && [ "$NONCE" != "$(cat "$ANSWERED" 2>/dev/null)" ]; then
      finalize "$NONCE"
    fi
    [ "$MAX_POLLS" -gt 0 ] && [ "$polls" -ge "$MAX_POLLS" ] && exit 0
  done
}

main "$@"
