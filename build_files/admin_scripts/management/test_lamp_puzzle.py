#!/usr/bin/env python3
"""
Govee Device Control Script (updated API v1)
Prompts for API key, device ID, and SKU at runtime.
"""

import uuid
import time
import requests

BASE = "https://openapi.api.govee.com/router/api/v1"

def get_input(prompt_text, default=None):
    text = input(f"{prompt_text}{' [' + default + ']' if default else ''}: ").strip()
    return text or default

def _headers(api_key):
    return {"Govee-API-Key": api_key, "Content-Type": "application/json"}

def list_devices(api_key):
    """List all devices linked to your account."""
    url = f"{BASE}/user/devices"
    r = requests.get(url, headers=_headers(api_key), timeout=15)
    r.raise_for_status()
    devices = r.json().get("data", [])
    print("\n== Your Devices ==")
    for d in devices:
        print(f"- Name: {d.get('deviceName', 'Unknown')}")
        print(f"  SKU: {d.get('sku')}")
        print(f"  Device ID: {d.get('device')}")
        print(f"  Capabilities: {[c.get('instance') for c in d.get('capabilities', [])]}")
        print()
    if not devices:
        print("⚠️  No devices found. Make sure your Govee Home account has Wi-Fi devices linked.")
    return devices

def get_state(api_key, sku, device):
    """Fetch current device state."""
    url = f"{BASE}/device/state"
    body = {"requestId": str(uuid.uuid4()), "payload": {"sku": sku, "device": device}}
    r = requests.post(url, headers=_headers(api_key), json=body, timeout=15)
    r.raise_for_status()
    print("\n== Device State ==")
    print(r.json())
    return r.json()

def _control(api_key, sku, device, capability):
    """Send a control command."""
    url = f"{BASE}/device/control"
    body = {
        "requestId": str(uuid.uuid4()),
        "payload": {
            "sku": sku,
            "device": device,
            "capability": capability,
        },
    }
    for attempt in range(3):
        r = requests.post(url, headers=_headers(api_key), json=body, timeout=15)
        if r.status_code == 429:
            print("Rate limited; retrying...")
            time.sleep(1.5 + attempt)
            continue
        r.raise_for_status()
        print("Response:", r.json())
        return r.json()

def power(api_key, sku, device, on=True):
    cap = {
        "type": "devices.capabilities.on_off",
        "instance": "powerSwitch",
        "value": 1 if on else 0,
    }
    return _control(api_key, sku, device, cap)

def set_brightness(api_key, sku, device, level):
    level = max(1, min(100, int(level)))
    cap = {
        "type": "devices.capabilities.range",
        "instance": "brightness",
        "value": level,
    }
    return _control(api_key, sku, device, cap)

def set_color_rgb(api_key, sku, device, r, g, b):
    r, g, b = [max(0, min(255, int(v))) for v in (r, g, b)]
    rgb_int = ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)
    cap = {
        "type": "devices.capabilities.color_setting",
        "instance": "colorRgb",
        "value": rgb_int,
    }
    return _control(api_key, sku, device, cap)

def set_color_temperature(api_key, sku, device, kelvin):
    val = max(2000, min(9000, int(kelvin)))
    cap = {
        "type": "devices.capabilities.color_setting",
        "instance": "colorTemperatureK",
        "value": val,
    }
    return _control(api_key, sku, device, cap)

if __name__ == "__main__":
    print("=== Govee API Control ===")
    api_key = get_input("Enter your Govee API key")
    print("\nListing devices associated with this key...")
    list_devices(api_key)

    sku = get_input("\nEnter SKU (e.g., H6020)")
    device = get_input("Enter Device ID (as shown above)")

    print("\nCommands:")
    print("1) Turn ON")
    print("2) Turn OFF")
    print("3) Set Brightness")
    print("4) Set Color (RGB)")
    print("5) Set Color Temperature (K)")
    print("6) Get State")
    print("0) Exit")

    while True:
        choice = get_input("\nChoose an option (0-6)")
        if choice == "0":
            break
        elif choice == "1":
            power(api_key, sku, device, True)
        elif choice == "2":
            power(api_key, sku, device, False)
        elif choice == "3":
            val = get_input("Brightness (1-100)", "60")
            set_brightness(api_key, sku, device, val)
        elif choice == "4":
            r = get_input("R (0-255)", "255")
            g = get_input("G (0-255)", "128")
            b = get_input("B (0-255)", "0")
            set_color_rgb(api_key, sku, device, r, g, b)
        elif choice == "5":
            kelvin = get_input("Color Temp (2000-9000K)", "3000")
            set_color_temperature(api_key, sku, device, kelvin)
        elif choice == "6":
            get_state(api_key, sku, device)
        else:
            print("Invalid choice. Try again.")
