#!/usr/bin/env bash
# preflight.sh - grade this Mac for the CS2-on-Apple-Silicon plan.
# Usage: bash scripts/preflight.sh [--json]
set -uo pipefail

STEAM="$HOME/Library/Application Support/Steam"
JSON=0; [ "${1:-}" = "--json" ] && JSON=1
FAIL=0; WARN=0
say(){ [ $JSON -eq 0 ] && printf '%s\n' "$*"; }
chk(){ # chk <PASS|WARN|FAIL> <label> <detail>
  case "$1" in FAIL) FAIL=$((FAIL+1));; WARN) WARN=$((WARN+1));; esac
  [ $JSON -eq 0 ] && printf '  [%-4s] %-34s %s\n' "$1" "$2" "$3"
  return 0; }

OSV=$(sw_vers -productVersion); OSB=$(sw_vers -buildVersion)
CHIP=$(sysctl -n machdep.cpu.brand_string)
MEMB=$(sysctl -n hw.memsize); MEMGB=$((MEMB/1024/1024/1024))
PCORE=$(sysctl -n hw.perflevel0.logicalcpu 2>/dev/null || echo "?")
ECORE=$(sysctl -n hw.perflevel1.logicalcpu 2>/dev/null || echo "?")
GPU=$(system_profiler SPDisplaysDataType 2>/dev/null | awk -F': ' '/Total Number of Cores/{print $2; exit}')
METAL=$(system_profiler SPDisplaysDataType 2>/dev/null | awk -F': ' '/Metal Support/{print $2; exit}')
RES=$(system_profiler SPDisplaysDataType 2>/dev/null | awk -F': ' '/Resolution/{print $2; exit}')
FREEK=$(df -k /System/Volumes/Data | awk 'NR==2{print $4}'); FREEGB=$((FREEK/1024/1024))
ARCHM=$(uname -m)
pgrep -q oahd && ROSETTA=yes || ROSETTA=no
OSMAJ=${OSV%%.*}

say ""; say "=== CS2 on Apple Silicon - preflight ==="
say "  $CHIP | ${PCORE}P+${ECORE}E | GPU ${GPU:-?} cores | ${MEMGB} GB | macOS $OSV ($OSB) | $ARCHM"
say "  Display: ${RES:-?} | ${METAL:-?} | Free: ${FREEGB} GiB"; say ""
say "-- hardware --"
case "$ARCHM" in arm64) chk PASS "Apple Silicon" "$CHIP";; *) chk FAIL "Apple Silicon" "$ARCHM - this plan targets arm64";; esac
[ "$MEMGB" -ge 16 ] && chk PASS "RAM" "${MEMGB} GB" || chk WARN "RAM" "${MEMGB} GB - 8 GB is playable but tight"
case "$CHIP" in *Air*) chk WARN "Chassis" "fanless - expect 30-40 FPS sustained";; esac
[ "$ROSETTA" = yes ] && chk PASS "Rosetta 2" "active" || chk FAIL "Rosetta 2" "not installed - softwareupdate --install-rosetta"
say ""; say "-- macOS --"
if [ "$OSMAJ" -ge 27 ] 2>/dev/null; then chk FAIL "Rosetta horizon" "macOS $OSMAJ >= 27 - general-purpose Rosetta is retired (risk R-1)"
else chk PASS "Rosetta horizon" "macOS $OSMAJ - supported through macOS 27"; fi
say ""; say "-- disk (reuse route needs ~85 GiB free; clean route ~150 GiB) --"
if   [ "$FREEGB" -ge 85 ]; then chk PASS "Free space" "${FREEGB} GiB - enough for the T-008 reuse route"
elif [ "$FREEGB" -ge 75 ]; then chk WARN "Free space" "${FREEGB} GiB - tight; uninstall the macOS CS2 copy if T-008 reuse fails"
else chk FAIL "Free space" "${FREEGB} GiB - insufficient"; fi
if [ -d "$STEAM/steamapps/downloading/730" ]; then
  D=$(du -sg "$STEAM/steamapps/downloading/730" 2>/dev/null | awk '{print $1}')
  chk FAIL "Dead CS2 download (T-001)" "${D:-?} GiB in steamapps/downloading/730 - macOS Steam omits the win64 exe depot; DELETE IT"
else chk PASS "Dead CS2 download (T-001)" "absent"; fi
[ -f "$STEAM/steamapps/appmanifest_730.acf" ] && chk WARN "macOS appmanifest_730" "present - macOS Steam install has no cs2.exe (depot 2347771 absent); see T-001/T-008" \
                                              || chk PASS "macOS appmanifest_730" "absent"
say ""; say "-- free stack: Wine + DXMT + MSync (T-004/T-006) --"
HOST=none
if command -v wine >/dev/null 2>&1; then
  WV=$(wine --version 2>/dev/null); HOST="$WV"
  case "$WV" in wine-1[1-9]*|wine-[2-9][0-9]*) chk PASS "Wine" "$WV";; *) chk WARN "Wine" "$WV - plan targets Wine 11.x";; esac
else
  chk WARN "Wine" "not installed - T-004: brew install --cask gcenx/wine/wine-crossover"
fi
if [ -n "${WINEPREFIX:-}" ] && [ -d "${WINEPREFIX:-/nonexistent}" ]; then
  if ls "$WINEPREFIX"/drive_c/windows/system32/d3d11.dll >/dev/null 2>&1; then chk PASS "Bottle" "$WINEPREFIX"
  else chk WARN "Bottle" "$WINEPREFIX exists but no d3d11 override yet (T-006)"; fi
else
  chk WARN "Bottle" "WINEPREFIX unset - T-006"
fi
[ -d /Applications/Whisky.app ] && chk WARN "Whisky" "archived 2025-05-11 - not part of this plan"
say ""; say "-- environment hygiene --"
if system_profiler SPAirPortDataType 2>/dev/null | grep -qi 'awdl'; then chk WARN "AWDL" "AirDrop/Handoff can add Wi-Fi jitter (R-12)"; fi
pmset -g 2>/dev/null | grep -q 'lowpowermode.*1' && chk WARN "Low Power Mode" "ON - disable before benchmarking" || chk PASS "Low Power Mode" "off"

if [ $JSON -eq 1 ]; then
  printf '{"macos":"%s","build":"%s","chip":"%s","p_cores":"%s","e_cores":"%s","gpu_cores":"%s","metal":"%s","ram_gb":%s,"resolution":"%s","arch":"%s","rosetta":"%s","free_gib":%s,"runtime_host":"%s","fail":%s,"warn":%s}\n' \
    "$OSV" "$OSB" "$CHIP" "$PCORE" "$ECORE" "${GPU:-?}" "${METAL:-?}" "$MEMGB" "${RES:-?}" "$ARCHM" "$ROSETTA" "$FREEGB" "$HOST" "$FAIL" "$WARN"
else
  say ""; say "=== $FAIL FAIL / $WARN WARN ==="
  say "Deeper grade (bottle, game files, integrity, profile): ./bin/cs2kit doctor"
  [ $FAIL -gt 0 ] && say "Resolve FAILs before Phase 1. Start at docs/03-development-plan.md T-001."
  say ""
fi
exit $(( FAIL > 0 ? 1 : 0 ))
