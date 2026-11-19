"""Pi start path without the hardware: detection of what is plugged in and
the values it writes to .env (never over a value somebody set)."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _mod():
    spec = importlib.util.spec_from_file_location("hardware_erkennen", ROOT / "scripts" / "hardware_erkennen.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GPIODETECT = """gpiochip0 [pinctrl-rp1] (54 lines)
gpiochip10 [gpio-brcmstb@107d508500] (32 lines)
"""
CARDS_FINAL = """ 0 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0
 2 [handset        ]: USB-Audio - USB Audio Device
                      GeneralPlus USB Audio Device at usb-xhci-hcd.0-1, full speed
 3 [speaker        ]: USB-Audio - USB Audio Device
 4 [C920           ]: USB-Audio - HD Pro Webcam C920
"""
CARDS_INTERIM = """ 0 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0
 2 [Headset        ]: USB-Audio - Jabra Headset
 3 [C920           ]: USB-Audio - HD Pro Webcam C920
"""


def _drm(tmp_path, **connectors):
    for name, state in connectors.items():
        d = tmp_path / "drm" / f"card1-{name.replace('_', '-')}"
        d.mkdir(parents=True)
        (d / "status").write_text(state + "\n")
    return tmp_path / "drm"


def test_final_build_is_recognised(tmp_path):
    m = _mod()
    values, report = m.detect(CARDS_FINAL, GPIODETECT, _drm(tmp_path, DSI_1="connected", HDMI_A_1="disconnected"))
    assert values == {"GPIO_CHIP": "0", "HANDSET_ALSA_DEVICE": "plughw:CARD=handset,DEV=0",
                      "SPEAKER_ALSA_DEVICE": "plughw:CARD=speaker,DEV=0", "AUDIO_DEVICE_NAME": "C920"}
    assert ("OK", "Bildschirm: DSI-1") in report
    assert not [r for r in report if r[0] == "FEHLT"]


def test_interim_build_uses_one_card_for_both(tmp_path):
    m = _mod()
    values, report = m.detect(CARDS_INTERIM, "", _drm(tmp_path))
    assert values["HANDSET_ALSA_DEVICE"] == values["SPEAKER_ALSA_DEVICE"] == "plughw:CARD=Headset,DEV=0"
    assert "GPIO_CHIP" not in values
    levels = [r[0] for r in report]
    assert levels.count("WARNUNG") >= 3       # gpio, one card, no screen


def test_no_sound_card_is_missing(tmp_path):
    m = _mod()
    _, report = m.detect(" 0 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0\n", GPIODETECT, _drm(tmp_path))
    assert any(level == "FEHLT" for level, _ in report)


def test_writes_missing_updates_own_and_keeps_hand_set(tmp_path):
    m = _mod()
    env = tmp_path / ".env"
    env.write_text("GPIO_CHIP=4\n# HANDSET_ALSA_DEVICE=plughw:CARD=handset,DEV=0\nAUDIO_DEVICE_NAME=C920\n")
    interim = {"GPIO_CHIP": "0", "HANDSET_ALSA_DEVICE": "plughw:CARD=Headset,DEV=0",
               "SPEAKER_ALSA_DEVICE": "plughw:CARD=Headset,DEV=0", "AUDIO_DEVICE_NAME": "C920"}
    notes = m._set_missing(env, interim)
    text = env.read_text()
    assert "GPIO_CHIP=4\n" in text and any("bleibt" in n for n in notes)   # set by hand
    assert "\nHANDSET_ALSA_DEVICE=plughw:CARD=Headset,DEV=0" in text
    assert text.count("AUDIO_DEVICE_NAME") == 1
    # later: two named adapters -> the values it wrote itself are updated
    final = dict(interim, HANDSET_ALSA_DEVICE="plughw:CARD=handset,DEV=0",
                 SPEAKER_ALSA_DEVICE="plughw:CARD=speaker,DEV=0")
    m._set_missing(env, final)
    text = env.read_text()
    assert "HANDSET_ALSA_DEVICE=plughw:CARD=handset,DEV=0" in text
    assert "SPEAKER_ALSA_DEVICE=plughw:CARD=speaker,DEV=0" in text and "Headset" not in text
    assert m._set_missing(env, final) == [n for n in m._set_missing(env, final)]   # stable
    before = env.read_text()
    m._set_missing(env, final)
    assert env.read_text() == before


def test_values_are_read_by_the_shell(tmp_path):
    import os
    import subprocess
    m = _mod()
    env = tmp_path / ".env"
    env.write_text("")
    m._set_missing(env, {"HANDSET_ALSA_DEVICE": "plughw:CARD=handset,DEV=0"})
    out = subprocess.run(["bash", "-c", f"set -a; . '{env}'; echo $HANDSET_ALSA_DEVICE"],
                         capture_output=True, text=True, env={"PATH": os.environ["PATH"]})
    assert out.stdout.strip() == "plughw:CARD=handset,DEV=0"


def test_units_follow_user_and_folder_like_the_install_script(tmp_path):
    import subprocess
    for unit in ("seniorvoice", "seniorvoice-api", "seniorvoice-screen"):
        src = (ROOT / "deploy" / f"{unit}.service").read_text()
        out = subprocess.run(["sed", "-e", "s#/home/pi/seniorvoice#/home/team/sv#g",
                              "-e", "s#^User=pi$#User=team#"], input=src,
                             capture_output=True, text=True).stdout
        assert "/home/pi" not in out and "User=team" in out, unit
    screen = (ROOT / "deploy" / "seniorvoice-screen.service").read_text()
    assert "cage" in screen and "bildschirm-kiosk.sh" in screen and "multi-user.target" in screen


def test_install_script_dry_run_lists_all_steps():
    import subprocess
    out = subprocess.run(["bash", str(ROOT / "scripts" / "pi-einrichten.sh"), "--trocken"],
                         capture_output=True, text=True).stdout
    for step in ("1/6", "2/6", "3/6", "4/6", "5/6", "6/6", "cage", "hardware_erkennen.py --schreiben",
                 "seniorvoice-screen.service"):
        assert step in out, step
