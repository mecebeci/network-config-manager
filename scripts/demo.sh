#!/usr/bin/env bash
# Interactive live demo of the Network Configuration Manager.
# Every step prints what it is about to do, waits for Enter, then runs the command.
#
# Usage:  ./scripts/demo.sh            (from anywhere; needs docker and containerlab)
# The lab is deployed first if it is not running (asks for sudo once).

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LAB_PREFIX="clab-srlinux-spine-leaf"
DEVICE_IPS=(172.21.20.11 172.21.20.12 172.21.20.13 172.21.20.14)

BOLD=$'\e[1m'; CYAN=$'\e[36m'; YELLOW=$'\e[33m'; DIM=$'\e[2m'; RESET=$'\e[0m'
STEP=0

for bin in docker containerlab; do
  command -v "$bin" >/dev/null || { echo "missing dependency: $bin" >&2; exit 1; }
done

# The CLI runs in the netconfig Docker image; use the repo's wrapper, not a stale installed copy
netconfig() { "$ROOT/netconfig" "$@"; }

# sr_cli_on <device> "<command>" — run an SR Linux CLI command directly on a lab node
sr_cli_on() {
  docker exec "$LAB_PREFIX-$1" sr_cli "$2" | grep . || echo "(empty — not configured)"
}

# step "<what this does>" "<command shown and executed>"
step() {
  STEP=$((STEP + 1))
  printf '\n%s━━ Step %d ━━ %s%s\n' "$BOLD$CYAN" "$STEP" "$1" "$RESET"
  printf '%s$ %s%s\n' "$YELLOW" "$2" "$RESET"
  read -r -p "${DIM}[Enter to run]${RESET} " _ || true
  eval "$2"
}

lab_running() {
  [ "$(docker ps -q --filter "name=^$LAB_PREFIX-" | wc -l)" -eq "${#DEVICE_IPS[@]}" ]
}

# --- Pre-flight (not part of the show): lab up, image current, spines at baseline ---
echo "${DIM}pre-flight: checking lab, image and device state...${RESET}"

if ! lab_running; then
  echo "${DIM}lab not running — deploying (SR Linux boot takes 2-3 minutes)${RESET}"
  sudo containerlab deploy -t lab/topology.yaml --reconfigure >/dev/null \
    || { echo "containerlab deploy failed" >&2; exit 1; }
fi

docker build -q -t netconfig . >/dev/null || { echo "docker build failed" >&2; exit 1; }

# Wait until every device answers SSH and its CLI is up
for ip in "${DEVICE_IPS[@]}"; do
  for _ in $(seq 1 90); do
    timeout 2 bash -c "</dev/tcp/$ip/22" 2>/dev/null && break
    sleep 2
  done
done
for dev in spine1 spine2; do
  for _ in $(seq 1 60); do
    docker exec "$LAB_PREFIX-$dev" sr_cli "info system name" >/dev/null 2>&1 && break
    sleep 2
  done
  # Start without NTP so the deploy and the rollback both show a visible change
  docker exec "$LAB_PREFIX-$dev" sr_cli -ec "delete / system ntp" >/dev/null 2>&1
done

clear
printf '%sNetwork Configuration Manager — live demo%s\n' "$BOLD" "$RESET"
printf '%s4 Nokia SR Linux nodes (2 spine, 2 leaf) in Containerlab, managed over SSH%s\n' "$DIM" "$RESET"

# --- 1. Lab and inventory ---
step "The lab: a spine-leaf topology running in Containerlab" \
     "containerlab inspect -t lab/topology.yaml"

step "Inventory: the single source of truth for every device" \
     "netconfig list --devices"

step "Validate the inventory before touching any device" \
     "netconfig validate --inventory"

# --- 2. Backup ---
step "Back up all 4 devices in parallel — timestamped files on the host" \
     "netconfig backup --all --parallel --yes"

step "Backup history for spine1" \
     "netconfig list --backups spine1"

# --- 3. Deploy ---
step "Available Jinja2 templates" \
     "netconfig list --templates"

step "The NTP template: variables are filled in per device" \
     "cat configs/templates/example_ntp.j2"

step "On the device: spine1 has no NTP configuration yet" \
     "sr_cli_on spine1 'info flat system ntp'"

step "Dry-run: render the template for spine1 and preview — nothing is sent" \
     "netconfig deploy -t example_ntp.j2 --device spine1 --vars '{\"ntp_server\": \"10.0.0.1\"}' --dry-run"

step "Deploy for real: automatic pre-deploy backup, then apply and commit" \
     "netconfig deploy -t example_ntp.j2 --device spine1 --vars '{\"ntp_server\": \"10.0.0.1\"}' --yes"

step "On the device: NTP is now configured" \
     "sr_cli_on spine1 'info flat system ntp'"

# --- 4. Rollback ---
step "Rollback dry-run: compares the running config with the latest backup and lists what would be deleted" \
     "netconfig rollback --device spine1 --latest --dry-run"

step "Roll back: safety backup, then delete + restore in a single commit" \
     "netconfig rollback --device spine1 --latest --yes"

step "On the device: NTP is gone — spine1 is back to its pre-deploy state" \
     "sr_cli_on spine1 'info flat system ntp'"

# --- 5. Multi-device ---
step "Deploy to every spine at once, in parallel" \
     "netconfig deploy -t example_ntp.j2 --role spine --vars '{\"ntp_server\": \"10.0.0.1\"}' --parallel --yes"

step "On both spines: NTP configured" \
     "for d in spine1 spine2; do echo \"== \$d\"; sr_cli_on \$d 'info flat system ntp'; done"

step "Roll back every spine in parallel" \
     "netconfig rollback --role spine --latest --parallel --yes"

step "On both spines: back to baseline" \
     "for d in spine1 spine2; do echo \"== \$d\"; sr_cli_on \$d 'info flat system ntp'; done"

step "Audit trail: every backup, pre-deploy backup and safety backup is kept" \
     "netconfig list --backups spine1"

printf '\n%sDemo complete.%s  Lab is still running — stop it with: sudo containerlab destroy -t lab/topology.yaml\n' "$BOLD" "$RESET"
