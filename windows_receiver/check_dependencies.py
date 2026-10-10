#!/usr/bin/env python3
"""
PhoneMic Dependency & Audio Diagnostic Utility
Checks Python environment, required packages (numpy, sounddevice),
VB-Audio Virtual Cable installation, and network interfaces.
Prompts for automatic installation or provides direct download links.
"""

import sys
import os
import subprocess
import socket
import webbrowser
import platform

# Terminal Colors
if os.name == 'nt':
    os.system('color')  # Enable ANSI in cmd.exe

GREEN = '\033[92m'
CYAN = '\033[96m'
YELLOW = '\033[93m'
RED = '\033[91m'
BOLD = '\033[1m'
RESET = '\033[0m'

VB_CABLE_PAGE = "https://vb-audio.com/Cable/"
VB_CABLE_DIRECT_ZIP = "https://download.vb-audio.com/Download_VIP/VBCABLE_Driver_Pack43.zip"
PYTHON_DOWNLOAD_PAGE = "https://www.python.org/downloads/"
NUMPY_PAGE = "https://pypi.org/project/numpy/"
SOUNDDEVICE_PAGE = "https://pypi.org/project/sounddevice/"

def print_header():
    print(f"{CYAN}{'=' * 72}{RESET}")
    print(f"{BOLD}{CYAN}         PhoneMic Windows Receiver - Dependency & Audio Checker{RESET}")
    print(f"{CYAN}{'=' * 72}{RESET}\n")

def prompt_yes_no(prompt_text, default=True):
    suffix = " [Y/n]: " if default else " [y/N]: "
    try:
        choice = input(f"{YELLOW}{prompt_text}{RESET}{suffix}").strip().lower()
        if not choice:
            return default
        return choice in ('y', 'yes', 'true', '1')
    except (KeyboardInterrupt, EOFError):
        print()
        return False

def check_python():
    print(f"[*] Checking Python environment...")
    v = sys.version_info
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    if v.major >= 3 and v.minor >= 8:
        print(f"    {GREEN}[✓] Python {ver_str} installed ({platform.architecture()[0]}){RESET}")
        return True
    else:
        print(f"    {RED}[✗] Python {ver_str} detected. PhoneMic requires Python 3.8+!{RESET}")
        print(f"        Download latest Python: {PYTHON_DOWNLOAD_PAGE}")
        if prompt_yes_no("Open Python download page in browser?"):
            webbrowser.open(PYTHON_DOWNLOAD_PAGE)
        return False

def check_pip():
    print(f"[*] Checking pip package manager...")
    try:
        out = subprocess.check_output(
            [sys.executable, "-m", "pip", "--version"],
            stderr=subprocess.STDOUT,
            text=True
        )
        pip_ver = out.strip().split()[1] if len(out.strip().split()) > 1 else "OK"
        print(f"    {GREEN}[✓] pip package manager available (v{pip_ver}){RESET}")
        return True
    except Exception:
        print(f"    {RED}[✗] pip is not available with current Python!{RESET}")
        print(f"        Run: python -m ensurepip --default-pip")
        return False

def check_and_install_package(package_name, import_name=None, pypi_url=""):
    if import_name is None:
        import_name = package_name

    print(f"[*] Checking '{package_name}'...")
    try:
        mod = __import__(import_name)
        ver = getattr(mod, '__version__', 'installed')
        print(f"    {GREEN}[✓] {package_name} is installed (v{ver}){RESET}")
        return True
    except ImportError:
        print(f"    {YELLOW}[!] {package_name} is NOT installed.{RESET}")
        print(f"        Package info: {pypi_url}")

        if prompt_yes_no(f"    Would you like to automatically install '{package_name}' now via pip?"):
            print(f"    Installing {package_name}...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", package_name
                ])
                print(f"    {GREEN}[✓] Successfully installed {package_name}!{RESET}")
                return True
            except Exception as e:
                print(f"    {RED}[✗] Failed to install {package_name} automatically: {e}{RESET}")
                print(f"        Manual command: pip install {package_name}")
                return False
        else:
            print(f"    Manual install command: pip install {package_name}")
            return False

def check_vb_cable():
    print(f"[*] Checking Windows Audio Devices & VB-Audio Virtual Cable...")
    try:
        import sounddevice as sd
    except ImportError:
        print(f"    {YELLOW}[-] Cannot query audio devices because 'sounddevice' is not yet installed.{RESET}")
        return False

    try:
        devices = sd.query_devices()
        cable_found = False
        cable_name = ""

        for dev in devices:
            name = dev.get('name', '')
            # Look for VB-CABLE Input or VB-Audio
            if "cable input" in name.lower() or "vb-audio virtual cable" in name.lower():
                cable_found = True
                cable_name = name
                break

        if cable_found:
            print(f"    {GREEN}[✓] VB-Audio Virtual Cable detected:{RESET} '{cable_name}'")
            print(f"        Your PC can route PhoneMic straight into Discord, OBS, Zoom & games!")
            return True
        else:
            print(f"    {YELLOW}[!] VB-Audio Virtual Cable was NOT found in your output devices.{RESET}")
            print(f"        Without VB-CABLE, PhoneMic can still play audio to your regular speakers/headphones,")
            print(f"        but VB-CABLE is needed to use your phone as a virtual microphone in Discord/games.")
            print(f"        - Official Website: {VB_CABLE_PAGE}")
            print(f"        - Direct Zip Download: {VB_CABLE_DIRECT_ZIP}")

            if prompt_yes_no("    Would you like to open the free VB-CABLE download page in your browser?"):
                webbrowser.open(VB_CABLE_PAGE)
            return False
    except Exception as e:
        print(f"    {YELLOW}[!] Unable to query audio devices: {e}{RESET}")
        return False

def check_network_ips():
    print(f"[*] Detecting Local IP Addresses for Android connection...")
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    # Fallback via dummy UDP socket connection
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        fallback_ip = s.getsockname()[0]
        s.close()
        if fallback_ip not in ips and not fallback_ip.startswith("127."):
            ips.append(fallback_ip)
    except Exception:
        pass

    if ips:
        print(f"    {GREEN}[✓] Found PC local IP address(es) for PhoneMic Android app:{RESET}")
        for ip in ips:
            print(f"        -> {BOLD}{CYAN}{ip}{RESET} (Port 5001)")
    else:
        print(f"    {YELLOW}[!] Could not detect local IP. Check network connection.{RESET}")

def main():
    print_header()

    # 1. Python Check
    py_ok = check_python()
    print()

    # 2. Pip Check
    pip_ok = check_pip() if py_ok else False
    print()

    # 3. Required packages
    numpy_ok = check_and_install_package("numpy", "numpy", NUMPY_PAGE) if pip_ok else False
    print()
    sd_ok = check_and_install_package("sounddevice", "sounddevice", SOUNDDEVICE_PAGE) if pip_ok else False
    print()

    # 4. Audio Devices / VB-CABLE
    vb_ok = check_vb_cable()
    print()

    # 5. Network IPs
    check_network_ips()
    print()

    # Summary
    print(f"{CYAN}{'=' * 72}{RESET}")
    print(f"{BOLD}Summary:{RESET}")
    print(f"  - Python Environment:        {'[✓] OK' if py_ok else '[✗] Missing'}")
    print(f"  - pip Package Manager:       {'[✓] OK' if pip_ok else '[✗] Missing'}")
    print(f"  - NumPy (Audio DSP):         {'[✓] OK' if numpy_ok else '[✗] Missing'}")
    print(f"  - SoundDevice (WASAPI Play): {'[✓] OK' if sd_ok else '[✗] Missing'}")
    print(f"  - VB-Audio Virtual Cable:    {'[✓] OK (Recommended)' if vb_ok else '[!] Optional (Recommended for Discord/OBS)'}")
    print(f"{CYAN}{'=' * 72}{RESET}\n")

    all_core_ready = py_ok and pip_ok and numpy_ok and sd_ok

    if all_core_ready:
        print(f"{GREEN}{BOLD}PhoneMic Receiver is 100% READY TO RUN!{RESET}\n")
        receiver_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phonemic_receiver.py")
        if os.path.exists(receiver_script):
            if prompt_yes_no("Would you like to start the PhoneMic Receiver now?"):
                print(f"[*] Launching PhoneMic Receiver...\n")
                subprocess.call([sys.executable, receiver_script])
        else:
            print(f"phonemic_receiver.py not found in same directory.")
    else:
        print(f"{YELLOW}Some core dependencies are missing. Please install them and re-run this check.{RESET}\n")

    input(f"{CYAN}Press Enter to exit...{RESET}")

if __name__ == "__main__":
    main()
