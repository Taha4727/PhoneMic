"""Settings migration/robustness and locale-independent ipconfig parsing."""
import json, os, tempfile, time
import _path  # noqa: F401
from phonemic.config import ConfigManager
from phonemic import system

EN = """Wireless LAN adapter Wi-Fi:

   Description . . . . . . . . . . . : Intel(R) Wi-Fi 6 AX201 160MHz
   IPv4 Address. . . . . . . . . . . : 192.168.178.23(Preferred)

Ethernet adapter Ethernet 3:

   Description . . . . . . . . . . . : Remote NDIS based Internet Sharing Device
   Autoconfiguration IPv4 Address. . : 169.254.3.4(Preferred)
   IPv4 Address. . . . . . . . . . . : 192.168.42.37(Preferred)
"""
DE = """Drahtlos-LAN-Adapter WLAN:

   Beschreibung. . . . . . . . . . . : Intel(R) Wi-Fi 6 AX201 160MHz
   IPv4-Adresse  . . . . . . . . . . : 192.168.178.23(Bevorzugt)

Ethernet-Adapter Ethernet 2:

   Beschreibung. . . . . . . . . . . : Samsung Mobile USB Remote NDIS Network Device
   IPv4-Adresse  . . . . . . . . . . : 192.168.29.100(Bevorzugt)
"""


def test_ipconfig_english_and_german():
    assert [(i.category, i.ip) for i in system.parse_ipconfig(EN)] == [("Wi-Fi", "192.168.178.23"), ("USB Tether", "192.168.42.37")]
    assert [(i.category, i.ip) for i in system.parse_ipconfig(DE)] == [("Wi-Fi", "192.168.178.23"), ("USB Tether", "192.168.29.100")]


def test_v08_config_migrates():
    d = tempfile.mkdtemp(); p = os.path.join(d, "c.json")
    json.dump({"version": "0.8.0", "visualizer_mode": "oscilloscope",
               "studio_fx": {"gain": 1.8, "gate_threshold_db": -80.0}, "voice_changer": {"mode": "Demon / Dark Lord"},
               "user_fx_presets": {"Mine": {"gain": 2.0}}}, open(p, "w"))
    c = ConfigManager(p)
    assert c.data["studio_fx"]["gain"] == 1.8 and c.data["studio_fx"]["gate_enabled"] is False
    assert c.data["voice_changer"]["mode"] == "Demon / Dark Lord" and "Mine" in c.data["user_fx_presets"]
    c.close()


def test_saves_are_debounced_and_corrupt_files_survive():
    d = tempfile.mkdtemp(); p = os.path.join(d, "c.json")
    c = ConfigManager(p); n = []; orig = c.save; c.save = lambda: (n.append(1), orig())[1]
    for i in range(100):
        c.data["studio_fx"]["gain"] = 1 + i / 100; c.save_soon(); time.sleep(0.001)
    time.sleep(1.0); assert len(n) <= 2; c.close()
    open(p, "w").write("{broken")
    c2 = ConfigManager(p); assert c2.load_error and c2.data["studio_fx"]["gain"] == 1.0; c2.close()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
