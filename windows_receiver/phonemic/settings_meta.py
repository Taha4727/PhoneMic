"""Single source of truth for every user-facing setting.

The UI builds its rows, help text, search index and reset buttons from this table, so an explanation can never describe
something the app no longer does. Tests check that every audio parameter is listed, that ranges contain the defaults and
that the writing follows the house style (sentence case, plain words).

Setting targets
    fx   an AudioProcessor parameter (key = parameter name)
    cfg  a settings-file value (key = "section.name")
    vc   a voice-changer value (key = "vc.name")
    sys  something Windows owns (key = "sys.name"), handled by custom code
"""
import math
from dataclasses import dataclass
from typing import Optional

from . import dsp
from .config import DEFAULTS


@dataclass(frozen=True)
class Setting:
    key: str
    target: str                      # fx | cfg | vc | sys
    page: str                        # sound | voice | devices | network | settings
    group: str                       # stage id on the Sound page, card id elsewhere
    label: str
    summary: str                     # one line, always visible
    details: str                     # what it does, when to change it, trade-offs (shown on demand)
    kind: str                        # slider | toggle | choice | custom
    lo: float = 0.0
    hi: float = 1.0
    step: float = 0.01
    fmt: str = "num"
    origin: Optional[float] = None
    conv: str = ""                   # "db_lin": shown in dB, stored as a linear factor
    log: bool = False                # logarithmic slider (frequencies, Q)
    choices: tuple = ()              # ((value, label), ...)
    advanced: bool = False
    needs: str = ""                  # toggle that must be on for this setting to matter
    keywords: str = ""
    short: str = ""                  # label used inside its own panel (defaults to label)
    restart: bool = False

    @property
    def title(self):
        return self.short or self.label


# ==============================================================================
# FORMATTING
# ==============================================================================
def format_value(fmt, v):
    if fmt == "db":
        return f"{v:+.1f} dB"
    if fmt == "db0":
        return f"{v:+.0f} dB"
    if fmt == "dbu":
        return f"{v:.0f} dB"
    if fmt == "dbfs":
        return f"{v:.1f} dBFS" if abs(v - round(v)) > 0.01 else f"{v:.0f} dBFS"
    if fmt == "hz":
        return f"{v / 1000:.1f} kHz" if v >= 1000 else f"{v:.0f} Hz"
    if fmt == "ms":
        return f"{v:.0f} ms"
    if fmt == "ms1":
        return f"{v:.1f} ms"
    if fmt == "s":
        return f"{v:.1f} s"
    if fmt == "pct":
        return f"{v * 100:.0f}%"
    if fmt == "ratio":
        return f"{v:.1f} : 1"
    if fmt == "q":
        return f"{v:.2f}" if v < 1 else f"{v:.1f}"
    if fmt == "st":
        return "no shift" if abs(v) < 0.25 else f"{v:+.1f} semitones"
    if fmt == "reduce":
        return "Automatic" if v < 0.5 else f"{v:.0f} dB"
    if fmt == "fps":
        return f"{v:.0f} frames/s"
    return f"{v:g}"


# ==============================================================================
# STAGES (Sound page) AND CARDS (other pages)
# ==============================================================================
@dataclass(frozen=True)
class Stage:
    id: str
    title: str
    blurb: str
    enable: str = ""                 # toggle parameter, or "" when the stage has no switch
    led: tuple = ()                  # parameters that light the chain indicator (defaults to `enable`)
    link: str = ""                   # jumps to another page instead of opening a panel


STAGES = (
    Stage("input", "Input", "The raw phone signal enters here. Set its level before any effect touches it."),
    Stage("filters", "Low-cut and high-cut", "Removes sound below and above the range a voice needs.",
          led=("lowcut_enabled", "highcut_enabled")),
    Stage("noise", "Noise suppression", "Learns steady background noise such as fans and hiss, and removes it.", "smart_noise_cancel"),
    Stage("gate", "Noise gate", "Silences the microphone between words so leftover noise is not heard.", "gate_enabled"),
    Stage("agc", "Auto gain", "Keeps your voice at a steady loudness as you move around.", "agc_enabled"),
    Stage("voice", "Voice changer", "Pitch and character effects. Open the Voice Changer page to set it up.", link="voice"),
    Stage("eq", "Equalizer", "Shapes the tone with up to five adjustable bands.", "eq_enabled"),
    Stage("deess", "De-esser", "Softens harsh \"s\" and \"sh\" sounds.", "deess_enabled"),
    Stage("comp", "Compressor", "Evens out loud and quiet speech for a fuller, more even sound.", "comp_enabled"),
    Stage("output", "Output", "Final level, peak protection and timing before the audio leaves the app."),
)
STAGE_BY_ID = {s.id: s for s in STAGES}

CARDS = {
    "devices": (("output", "Output device", "Where the PC plays the phone's voice."),
                ("latency", "Delay and stability", "Trade a little delay for protection against network hiccups."),
                ("monitor", "Monitoring", "Hear your processed voice on headphones.")),
    "network": (("listen", "Listening", "How the PC accepts audio from the phone."),
                ("options", "Connection options", "Rules for finding and accepting phones.")),
    "settings": (("general", "General", "How the app starts and behaves."),
                 ("shortcuts", "Shortcuts", "Keys that work in any app, including full-screen games."),
                 ("appearance", "Appearance", "How the app looks."),
                 ("recording", "Recording", "Where recordings go and what they contain.")),
}


# ==============================================================================
# THE REGISTRY
# ==============================================================================
_S = []


def add(**kw):
    _S.append(Setting(**kw))


def fx(key, group, label, summary, details, kind, **kw):
    add(key=key, target="fx", page="sound", group=group, label=label, summary=summary, details=details, kind=kind, **kw)


def cfg(key, page, group, label, summary, details, kind, **kw):
    add(key=key, target="cfg", page=page, group=group, label=label, summary=summary, details=details, kind=kind, **kw)


# ---- input ----------------------------------------------------------------------------------------------------------
fx("gain", "input", "Mic gain", "Boosts or lowers the phone's signal before any effect.",
   "Raise it if you sound quiet in other apps, and lower it if the level meter often reaches the red zone. Gain also raises "
   "background noise, so combine a big boost with Noise suppression, or let Auto gain do the work. The limiter at the end "
   "catches any peaks.", "slider", lo=-12.0, hi=18.0, step=0.5, fmt="db", origin=0.0, conv="db_lin",
   keywords="volume loudness level boost quiet louder")
fx("invert_polarity", "input", "Invert polarity", "Flips the waveform upside down.",
   "You almost never need this. It only matters when you also record this voice with a second microphone: if the two signals "
   "cancel each other and the voice sounds thin or hollow, invert one of them. On its own it sounds identical.",
   "toggle", advanced=True, keywords="phase flip")

# ---- filters --------------------------------------------------------------------------------------------------------
fx("lowcut_enabled", "filters", "Low-cut filter", "Removes rumble and desk thumps below a chosen frequency.",
   "A voice carries almost no energy below 80 Hz, but desk knocks, wind and handling noise do. Keep this on. It also reduces the "
   "boomy bass you get when the phone is close to your mouth.", "toggle", short="Low-cut",
   keywords="high-pass highpass rumble wind thump bass")
fx("lowcut_hz", "filters", "Low-cut frequency", "Sound below this pitch is reduced.",
   "80 Hz suits most voices. Go to 100 to 150 Hz for a deep, boomy voice or a noisy desk, and stay at 60 to 80 Hz for a fuller "
   "broadcast sound. Above about 200 Hz a voice starts to sound thin.", "slider", lo=40, hi=300, step=5, fmt="hz",
   needs="lowcut_enabled", short="Frequency", keywords="rumble wind thump bass high-pass cut-off")
fx("lowcut_slope", "filters", "Low-cut steepness", "How sharply the filter cuts below the frequency.",
   "12 dB per octave is gentle and natural. 24 dB per octave removes rumble more firmly but can make the voice slightly less "
   "natural around the cut-off.", "choice", choices=(("12", "Gentle, 12 dB/oct"), ("24", "Steep, 24 dB/oct")),
   advanced=True, needs="lowcut_enabled", short="Steepness", keywords="rumble slope high-pass")
fx("highcut_enabled", "filters", "High-cut filter", "Softens hiss and a harsh top end above a chosen frequency.",
   "Phone microphones can add hiss and a sharp edge above 10 kHz. A cut-off around 12 to 16 kHz tames it. Most chat apps ignore "
   "audio above 12 kHz anyway, so you rarely lose anything you could hear.", "toggle", advanced=True, short="High-cut",
   keywords="low-pass lowpass hiss treble")
fx("highcut_hz", "filters", "High-cut frequency", "Sound above this pitch is reduced.",
   "Start around 14 kHz. Lower values make the voice darker and warmer; going under 8 kHz starts to sound like a telephone.",
   "slider", lo=4000, hi=20000, step=500, fmt="hz", advanced=True, needs="highcut_enabled", short="Frequency",
   keywords="hiss treble low-pass cut-off")

# ---- noise suppression ---------------------------------------------------------------------------------------------
fx("smart_noise_cancel", "noise", "Noise suppression", "Learns steady background noise and removes it from your voice.",
   "Works on constant sounds such as fans, air conditioning, hiss and room hum. It does not remove other voices or sudden "
   "sounds like keyboard clicks. Balanced mode adds about 10 ms of delay and Fast mode about 5 ms.", "toggle",
   short="Enable", keywords="denoise noise cancel fan hiss background hum")
fx("noise_cancel_amount", "noise", "Noise suppression strength", "How aggressively noise is removed.",
   "Higher values remove more noise but can make the voice sound slightly watery, especially on quiet words. Start at 65 % and "
   "raise it only while you can still hear noise between words.", "slider", lo=0.0, hi=1.0, step=0.05, fmt="pct",
   needs="smart_noise_cancel", short="Strength")
fx("noise_quality", "noise", "Noise suppression mode", "Trades a little quality for lower delay.",
   "Balanced uses a longer analysis window, sounds cleaner and adds about 10 ms. Fast adds about 5 ms with slightly less precise "
   "noise removal. Choose Fast only when every millisecond counts, for example while monitoring yourself.", "choice",
   choices=(("high", "Balanced, +10 ms"), ("fast", "Fast, +5 ms")), needs="smart_noise_cancel", short="Mode")
fx("noise_max_reduction_db", "noise", "Maximum noise reduction", "Caps how much quieter the noise may become.",
   "Automatic follows the Strength slider. Set a fixed limit such as 12 dB to leave a little natural room sound, so the voice "
   "does not seem to be cut out of silence. A higher limit means a deader background.", "slider", lo=0, hi=40, step=1,
   fmt="reduce", advanced=True, needs="smart_noise_cancel", short="Maximum reduction")
fx("noise_learn_s", "noise", "Noise learning time", "How long the suppressor remembers the quietest moments.",
   "The noise level is found from the quietest moments in this window. Longer windows are more accurate but react slowly when "
   "the noise changes, for example when a fan switches speed. Shorter windows adapt quickly but may mistake long sounds for "
   "noise. 2 seconds is a good balance.", "slider", lo=1.0, hi=8.0, step=0.5, fmt="s", advanced=True,
   needs="smart_noise_cancel", short="Learning time")

# ---- gate ---------------------------------------------------------------------------------------------------------
fx("gate_enabled", "gate", "Noise gate", "Silences the microphone when you are not speaking.",
   "Closes the signal between words so leftover noise is not heard. It cannot clean noise while you talk, so use it together "
   "with Noise suppression. Set the threshold just above your background noise.", "toggle", short="Enable",
   keywords="expander mute silence cut")
fx("gate_threshold_db", "gate", "Gate threshold", "The level your voice must reach to open the gate.",
   "Stay quiet and watch the level meter on the Dashboard, then place the threshold a few dB above what it shows. If the "
   "beginnings of words are cut off, lower it. If noise still gets through between words, raise it.", "slider",
   lo=-80, hi=-20, step=1, fmt="dbu", needs="gate_enabled", short="Threshold")
fx("gate_release_ms", "gate", "Gate release", "How slowly the gate closes after you stop talking.",
   "A longer release lets word endings fade naturally, a shorter one cuts quickly and sounds tighter. 150 to 250 ms suits speech.",
   "slider", lo=40, hi=600, step=10, fmt="ms", needs="gate_enabled", short="Release")
fx("gate_attack_ms", "gate", "Gate attack", "How fast the gate opens when you start talking.",
   "Short attacks of 1 to 5 ms keep the first syllable intact. Longer values soften the opening but can swallow the start of words.",
   "slider", lo=0.5, hi=50, step=0.5, fmt="ms1", advanced=True, needs="gate_enabled", short="Attack")
fx("gate_hold_ms", "gate", "Gate hold", "How long the gate stays open after the level drops.",
   "Prevents flutter when you speak softly or pause briefly inside a sentence. Raise it if the gate chatters, lower it for "
   "quicker closing.", "slider", lo=0, hi=500, step=10, fmt="ms", advanced=True, needs="gate_enabled", short="Hold")
fx("gate_depth_db", "gate", "Gate depth", "How quiet the signal gets while the gate is closed.",
   "-40 dB mutes the background almost completely yet sounds natural. A shallower setting such as -15 dB only lowers the "
   "background, which hides the pumping you can hear when a gate opens and closes.", "slider", lo=-80, hi=-6, step=1,
   fmt="dbu", advanced=True, needs="gate_enabled", short="Closed attenuation")
fx("gate_hysteresis_db", "gate", "Gate hysteresis", "Extra margin before the gate closes again.",
   "The gate closes only when the level falls this far below the threshold. It stops fluttering when your voice hovers around "
   "the threshold. 3 dB is usual.", "slider", lo=0, hi=12, step=0.5, fmt="dbu", advanced=True, needs="gate_enabled",
   short="Hysteresis")

# ---- auto gain -------------------------------------------------------------------------------------------------------
fx("agc_enabled", "agc", "Auto gain", "Keeps your voice at a steady loudness.",
   "Slowly raises quiet speech and lowers loud speech, so your level stays the same when you move closer to or further from "
   "the phone. It only reacts to speech, so it does not pump up background noise between words.", "toggle", short="Enable",
   keywords="leveler leveller normalize automatic volume")
fx("agc_target_db", "agc", "Auto gain target level", "The loudness Auto gain aims for.",
   "Measured as average level in dBFS. -20 dBFS is a healthy speaking level for chat apps. Raise it to -16 for a louder voice "
   "or lower it to -24 to leave more headroom.", "slider", lo=-30, hi=-10, step=1, fmt="dbfs", needs="agc_enabled",
   short="Target level")
fx("agc_max_gain_db", "agc", "Auto gain maximum boost", "The most Auto gain is allowed to raise your voice.",
   "Lower this if Auto gain brings up background noise or distant sounds too much when you are quiet.", "slider", lo=0, hi=36,
   step=1, fmt="db0", advanced=True, needs="agc_enabled", short="Maximum boost")
fx("agc_attack_ms", "agc", "Auto gain reduction speed", "How fast the gain drops when you get louder.",
   "Short values catch a sudden shout quickly, long values keep the level natural. The default of 120 ms works for most voices.",
   "slider", lo=20, hi=1000, step=10, fmt="ms", advanced=True, needs="agc_enabled", short="Reduction speed")
fx("agc_release_ms", "agc", "Auto gain recovery speed", "How fast the gain rises when you get quieter.",
   "Slow values of 1 to 3 seconds sound natural. Fast values make the background swell between sentences.", "slider",
   lo=100, hi=5000, step=50, fmt="ms", advanced=True, needs="agc_enabled", short="Recovery speed")

# ---- equalizer -------------------------------------------------------------------------------------------------------
fx("eq_enabled", "eq", "Equalizer", "Shapes the tone of your voice with up to five bands.",
   "Drag the numbered points on the graph: left and right change the frequency, up and down change the gain. Scroll the mouse "
   "wheel over a point to change its width. A few dB is plenty, because large boosts sound harsh and raise noise.",
   "toggle", short="Enable", keywords="tone bass treble warmth clarity air")
_BAND_NAMES = {1: "low band", 2: "low-mid band", 3: "mid band", 4: "high-mid band", 5: "high band"}
_BAND_HINTS = {1: "Warmth and body. Boost a little for a fuller voice, cut to remove boominess.",
               2: "Where muddiness lives, around 200 to 500 Hz. A small cut often makes a voice clearer.",
               3: "Presence and clarity, around 2 to 4 kHz. A small boost helps words cut through.",
               4: "Edge and bite. Useful for taming a harsh microphone or adding definition.",
               5: "Air and brightness. A gentle boost adds sparkle, a cut softens a bright microphone."}
for _n in range(1, dsp.EQ_BANDS + 1):
    _nm = _BAND_NAMES[_n]
    fx(f"eq{_n}_gain", "eq", f"EQ band {_n} gain", f"Boost or cut for the {_nm}.", _BAND_HINTS[_n] +
       " Notch bands ignore this value because they always remove their frequency.", "slider", lo=-18, hi=18, step=0.5,
       fmt="db", origin=0.0, needs="eq_enabled", short="Gain")
    fx(f"eq{_n}_freq", "eq", f"EQ band {_n} frequency", f"Centre of the {_nm}.",
       "The frequency this band acts on. For a shelf it is the point where the change begins. Dragging the point on the graph "
       "sets this and the gain together.", "slider", lo=20, hi=20000, step=1, fmt="hz", log=True, needs="eq_enabled",
       short="Frequency")
    fx(f"eq{_n}_q", "eq", f"EQ band {_n} width", f"How narrow the {_nm} is.",
       "Low values around 0.5 are broad and gentle, values of 4 or more are surgical. For shelves this sets how steep the "
       "transition is. Scroll over a point on the graph to change it.", "slider", lo=0.2, hi=8.0, step=0.01, fmt="q", log=True,
       advanced=True, needs="eq_enabled", short="Width (Q)")
    fx(f"eq{_n}_type", "eq", f"EQ band {_n} type", f"Shape of the {_nm}.",
       "Bell boosts or cuts around the frequency. Low shelf changes everything below it and High shelf everything above it. "
       "Notch removes one narrow frequency completely, which is handy for a single whistle or hum.", "choice",
       choices=(("peak", "Bell"), ("lowshelf", "Low shelf"), ("highshelf", "High shelf"), ("notch", "Notch")),
       advanced=True, needs="eq_enabled", short="Type")
    fx(f"eq{_n}_on", "eq", f"EQ band {_n} active", f"Switches the {_nm} on or off.",
       "Turns this band off without losing its settings, which is a quick way to hear what it does.", "toggle",
       advanced=True, needs="eq_enabled", short="Active")

# ---- de-esser --------------------------------------------------------------------------------------------------------
fx("deess_enabled", "deess", "De-esser", "Softens harsh \"s\" and \"sh\" sounds.",
   "Only the sibilance range is turned down, and only when it gets too loud, so the rest of the voice stays unchanged. Useful "
   "after boosting high frequencies or with a bright microphone. It works best together with a little compression.",
   "toggle", short="Enable", keywords="sibilance ess harsh")
fx("deess_freq", "deess", "De-esser frequency", "Where your \"s\" sounds are strongest.",
   "Around 5 to 7 kHz for most voices, a little lower for deep voices and higher for light ones. Say \"sss\" and sweep the "
   "value until the reduction is strongest.", "slider", lo=3000, hi=10000, step=100, fmt="hz", needs="deess_enabled",
   short="Frequency")
fx("deess_threshold_db", "deess", "De-esser threshold", "Sibilance louder than this is reduced.",
   "Lower values catch more of the \"s\" sounds. Raise it until normal speech passes untouched and only harsh peaks are "
   "reduced.", "slider", lo=-60, hi=-10, step=1, fmt="dbu", needs="deess_enabled", short="Threshold")
fx("deess_range_db", "deess", "De-esser maximum reduction", "The most the sibilance may be turned down.",
   "4 to 8 dB sounds natural. More than that starts to sound like a lisp.", "slider", lo=0, hi=18, step=0.5, fmt="dbu",
   needs="deess_enabled", short="Maximum reduction")

# ---- compressor ------------------------------------------------------------------------------------------------------
fx("comp_enabled", "comp", "Compressor", "Evens out loud and quiet speech for a fuller sound.",
   "Turns down the loudest parts and then brings everything back up, so quiet words are easier to hear. It adds punch and "
   "presence but also lifts background noise slightly, so set up the gate and Noise suppression first.", "toggle",
   short="Enable", keywords="dynamics punch even level")
fx("comp_threshold_db", "comp", "Compressor threshold", "Level above which compression starts.",
   "Measured as average level. Lower the threshold until the gain reduction readout on the Dashboard shows 3 to 6 dB on your "
   "loudest words.", "slider", lo=-50, hi=-5, step=1, fmt="dbu", needs="comp_enabled", short="Threshold")
fx("comp_ratio", "comp", "Compressor ratio", "How strongly levels above the threshold are reduced.",
   "2 : 1 is gentle, 3 to 4 : 1 is typical for voice, and anything above 8 : 1 starts to behave like a limiter.", "slider",
   lo=1.5, hi=10, step=0.5, fmt="ratio", needs="comp_enabled", short="Ratio")
fx("comp_makeup_db", "comp", "Compressor make-up gain", "Brings the level back up after compression.",
   "Set it to roughly the gain reduction you see on normal speech, so loudness stays similar but quiet words come forward.",
   "slider", lo=0, hi=18, step=0.5, fmt="db", needs="comp_enabled", short="Make-up gain")
fx("comp_attack_ms", "comp", "Compressor attack", "How quickly it reacts to loud sounds.",
   "Fast attacks catch peaks but can dull consonants. Slower attacks let the start of each word through for more punch.",
   "slider", lo=1, hi=100, step=1, fmt="ms", advanced=True, needs="comp_enabled", short="Attack")
fx("comp_release_ms", "comp", "Compressor release", "How quickly it lets go afterwards.",
   "Too short sounds jittery and too long sounds as if the voice is being held down. 100 to 250 ms is usual.", "slider",
   lo=30, hi=1000, step=10, fmt="ms", advanced=True, needs="comp_enabled", short="Release")
fx("comp_knee_db", "comp", "Compressor knee", "How gradually compression begins.",
   "0 dB switches on abruptly. Higher values ease in around the threshold, for a smoother and less noticeable result.",
   "slider", lo=0, hi=24, step=1, fmt="dbu", advanced=True, needs="comp_enabled", short="Knee")
fx("comp_mix", "comp", "Compressor dry/wet mix", "Blends the original voice with the compressed voice.",
   "100 % is normal compression. Around 50 % keeps natural dynamics while adding density, which is called parallel "
   "compression.", "slider", lo=0.0, hi=1.0, step=0.05, fmt="pct", advanced=True, needs="comp_enabled", short="Dry/wet mix")

# ---- output ----------------------------------------------------------------------------------------------------------
fx("out_gain_db", "output", "Output level", "Final volume trim, applied before the limiter.",
   "Raises or lowers the level other apps receive. Raise it if an app is still too quiet at full gain. The limiter prevents "
   "clipping.", "slider", lo=-24, hi=12, step=0.5, fmt="db", origin=0.0, short="Level")
fx("limiter_enabled", "output", "Limiter", "Prevents loud peaks from distorting.",
   "Smoothly limits any peak above the ceiling instead of letting it clip harshly. Leave it on unless you need the signal "
   "completely untouched.", "toggle", short="Limiter", keywords="clip distortion peak protect")
fx("limiter_ceiling_db", "output", "Limiter ceiling", "The highest level the output may reach.",
   "-1 dBFS leaves a small safety margin for apps that add their own processing. Lower it to -3 if a streaming app distorts "
   "your loudest moments.", "slider", lo=-6, hi=0, step=0.5, fmt="dbfs", needs="limiter_enabled", short="Ceiling")
fx("delay_ms", "output", "Lip-sync delay", "Delays your voice so it lines up with your webcam picture.",
   "Webcams usually delay the picture by 100 to 300 ms, so your voice arrives early. Add the same amount here until lips and "
   "voice line up. It adds exactly that much delay, so leave it at 0 if you do not use video.", "slider", lo=0, hi=500,
   step=5, fmt="ms", short="Lip-sync delay", keywords="webcam video sync latency offset")
fx("monitor_volume", "output", "Monitor volume", "How loud you hear yourself on headphones.",
   "Only changes what you hear through the monitor device. It does not change what other apps receive.", "slider",
   lo=0.0, hi=1.0, step=0.05, fmt="pct", short="Monitor volume")
cfg("audio.out_channels", "sound", "output", "Output channels", "Which speaker channel carries your voice.",
    "Normally both, so apps that listen to either channel hear you. Some apps only read one channel of a stereo input. If your "
    "voice is missing or only in one ear there, make sure this is set to both. Left or right is for special mixing setups.",
    "choice", choices=(("both", "Both"), ("left", "Left only"), ("right", "Right only")), advanced=True, short="Channels")

# ---- voice changer ---------------------------------------------------------------------------------------------------
add(key="vc.enabled", target="vc", page="voice", group="voice", label="Voice changer",
    summary="Turns the voice effect on or off.",
    details="When off, audio passes straight through with no processing and no extra delay.", kind="toggle", short="Enable")
add(key="vc.pitch_semitones", target="vc", page="voice", group="voice", label="Pitch shift",
    summary="Moves the voice up or down in musical steps.",
    details="12 semitones is one octave. Small shifts of 1 to 2 semitones sound natural, larger ones sound more like a character. "
            "Shifting the pitch adds about 15 ms of delay.", kind="slider", lo=-12, hi=12, step=0.5, fmt="st", origin=0.0,
    short="Pitch shift", keywords="deeper higher chipmunk octave")
add(key="vc.formant_semitones", target="vc", page="voice", group="voice", label="Formant shift",
    summary="Adjusts the vocal tract resonance independently of pitch.",
    details="Raising formants gives a brighter, lighter tone; lowering formants deepens throat and chest resonance without detuning pitch.",
    kind="slider", lo=-12, hi=12, step=0.5, fmt="st", origin=0.0, short="Formant shift", keywords="formant throat chest resonance tone")
add(key="vc.mix", target="vc", page="voice", group="voice", label="Effect amount",
    summary="Blends your natural voice with the effect.",
    details="100 % is the full effect. Lower values keep some of your own voice, which often sounds more believable.",
    kind="slider", lo=0.0, hi=1.0, step=0.05, fmt="pct", short="Effect amount", keywords="dry wet blend")

# ---- devices ---------------------------------------------------------------------------------------------------------
add(key="audio.api", target="cfg", page="devices", group="output", label="Audio backend",
    summary="The Windows audio system used for output.",
    details="Auto picks the best one available, usually WASAPI, which has the lowest delay. Use DirectSound or MME only if a "
            "device you need does not appear under WASAPI.", kind="custom", short="Backend", keywords="wasapi mme directsound driver")
add(key="audio.output_device", target="sys", page="devices", group="output", label="Output device",
    summary="Where the voice is sent. Pick VB-CABLE to use it as a microphone in other apps.",
    details="Choose \"CABLE Input\" to make your phone appear as a microphone in Discord, OBS, Zoom and similar apps, where you "
            "then pick \"CABLE Output\" as the microphone. Choose your speakers or headphones to simply hear it yourself.",
    kind="custom", short="Device", keywords="vb-cable virtual cable speakers headphones microphone")
add(key="audio.jitter_ms", target="cfg", page="devices", group="latency", label="Delay profile",
    summary="How much audio is held back to smooth out network hiccups.",
    details="Wi-Fi delivers audio in uneven bursts. The receiver keeps a small cushion so those bursts do not become gaps. "
            "A smaller cushion means less delay but more risk of crackles on a weak connection. USB tethering is steady, "
            "so Low is usually fine there.", kind="custom", short="Profile", keywords="jitter buffer crackle stutter latency")
cfg("audio.adaptive_jitter", "devices", "latency", "Adaptive buffer", "Adds cushion automatically when the network gets bursty.",
    "When the connection is rough, the buffer grows a little and shrinks again when things calm down. This gives you low delay "
    "on a good connection and protection on a bad one.", "toggle", short="Adaptive buffer")
cfg("audio.adaptive_max_ms", "devices", "latency", "Maximum extra cushion", "How far the adaptive buffer may grow.",
    "A higher limit survives worse networks but lets the delay climb further before it settles. 80 ms is a good balance.",
    "slider", lo=0, hi=200, step=10, fmt="ms", advanced=True, needs="audio.adaptive_jitter", short="Maximum extra cushion")
cfg("audio.drift_correction", "devices", "latency", "Drift correction", "Removes slowly growing delay.",
    "Phone and PC clocks run at slightly different speeds, so the cushion can slowly fill up and add delay. When this is on, "
    "a few milliseconds are trimmed whenever the surplus stays for a second. Turn it off only if you hear tiny periodic skips.",
    "toggle", advanced=True, short="Drift correction")
cfg("audio.plc_mode", "devices", "latency", "Lost-packet filling", "What to play when a packet is lost.",
    "Repeat and fade replays the previous few milliseconds and fades out, which hides single losses. Silence leaves a short gap, "
    "which is more honest but easier to notice.", "choice",
    choices=(("repeat", "Repeat and fade"), ("silence", "Silence")), advanced=True, short="Lost packets")
cfg("audio.output_latency", "devices", "latency", "Sound card buffer", "Smaller buffers mean less delay but need a steadier computer.",
    "Low gives the least delay. If you hear crackling that is not caused by the network, try Medium or High. A busy computer "
    "or an older audio driver may need a larger buffer.", "choice",
    choices=(("low", "Low"), ("medium", "Medium"), ("high", "High")), short="Sound card buffer", keywords="crackle latency")
cfg("audio.high_priority", "devices", "latency", "High-priority audio threads",
    "Keeps the audio responsive when the computer is busy.",
    "Raises the receiver's threads above normal so a game or browser cannot starve them. Applies the next time the app starts.",
    "toggle", advanced=True, short="High priority", restart=True, keywords="performance cpu games")
add(key="audio.monitor_device", target="sys", page="devices", group="monitor", label="Monitor device",
    summary="The headphones used to hear yourself.",
    details="Pick your headphones or speakers. Start monitoring from the header or with Ctrl+E. A wired headset gives the least delay.",
    kind="custom", short="Device")

# ---- network ---------------------------------------------------------------------------------------------------------
add(key="network.port", target="cfg", page="network", group="listen", label="Listening port",
    summary="The port the phone sends audio to.",
    details="The default 5001 works for the standard app. Change it only if another program already uses it, and then enter "
            "the same port on the phone. The firewall rules follow the port you choose.", kind="custom", short="Port",
    keywords="udp tcp 5001")
cfg("network.stream_timeout_s", "network", "listen", "Connection-lost timeout", "How long to wait before the connection counts as lost.",
    "If no audio arrives for this long, the app shows the connection as lost and gets ready for a new stream. Raise it on a very "
    "unreliable network so short outages are not reported.", "slider", lo=0.5, hi=5.0, step=0.5, fmt="s", advanced=True,
    short="Timeout")
cfg("network.beacon", "network", "options", "Announce this PC", "Lets the phone find this computer automatically.",
    "Sends a small message every second and a half so \"Scan / Auto-Detect PC\" on the phone works. Turn it off on networks "
    "where broadcast messages are unwelcome, and type the address into the phone instead.", "toggle", short="Announce this PC",
    keywords="discovery broadcast scan auto-detect")
cfg("network.lock_client", "network", "options", "Lock to single phone", "Ignores additional phones while one is streaming.",
    "When disabled (default), PhoneMic receives and mixes multiple connected phones simultaneously. Enable this to lock to the first phone only.",
    "toggle", short="Lock to single phone")
cfg("network.accept_raw", "network", "options", "Accept plain audio packets", "Compatibility with old app versions.",
    "Older versions of the phone app send audio without a header. Leave this on unless the receiver picks up stray network "
    "traffic as noise.", "toggle", advanced=True, short="Accept plain audio packets")

# ---- settings --------------------------------------------------------------------------------------------------------
add(key="sys.start_with_windows", target="sys", page="settings", group="general", label="Start with Windows",
    summary="Opens the receiver when you sign in.", details="The app starts minimized so it is ready when you open the phone app.",
    kind="toggle", short="Start with Windows", keywords="startup boot autostart login")
cfg("app.start_minimized", "settings", "general", "Start minimized", "Opens to the taskbar instead of a window.",
    "Handy together with Start with Windows. You can still open the window from the taskbar.", "toggle", short="Start minimized")
cfg("app.always_on_top", "settings", "general", "Always on top", "Keeps this window above other apps.",
    "Useful while you adjust settings during a game or a call. It can get in the way otherwise.", "toggle", short="Always on top")
cfg("app.tray_icon", "settings", "general", "Tray icon", "Shows an icon near the clock with quick controls.",
    "Right-click the icon to mute, record or quit, and click it to open the window. The icon changes colour with the connection "
    "state. It needs the optional pystray package, which the installer and the build script include.", "toggle",
    short="Tray icon", keywords="notification area system tray")
cfg("app.close_to_tray", "settings", "general", "Keep running when the window is closed",
    "The close button hides the window instead of quitting.",
    "The receiver keeps working in the background, so your phone microphone stays available. Choose Quit from the tray menu to exit "
    "completely. This needs the tray icon.", "toggle", needs="app.tray_icon", short="Close to tray",
    keywords="minimize background hide exit")
cfg("app.advanced_mode", "settings", "general", "Show advanced settings", "Shows every control instead of just the essentials.",
    "Simple view keeps the common controls. Advanced view adds attack and release times, filter steepness, EQ widths and types, "
    "buffer limits and more. Everything keeps working the same either way.", "toggle", short="Advanced settings")
cfg("hotkeys.enabled", "settings", "shortcuts", "Global shortcuts", "Lets the keys below work in any app, including full-screen games.",
    "The receiver watches the keys you choose while it runs in the background. It does not block them, so the game or app you are in "
    "still receives them too. Pick keys you do not use for anything else, such as an F key or a mouse side button.", "toggle",
    short="Global shortcuts", keywords="hotkey keyboard keys")
for _key, _label, _summary, _details in (
        ("toggle_mute", "Mute shortcut", "Press once to mute and again to unmute.",
         "Does the same as the Mute button: the output goes silent and the phone is asked to pause. A combination such as Ctrl+Alt+M "
         "is hard to press by accident."),
        ("push_to_talk", "Push-to-talk key", "Hold the key to talk. You are silent whenever it is not held.",
         "While a push-to-talk key is set, you are silent until you hold it. The phone keeps streaming, so there is no delay when you "
         "press the key. Mouse side buttons work well. Clear the key to go back to an open microphone."),
        ("push_to_mute", "Push-to-mute key", "Hold the key to go silent for a moment.",
         "Useful for a cough or a quick word with someone in the room. You are heard again the moment you let go."),
        ("toggle_monitor", "Monitoring shortcut", "Press to start or stop hearing yourself.",
         "Does the same as the Monitor button. Set the headphones on the Audio Devices page first."),
        ("toggle_record", "Recording shortcut", "Press to start or stop recording.",
         "Does the same as the Record button. The file is saved in your recording folder."),
        ("toggle_bypass", "Compare shortcut", "Press to switch every effect off and on.",
         "Lets you compare your processed voice with the plain microphone without leaving a game. Does the same as the Effects button."),
        ("show_window", "Show window shortcut", "Press to bring this window to the front.",
         "Handy when the app runs in the tray or is hidden behind a full-screen game. It also works while the window is minimized.")):
    add(key=f"hotkeys.{_key}", target="cfg", page="settings", group="shortcuts", label=_label, summary=_summary, details=_details,
        kind="custom", needs="hotkeys.enabled", short=_label.replace(" shortcut", "").replace(" key", ""), keywords="hotkey keyboard key shortcut")
cfg("hotkeys.sound_cues", "settings", "shortcuts", "Sound cues", "Plays a short beep when a shortcut mutes or unmutes you.",
    "The beep plays through your Windows default sound device, not through the receiver's output, so other people do not hear it. "
    "If your Windows default device is VB-CABLE, leave this off or they will.", "toggle", needs="hotkeys.enabled", short="Sound cues",
    keywords="beep audio feedback")
cfg("app.ui_fps", "settings", "appearance", "Animation smoothness", "How often meters and graphs redraw.",
    "30 frames per second looks smooth and is light on the processor. 15 saves a little more power on slow computers. "
    "The meters are not drawn while the window is minimized.", "choice",
    choices=((15, "15 frames/s"), (30, "30 frames/s"), (60, "60 frames/s")), short="Animation smoothness")
cfg("app.accent", "settings", "appearance", "Accent colour", "The highlight colour used across the app.",
    "Changes sliders, switches and highlights. Applies the next time the app starts.", "choice",
    choices=(("teal", "Teal"), ("blue", "Blue"), ("violet", "Violet"), ("amber", "Amber"), ("rose", "Rose")),
    short="Accent colour", restart=True, keywords="theme color")
cfg("recording.source", "settings", "recording", "Recording content", "Whether recordings include your effects.",
    "With effects records exactly what other apps hear. Raw microphone records the untouched phone signal, which is useful if "
    "you want to edit the sound yourself later.", "choice",
    choices=(("processed", "With effects"), ("raw", "Raw microphone")), short="Content")
add(key="recording.folder", target="cfg", page="settings", group="recording", label="Recording folder",
    summary="Where recordings are saved.",
    details="Files are 16-bit mono WAV at 48 kHz, written in the background so disk activity cannot cause dropouts.",
    kind="custom", short="Folder")

REGISTRY = tuple(_S)
BY_KEY = {s.key: s for s in REGISTRY}
assert len(BY_KEY) == len(REGISTRY), "duplicate setting keys"


# ==============================================================================
# LOOK-UPS
# ==============================================================================
def by_page(page):
    return [s for s in REGISTRY if s.page == page]


def by_group(page, group):
    return [s for s in REGISTRY if s.page == page and s.group == group]


def default_of(s):
    """Default in UI units (dB for conv='db_lin')."""
    if s.target == "fx":
        v = dsp.FX_BASE[s.key]
    elif s.target == "cfg":
        sec, name = s.key.split(".")
        v = DEFAULTS[sec][name]
    elif s.key == "vc.enabled":
        v = False
    elif s.key == "vc.pitch_semitones":
        v = 0.0
    elif s.key == "vc.formant_semitones":
        v = 0.0
    elif s.key == "vc.mix":
        v = 1.0
    else:
        return None
    if s.conv == "db_lin":
        v = 20.0 * math.log10(v)
    return v


def tokens(text):
    return [t for t in "".join(c.lower() if c.isalnum() else " " for c in text).split() if t]


def search(query, include_advanced=True, limit=14):
    """Settings whose label, summary, keywords or text contain every word of the query, best matches first."""
    words = tokens(query)
    if not words:
        return []
    out = []
    for s in REGISTRY:
        if s.kind == "custom" and s.target == "sys":
            pass
        if s.advanced and not include_advanced:
            continue
        label = " ".join(tokens(s.label + " " + s.short))
        head = " ".join(tokens(s.summary + " " + s.keywords))
        body = " ".join(tokens(s.details))
        score = 0
        for w in words:
            if w in label:
                score += 6 if label.startswith(w) or f" {w}" in f" {label}" else 4
            elif w in head:
                score += 3
            elif w in body:
                score += 1
            else:
                score = -1
                break
        if score > 0:
            out.append((score, s))
    out.sort(key=lambda t: (-t[0], t[1].label))
    return [s for _, s in out[:limit]]
