"""Cross-platform Linux / Arch Linux unit tests (pure stdlib: runs cleanly without tkinter, numpy, or pactl)."""
import os
import tempfile
import _path  # noqa: F401
from phonemic import system, virtual_mic, cues


IP_ADDR_SAMPLE = """1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever preferred_lft forever
2: enp4s0    inet 192.168.1.44/24 brd 192.168.1.255 scope global dynamic noprefixroute enp4s0\\       valid_lft 86000sec preferred_lft 86000sec
3: wlp3s0    inet 192.168.178.23/24 brd 192.168.178.255 scope global dynamic noprefixroute wlp3s0\\       valid_lft 86000sec preferred_lft 86000sec
4: usb0    inet 192.168.42.129/24 brd 192.168.42.255 scope global dynamic usb0\\       valid_lft 3600sec preferred_lft 3600sec
5: enp0s20f0u1    inet 10.42.0.15/24 brd 10.42.0.255 scope global dynamic enp0s20f0u1\\       valid_lft 3600sec preferred_lft 3600sec
6: docker0    inet 172.17.0.1/16 brd 172.17.255.255 scope global docker0\\       valid_lft forever preferred_lft forever
7: tailscale0    inet 100.64.1.9/32 scope global tailscale0\\       valid_lft forever preferred_lft forever
8: virbr0    inet 192.168.122.1/24 brd 192.168.122.255 scope global virbr0\\       valid_lft forever preferred_lft forever
9: wlan1    inet 169.254.9.10/16 brd 169.254.255.255 scope link wlan1\\       valid_lft forever preferred_lft forever
"""


PACTL_INFO_PIPEWIRE = """Server String: /run/user/1000/pulse/native
Library Protocol Version: 35
Server Protocol Version: 35
Is Local: yes
Client Index: 124
Tile Size: 65472
User Name: archuser
Host Name: workstation
Server Name: PulseAudio (on PipeWire 1.2.7)
Server Version: 15.0.0
Default Sample Specification: float32le 2ch 48000Hz
Default Channel Map: front-left,front-right
Default Sink: alsa_output.pci-0000_00_1f.3.analog-stereo
Default Source: alsa_input.pci-0000_00_1f.3.analog-stereo
"""


PACTL_SINKS_SAMPLE = """Sink #42
\tState: SUSPENDED
\tName: alsa_output.pci-0000_00_1f.3.analog-stereo
\tDescription: Built-in Audio Analog Stereo
\tDriver: PipeWire
\tSample Specification: s32le 2ch 48000Hz

Sink #87
\tState: IDLE
\tName: PhoneMic_Sink
\tDescription: PhoneMic_Sink
\tDriver: module-null-sink.c
\tSample Specification: s16le 2ch 48000Hz
"""


PACTL_SOURCES_SHORT = """42\talsa_output.pci-0000_00_1f.3.analog-stereo.monitor\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED
43\talsa_input.pci-0000_00_1f.3.analog-stereo\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED
87\tPhoneMic_Sink.monitor\tPipeWire\ts16le 2ch 48000Hz\tIDLE
88\tPhoneMic_Virtual_Mic\tmodule-remap-source.c\ts16le 2ch 48000Hz\tIDLE
"""


PACTL_MODULES_SHORT = """24\tmodule-null-sink\tsink_name=PhoneMic_Sink sink_properties=device.description=PhoneMic_Sink
25\tmodule-remap-source\tmaster=PhoneMic_Sink.monitor source_name=PhoneMic_Virtual_Mic source_properties=device.description=PhoneMic_Virtual_Mic
"""


def test_parse_ip_addr_and_linux_interface_classification():
    parsed = [(i.category, i.ip, i.name) for i in system.parse_ip_addr(IP_ADDR_SAMPLE)]
    assert parsed == [
        ("Ethernet", "192.168.1.44", "enp4s0"),
        ("Wi-Fi", "192.168.178.23", "wlp3s0"),
        ("USB Tether", "192.168.42.129", "usb0"),
        ("USB Tether", "10.42.0.15", "enp0s20f0u1"),
        ("Virtual", "172.17.0.1", "docker0"),
        ("Virtual", "100.64.1.9", "tailscale0"),
        ("Virtual", "192.168.122.1", "virbr0"),
    ]
    assert system.classify_interface("wlan0", "", "192.168.1.10") == "Wi-Fi"
    assert system.classify_interface("wlx00c0ca991122", "", "192.168.1.11") == "Wi-Fi"
    assert system.classify_interface("enx020c29aabbcc", "", "192.168.200.2") == "USB Tether"
    assert system.classify_interface("br-12ab34cd", "", "172.20.0.1") == "Virtual"
    assert system.classify_interface("waydroid0", "", "192.168.240.1") == "Virtual"


def test_virtual_mic_parsers():
    backend, default_sink = virtual_mic.parse_pactl_info(PACTL_INFO_PIPEWIRE)
    assert backend == "PipeWire"
    assert default_sink == "alsa_output.pci-0000_00_1f.3.analog-stereo"

    sinks = virtual_mic.parse_pactl_sinks(PACTL_SINKS_SAMPLE, default_sink=default_sink)
    assert len(sinks) == 2
    assert sinks[0].name == "alsa_output.pci-0000_00_1f.3.analog-stereo" and sinks[0].is_default and not sinks[0].is_virtual
    assert sinks[1].name == virtual_mic.SINK_NAME and not sinks[1].is_default and sinks[1].is_virtual

    sources = virtual_mic.parse_pactl_sources_short(PACTL_SOURCES_SHORT)
    assert f"{virtual_mic.SINK_NAME}.monitor" in sources
    assert virtual_mic.SOURCE_NAME in sources

    mods = virtual_mic.parse_pactl_modules_short(PACTL_MODULES_SHORT)
    assert mods[0][:2] == ("24", "module-null-sink")
    assert mods[1][:2] == ("25", "module-remap-source")


def test_xdg_config_override_and_autostart():
    old_cache = system._data_dir_cache
    old_env = os.environ.get("PHONEMIC_CONFIG_DIR")
    old_xdg = os.environ.get("XDG_CONFIG_HOME")
    tmp_cfg = tempfile.mkdtemp(prefix="pm_cfg_")
    tmp_xdg = tempfile.mkdtemp(prefix="pm_xdg_")
    try:
        system._data_dir_cache = None
        os.environ["PHONEMIC_CONFIG_DIR"] = tmp_cfg
        assert system.data_dir() == tmp_cfg
        assert system.config_path() == os.path.join(tmp_cfg, "phonemic_config.json")
        assert system.crash_log_path() == os.path.join(tmp_cfg, "phonemic_crash.log")

        if system.IS_LINUX:
            os.environ["XDG_CONFIG_HOME"] = tmp_xdg
            assert system.set_startup_enabled(True)
            assert system.get_startup_enabled() is True
            autostart_file = os.path.join(tmp_xdg, "autostart", "phonemic-receiver.desktop")
            assert os.path.isfile(autostart_file)
            assert "--minimized" in open(autostart_file, encoding="utf-8").read()
            assert system.set_startup_enabled(False)
            assert system.get_startup_enabled() is False
    finally:
        system._data_dir_cache = old_cache
        if old_env is None:
            os.environ.pop("PHONEMIC_CONFIG_DIR", None)
        else:
            os.environ["PHONEMIC_CONFIG_DIR"] = old_env
        if old_xdg is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = old_xdg


def test_cues_wav_generation_and_backend():
    for kind in ("mute", "unmute", "on", "off"):
        wav = cues.make_cue_wav(kind)
        assert wav.startswith(b"RIFF") and b"WAVE" in wav[:16] and len(wav) > 100
    assert isinstance(cues.backend_name(), str)


def test_virtual_device_flag_recognizes_linux_sink():
    dev = system.AudioDevice(
        index=0,
        name=virtual_mic.FRIENDLY_DEVICE_LABEL,
        api="PipeWire",
        channels=2,
        default_sr=48000.0,
        sink_name=virtual_mic.SINK_NAME,
    )
    assert dev.is_cable is True


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
