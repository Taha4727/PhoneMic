"""Packaging must agree with the app: every module is in the build spec, the installer creates the exact firewall rules the
app looks for, versions match, and every file the installer ships exists."""
import os
import re
import _path  # noqa: F401
from phonemic import system
from phonemic.const import VERSION, DEFAULT_PORT

ROOT = _path.ROOT


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_every_module_is_listed_in_the_build_spec():
    spec = read("PhoneMicReceiver.spec")
    for fn in sorted(os.listdir(os.path.join(ROOT, "phonemic"))):
        if fn.endswith(".py") and fn != "__init__.py":
            assert f'"phonemic.{fn[:-3]}"' in spec, f"{fn} is missing from hiddenimports (the exe would crash at import time)"
    assert '"phonemic"' in spec and "pystray" in spec and '"PIL"' not in re.search(r"excludes = \[(.*?)\]", spec, re.S).group(1), "tray packages must be bundled, not excluded"


def test_installer_matches_the_app():
    iss = read("installer", "PhoneMicReceiver.iss")
    assert re.search(r'#define AppVersion "([^"]+)"', iss).group(1) == VERSION
    port = int(re.search(r'#define AppPort "(\d+)"', iss).group(1)); assert port == DEFAULT_PORT
    flat = iss.replace("{#AppPort}", str(port)).replace('""', '"')
    for name in system.firewall_rule_names(port) + ["PhoneMic Receiver App"]:
        assert flat.count(f'name="{name}"') >= 3, f"installer must add AND remove the rule '{name}'"
    for section in ("[Setup]", "[Files]", "[Icons]", "[Run]", "[UninstallRun]", "[Code]"):
        assert section in iss
    assert "AppId={{" in iss, "the GUID's opening brace must be doubled"
    assert "PrivilegesRequired=admin" in iss and "OutputBaseFilename=PhoneMicReceiver-Setup-{#AppVersion}" in iss
    for rel in re.findall(r'Source: "\.\.\\([^*"]+?)"', iss):
        if not rel.startswith("dist"):
            assert os.path.exists(os.path.join(ROOT, rel.replace("\\", os.sep))), rel
    assert os.path.exists(os.path.join(ROOT, "assets", "phonemic.ico"))
    for rid in re.findall(r'RunOnceId: "(\w+)"', iss):
        assert iss.count(f'"{rid}"') == 1, "RunOnceId values must be unique"


def test_build_scripts_chain_together():
    inst = read("installer", "build_installer.bat"); build = read("build_exe.bat")
    assert 'build_exe.bat" onedir nopause' in inst and "PM_NOPAUSE" in build
    assert "pystray" in build and "pystray" in read("requirements.txt") and "pillow" in read("requirements.txt").lower()
    assert "Inno Setup 6" in inst and "ISCC.exe" in inst
    for f in ("build_exe.bat", "start_receiver.bat", "start_receiver.ps1", "PhoneMicReceiver.spec"):
        txt = read(f)
        assert VERSION in txt, f"{f} does not show the current version"
        assert not re.search(r"v0\.(9|10)\.\d", txt), f"{f} still mentions an old version"


def test_batch_files_never_expand_paths_inside_parenthesised_blocks():
    """cmd breaks on 'C:\\Program Files (x86)\\...' inside ( ... ) blocks; the scripts use goto labels instead."""
    for f in ("build_exe.bat", "start_receiver.bat", "fix_firewall.bat", os.path.join("installer", "build_installer.bat")):
        depth, bad = 0, []
        for n, line in enumerate(read(f).splitlines(), 1):
            if line.lstrip().lower().startswith(("echo", "rem", "::")):
                continue
            opened = line.count("(") - line.count(")")
            if (depth > 0 or opened > 0) and re.search(r"%~?(dp0|f0|ProgramFiles|LOCALAPPDATA)", line):
                bad.append(n)
            depth = max(0, depth + opened)
        assert not bad, f"{f}: path expanded inside a block on lines {bad}"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
