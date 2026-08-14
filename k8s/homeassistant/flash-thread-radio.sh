#!/usr/bin/env bash
set -euo pipefail

radio_id="309eb9d5308aef118ae6c2a3ef8776e9"
radio_path="/dev/serial/by-id/usb-ITead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_${radio_id}-if00-port0"
zigbee_path="/dev/serial/by-id/usb-ITead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_7cfb165fcd8aef11922220ccef8776e9-if00-port0"
firmware_name="CC1352P2_CC2652P_launchpad_ot_rcp_2025_3_1"
firmware_url="https://github.com/Koenkk/OpenThread-TexasInstruments-firmware/releases/download/2025.3.1/${firmware_name}.zip"
firmware_sha256="5858a338f4d82e11a269410a9917561e91a5130fe3d6207dfc7066b0ed9e7e1d"

if [[ ! -c "$radio_path" ]]; then
  echo "The spare Thread radio is not available at $radio_path" >&2
  exit 1
fi

if [[ -e "$zigbee_path" ]] && [[ "$(readlink -f "$radio_path")" == "$(readlink -f "$zigbee_path")" ]]; then
  echo "Refusing to flash: the selected radio resolves to the live Zigbee coordinator." >&2
  exit 1
fi

echo "Spare Thread radio: $radio_path -> $(readlink -f "$radio_path")"
echo "This erases the spare radio's Zigbee firmware and replaces it with OpenThread RCP firmware."
read -r -p "Type 309eb9d5 to continue: " confirmation
if [[ "$confirmation" != "309eb9d5" ]]; then
  echo "Confirmation did not match; nothing was changed." >&2
  exit 1
fi

work_dir="$(mktemp -d --tmpdir thread-radio-flash.XXXXXX)"
cleanup() {
  rm -rf -- "$work_dir"
}
trap cleanup EXIT

archive="$work_dir/$firmware_name.zip"
curl -fL --output "$archive" "$firmware_url"
echo "$firmware_sha256  $archive" | sha256sum --check --status
unzip -q "$archive" -d "$work_dir"

flasher="$(nix build --no-link --print-out-paths nixpkgs#cc2538-bsl)/bin/cc2538-bsl"
sudo "$flasher" \
  -ewv \
  -p "$radio_path" \
  --bootloader-sonoff-usb \
  "$work_dir/$firmware_name.hex"

echo "OpenThread RCP firmware was written and verified on radio $radio_id."
