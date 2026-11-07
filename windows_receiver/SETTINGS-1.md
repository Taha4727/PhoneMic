# PhoneMic Receiver 0.11.0: settings reference

Generated from the settings registry that drives the app, so it always matches what you see. Settings marked *advanced* only appear when **Settings view: Advanced** is turned on (bottom of the sidebar). You can also find any setting with the search box at the top of the window.

## Sound

### Input

The raw phone signal enters here. Set its level before any effect touches it.

**Mic gain**  
Boosts or lowers the phone's signal before any effect. Raise it if you sound quiet in other apps, and lower it if the level meter often reaches the red zone. Gain also raises background noise, so combine a big boost with Noise suppression, or let Auto gain do the work. The limiter at the end catches any peaks.  
_-12.0 dB to +18.0 dB, default +0.0 dB_

**Invert polarity** *(advanced)*  
Flips the waveform upside down. You almost never need this. It only matters when you also record this voice with a second microphone: if the two signals cancel each other and the voice sounds thin or hollow, invert one of them. On its own it sounds identical.  
_on or off, default off_

### Low-cut and high-cut

Removes sound below and above the range a voice needs.

**Low-cut filter**  
Removes rumble and desk thumps below a chosen frequency. A voice carries almost no energy below 80 Hz, but desk knocks, wind and handling noise do. Keep this on. It also reduces the boomy bass you get when the phone is close to your mouth.  
_on or off, default on_

**Low-cut frequency**  
Sound below this pitch is reduced. 80 Hz suits most voices. Go to 100 to 150 Hz for a deep, boomy voice or a noisy desk, and stay at 60 to 80 Hz for a fuller broadcast sound. Above about 200 Hz a voice starts to sound thin.  
_40 Hz to 300 Hz, default 80 Hz_

**Low-cut steepness** *(advanced)*  
How sharply the filter cuts below the frequency. 12 dB per octave is gentle and natural. 24 dB per octave removes rumble more firmly but can make the voice slightly less natural around the cut-off.  
_one of Gentle, 12 dB/oct, Steep, 24 dB/oct; default Gentle, 12 dB/oct_

**High-cut filter** *(advanced)*  
Softens hiss and a harsh top end above a chosen frequency. Phone microphones can add hiss and a sharp edge above 10 kHz. A cut-off around 12 to 16 kHz tames it. Most chat apps ignore audio above 12 kHz anyway, so you rarely lose anything you could hear.  
_on or off, default off_

**High-cut frequency** *(advanced)*  
Sound above this pitch is reduced. Start around 14 kHz. Lower values make the voice darker and warmer; going under 8 kHz starts to sound like a telephone.  
_4.0 kHz to 20.0 kHz, default 14.0 kHz_

### Noise suppression

Learns steady background noise such as fans and hiss, and removes it.

**Noise suppression**  
Learns steady background noise and removes it from your voice. Works on constant sounds such as fans, air conditioning, hiss and room hum. It does not remove other voices or sudden sounds like keyboard clicks. Balanced mode adds about 10 ms of delay and Fast mode about 5 ms.  
_on or off, default on_

**Noise suppression strength**  
How aggressively noise is removed. Higher values remove more noise but can make the voice sound slightly watery, especially on quiet words. Start at 65 % and raise it only while you can still hear noise between words.  
_0% to 100%, default 65%_

**Noise suppression mode**  
Trades a little quality for lower delay. Balanced uses a longer analysis window, sounds cleaner and adds about 10 ms. Fast adds about 5 ms with slightly less precise noise removal. Choose Fast only when every millisecond counts, for example while monitoring yourself.  
_one of Balanced, +10 ms, Fast, +5 ms; default Balanced, +10 ms_

**Maximum noise reduction** *(advanced)*  
Caps how much quieter the noise may become. Automatic follows the Strength slider. Set a fixed limit such as 12 dB to leave a little natural room sound, so the voice does not seem to be cut out of silence. A higher limit means a deader background.  
_Automatic to 40 dB, default Automatic_

**Noise learning time** *(advanced)*  
How long the suppressor remembers the quietest moments. The noise level is found from the quietest moments in this window. Longer windows are more accurate but react slowly when the noise changes, for example when a fan switches speed. Shorter windows adapt quickly but may mistake long sounds for noise. 2 seconds is a good balance.  
_1.0 s to 8.0 s, default 2.0 s_

### Noise gate

Silences the microphone between words so leftover noise is not heard.

**Noise gate**  
Silences the microphone when you are not speaking. Closes the signal between words so leftover noise is not heard. It cannot clean noise while you talk, so use it together with Noise suppression. Set the threshold just above your background noise.  
_on or off, default on_

**Gate threshold**  
The level your voice must reach to open the gate. Stay quiet and watch the level meter on the Dashboard, then place the threshold a few dB above what it shows. If the beginnings of words are cut off, lower it. If noise still gets through between words, raise it.  
_-80 dB to -20 dB, default -55 dB_

**Gate release**  
How slowly the gate closes after you stop talking. A longer release lets word endings fade naturally, a shorter one cuts quickly and sounds tighter. 150 to 250 ms suits speech.  
_40 ms to 600 ms, default 180 ms_

**Gate attack** *(advanced)*  
How fast the gate opens when you start talking. Short attacks of 1 to 5 ms keep the first syllable intact. Longer values soften the opening but can swallow the start of words.  
_0.5 ms to 50.0 ms, default 2.0 ms_

**Gate hold** *(advanced)*  
How long the gate stays open after the level drops. Prevents flutter when you speak softly or pause briefly inside a sentence. Raise it if the gate chatters, lower it for quicker closing.  
_0 ms to 500 ms, default 60 ms_

**Gate depth** *(advanced)*  
How quiet the signal gets while the gate is closed. -40 dB mutes the background almost completely yet sounds natural. A shallower setting such as -15 dB only lowers the background, which hides the pumping you can hear when a gate opens and closes.  
_-80 dB to -6 dB, default -40 dB_

**Gate hysteresis** *(advanced)*  
Extra margin before the gate closes again. The gate closes only when the level falls this far below the threshold. It stops fluttering when your voice hovers around the threshold. 3 dB is usual.  
_0 dB to 12 dB, default 3 dB_

### Auto gain

Keeps your voice at a steady loudness as you move around.

**Auto gain**  
Keeps your voice at a steady loudness. Slowly raises quiet speech and lowers loud speech, so your level stays the same when you move closer to or further from the phone. It only reacts to speech, so it does not pump up background noise between words.  
_on or off, default off_

**Auto gain target level**  
The loudness Auto gain aims for. Measured as average level in dBFS. -20 dBFS is a healthy speaking level for chat apps. Raise it to -16 for a louder voice or lower it to -24 to leave more headroom.  
_-30 dBFS to -10 dBFS, default -20 dBFS_

**Auto gain maximum boost** *(advanced)*  
The most Auto gain is allowed to raise your voice. Lower this if Auto gain brings up background noise or distant sounds too much when you are quiet.  
_+0 dB to +36 dB, default +24 dB_

**Auto gain reduction speed** *(advanced)*  
How fast the gain drops when you get louder. Short values catch a sudden shout quickly, long values keep the level natural. The default of 120 ms works for most voices.  
_20 ms to 1000 ms, default 120 ms_

**Auto gain recovery speed** *(advanced)*  
How fast the gain rises when you get quieter. Slow values of 1 to 3 seconds sound natural. Fast values make the background swell between sentences.  
_100 ms to 5000 ms, default 900 ms_

### Equalizer

Shapes the tone with up to five adjustable bands.

**Equalizer**  
Shapes the tone of your voice with up to five bands. Drag the numbered points on the graph: left and right change the frequency, up and down change the gain. Scroll the mouse wheel over a point to change its width. A few dB is plenty, because large boosts sound harsh and raise noise.  
_on or off, default on_

**EQ band 1 gain**  
Boost or cut for the low band. Warmth and body. Boost a little for a fuller voice, cut to remove boominess. Notch bands ignore this value because they always remove their frequency.  
_-18.0 dB to +18.0 dB, default +0.0 dB_

**EQ band 1 frequency**  
Centre of the low band. The frequency this band acts on. For a shelf it is the point where the change begins. Dragging the point on the graph sets this and the gain together.  
_20 Hz to 20.0 kHz, default 120 Hz_

**EQ band 1 width** *(advanced)*  
How narrow the low band is. Low values around 0.5 are broad and gentle, values of 4 or more are surgical. For shelves this sets how steep the transition is. Scroll over a point on the graph to change it.  
_0.20 to 8.0, default 0.71_

**EQ band 1 type** *(advanced)*  
Shape of the low band. Bell boosts or cuts around the frequency. Low shelf changes everything below it and High shelf everything above it. Notch removes one narrow frequency completely, which is handy for a single whistle or hum.  
_one of Bell, Low shelf, High shelf, Notch; default Low shelf_

**EQ band 1 active** *(advanced)*  
Switches the low band on or off. Turns this band off without losing its settings, which is a quick way to hear what it does.  
_on or off, default on_

**EQ band 2 gain**  
Boost or cut for the low-mid band. Where muddiness lives, around 200 to 500 Hz. A small cut often makes a voice clearer. Notch bands ignore this value because they always remove their frequency.  
_-18.0 dB to +18.0 dB, default +0.0 dB_

**EQ band 2 frequency**  
Centre of the low-mid band. The frequency this band acts on. For a shelf it is the point where the change begins. Dragging the point on the graph sets this and the gain together.  
_20 Hz to 20.0 kHz, default 350 Hz_

**EQ band 2 width** *(advanced)*  
How narrow the low-mid band is. Low values around 0.5 are broad and gentle, values of 4 or more are surgical. For shelves this sets how steep the transition is. Scroll over a point on the graph to change it.  
_0.20 to 8.0, default 1.0_

**EQ band 2 type** *(advanced)*  
Shape of the low-mid band. Bell boosts or cuts around the frequency. Low shelf changes everything below it and High shelf everything above it. Notch removes one narrow frequency completely, which is handy for a single whistle or hum.  
_one of Bell, Low shelf, High shelf, Notch; default Bell_

**EQ band 2 active** *(advanced)*  
Switches the low-mid band on or off. Turns this band off without losing its settings, which is a quick way to hear what it does.  
_on or off, default on_

**EQ band 3 gain**  
Boost or cut for the mid band. Presence and clarity, around 2 to 4 kHz. A small boost helps words cut through. Notch bands ignore this value because they always remove their frequency.  
_-18.0 dB to +18.0 dB, default +0.0 dB_

**EQ band 3 frequency**  
Centre of the mid band. The frequency this band acts on. For a shelf it is the point where the change begins. Dragging the point on the graph sets this and the gain together.  
_20 Hz to 20.0 kHz, default 2.5 kHz_

**EQ band 3 width** *(advanced)*  
How narrow the mid band is. Low values around 0.5 are broad and gentle, values of 4 or more are surgical. For shelves this sets how steep the transition is. Scroll over a point on the graph to change it.  
_0.20 to 8.0, default 1.0_

**EQ band 3 type** *(advanced)*  
Shape of the mid band. Bell boosts or cuts around the frequency. Low shelf changes everything below it and High shelf everything above it. Notch removes one narrow frequency completely, which is handy for a single whistle or hum.  
_one of Bell, Low shelf, High shelf, Notch; default Bell_

**EQ band 3 active** *(advanced)*  
Switches the mid band on or off. Turns this band off without losing its settings, which is a quick way to hear what it does.  
_on or off, default on_

**EQ band 4 gain**  
Boost or cut for the high-mid band. Edge and bite. Useful for taming a harsh microphone or adding definition. Notch bands ignore this value because they always remove their frequency.  
_-18.0 dB to +18.0 dB, default +0.0 dB_

**EQ band 4 frequency**  
Centre of the high-mid band. The frequency this band acts on. For a shelf it is the point where the change begins. Dragging the point on the graph sets this and the gain together.  
_20 Hz to 20.0 kHz, default 5.5 kHz_

**EQ band 4 width** *(advanced)*  
How narrow the high-mid band is. Low values around 0.5 are broad and gentle, values of 4 or more are surgical. For shelves this sets how steep the transition is. Scroll over a point on the graph to change it.  
_0.20 to 8.0, default 1.0_

**EQ band 4 type** *(advanced)*  
Shape of the high-mid band. Bell boosts or cuts around the frequency. Low shelf changes everything below it and High shelf everything above it. Notch removes one narrow frequency completely, which is handy for a single whistle or hum.  
_one of Bell, Low shelf, High shelf, Notch; default Bell_

**EQ band 4 active** *(advanced)*  
Switches the high-mid band on or off. Turns this band off without losing its settings, which is a quick way to hear what it does.  
_on or off, default on_

**EQ band 5 gain**  
Boost or cut for the high band. Air and brightness. A gentle boost adds sparkle, a cut softens a bright microphone. Notch bands ignore this value because they always remove their frequency.  
_-18.0 dB to +18.0 dB, default +0.0 dB_

**EQ band 5 frequency**  
Centre of the high band. The frequency this band acts on. For a shelf it is the point where the change begins. Dragging the point on the graph sets this and the gain together.  
_20 Hz to 20.0 kHz, default 8.0 kHz_

**EQ band 5 width** *(advanced)*  
How narrow the high band is. Low values around 0.5 are broad and gentle, values of 4 or more are surgical. For shelves this sets how steep the transition is. Scroll over a point on the graph to change it.  
_0.20 to 8.0, default 0.71_

**EQ band 5 type** *(advanced)*  
Shape of the high band. Bell boosts or cuts around the frequency. Low shelf changes everything below it and High shelf everything above it. Notch removes one narrow frequency completely, which is handy for a single whistle or hum.  
_one of Bell, Low shelf, High shelf, Notch; default High shelf_

**EQ band 5 active** *(advanced)*  
Switches the high band on or off. Turns this band off without losing its settings, which is a quick way to hear what it does.  
_on or off, default on_

### De-esser

Softens harsh "s" and "sh" sounds.

**De-esser**  
Softens harsh "s" and "sh" sounds. Only the sibilance range is turned down, and only when it gets too loud, so the rest of the voice stays unchanged. Useful after boosting high frequencies or with a bright microphone. It works best together with a little compression.  
_on or off, default off_

**De-esser frequency**  
Where your "s" sounds are strongest. Around 5 to 7 kHz for most voices, a little lower for deep voices and higher for light ones. Say "sss" and sweep the value until the reduction is strongest.  
_3.0 kHz to 10.0 kHz, default 6.5 kHz_

**De-esser threshold**  
Sibilance louder than this is reduced. Lower values catch more of the "s" sounds. Raise it until normal speech passes untouched and only harsh peaks are reduced.  
_-60 dB to -10 dB, default -30 dB_

**De-esser maximum reduction**  
The most the sibilance may be turned down. 4 to 8 dB sounds natural. More than that starts to sound like a lisp.  
_0 dB to 18 dB, default 6 dB_

### Compressor

Evens out loud and quiet speech for a fuller, more even sound.

**Compressor**  
Evens out loud and quiet speech for a fuller sound. Turns down the loudest parts and then brings everything back up, so quiet words are easier to hear. It adds punch and presence but also lifts background noise slightly, so set up the gate and Noise suppression first.  
_on or off, default off_

**Compressor threshold**  
Level above which compression starts. Measured as average level. Lower the threshold until the gain reduction readout on the Dashboard shows 3 to 6 dB on your loudest words.  
_-50 dB to -5 dB, default -22 dB_

**Compressor ratio**  
How strongly levels above the threshold are reduced. 2 : 1 is gentle, 3 to 4 : 1 is typical for voice, and anything above 8 : 1 starts to behave like a limiter.  
_1.5 : 1 to 10.0 : 1, default 3.0 : 1_

**Compressor make-up gain**  
Brings the level back up after compression. Set it to roughly the gain reduction you see on normal speech, so loudness stays similar but quiet words come forward.  
_+0.0 dB to +18.0 dB, default +3.0 dB_

**Compressor attack** *(advanced)*  
How quickly it reacts to loud sounds. Fast attacks catch peaks but can dull consonants. Slower attacks let the start of each word through for more punch.  
_1 ms to 100 ms, default 8 ms_

**Compressor release** *(advanced)*  
How quickly it lets go afterwards. Too short sounds jittery and too long sounds as if the voice is being held down. 100 to 250 ms is usual.  
_30 ms to 1000 ms, default 160 ms_

**Compressor knee** *(advanced)*  
How gradually compression begins. 0 dB switches on abruptly. Higher values ease in around the threshold, for a smoother and less noticeable result.  
_0 dB to 24 dB, default 6 dB_

**Compressor dry/wet mix** *(advanced)*  
Blends the original voice with the compressed voice. 100 % is normal compression. Around 50 % keeps natural dynamics while adding density, which is called parallel compression.  
_0% to 100%, default 100%_

### Output

Final level, peak protection and timing before the audio leaves the app.

**Output level**  
Final volume trim, applied before the limiter. Raises or lowers the level other apps receive. Raise it if an app is still too quiet at full gain. The limiter prevents clipping.  
_-24.0 dB to +12.0 dB, default +0.0 dB_

**Limiter**  
Prevents loud peaks from distorting. Smoothly limits any peak above the ceiling instead of letting it clip harshly. Leave it on unless you need the signal completely untouched.  
_on or off, default on_

**Limiter ceiling**  
The highest level the output may reach. -1 dBFS leaves a small safety margin for apps that add their own processing. Lower it to -3 if a streaming app distorts your loudest moments.  
_-6 dBFS to 0 dBFS, default -1 dBFS_

**Lip-sync delay**  
Delays your voice so it lines up with your webcam picture. Webcams usually delay the picture by 100 to 300 ms, so your voice arrives early. Add the same amount here until lips and voice line up. It adds exactly that much delay, so leave it at 0 if you do not use video.  
_0 ms to 500 ms, default 0 ms_

**Monitor volume**  
How loud you hear yourself on headphones. Only changes what you hear through the monitor device. It does not change what other apps receive.  
_0% to 100%, default 85%_

**Output channels** *(advanced)*  
Which speaker channel carries your voice. Normally both, so apps that listen to either channel hear you. Some apps only read one channel of a stereo input. If your voice is missing or only in one ear there, make sure this is set to both. Left or right is for special mixing setups.  
_one of Both, Left only, Right only; default Both_

## Voice Changer

### Voice changer

**Voice changer**  
Turns the voice effect on or off. When off, audio passes straight through with no processing and no extra delay.  
_on or off, default off_

**Pitch shift**  
Moves the voice up or down in musical steps. 12 semitones is one octave. Small shifts of 1 to 2 semitones sound natural, larger ones sound more like a character. Shifting the pitch adds about 21 ms of delay.  
_-12.0 semitones to +12.0 semitones, default no shift_

**Effect amount**  
Blends your natural voice with the effect. 100 % is the full effect. Lower values keep some of your own voice, which often sounds more believable.  
_0% to 100%, default 100%_

## Audio Devices

### Output device

Where the PC plays the phone's voice.

**Audio backend**  
The Windows audio system used for output. Auto picks the best one available, usually WASAPI, which has the lowest delay. Use DirectSound or MME only if a device you need does not appear under WASAPI.  


**Output device**  
Where the voice is sent. Pick VB-CABLE to use it as a microphone in other apps. Choose "CABLE Input" to make your phone appear as a microphone in Discord, OBS, Zoom and similar apps, where you then pick "CABLE Output" as the microphone. Choose your speakers or headphones to simply hear it yourself.  


### Delay and stability

Trade a little delay for protection against network hiccups.

**Delay profile**  
How much audio is held back to smooth out network hiccups. Wi-Fi delivers audio in uneven bursts. The receiver keeps a small cushion so those bursts do not become gaps. A smaller cushion means less delay but more risk of crackles on a weak connection. USB tethering is steady, so Low is usually fine there.  


**Adaptive buffer**  
Adds cushion automatically when the network gets bursty. When the connection is rough, the buffer grows a little and shrinks again when things calm down. This gives you low delay on a good connection and protection on a bad one.  
_on or off, default on_

**Maximum extra cushion** *(advanced)*  
How far the adaptive buffer may grow. A higher limit survives worse networks but lets the delay climb further before it settles. 80 ms is a good balance.  
_0 ms to 200 ms, default 80 ms_

**Drift correction** *(advanced)*  
Removes slowly growing delay. Phone and PC clocks run at slightly different speeds, so the cushion can slowly fill up and add delay. When this is on, a few milliseconds are trimmed whenever the surplus stays for a second. Turn it off only if you hear tiny periodic skips.  
_on or off, default on_

**Lost-packet filling** *(advanced)*  
What to play when a packet is lost. Repeat and fade replays the previous few milliseconds and fades out, which hides single losses. Silence leaves a short gap, which is more honest but easier to notice.  
_one of Repeat and fade, Silence; default Repeat and fade_

**Sound card buffer**  
Smaller buffers mean less delay but need a steadier computer. Low gives the least delay. If you hear crackling that is not caused by the network, try Medium or High. A busy computer or an older audio driver may need a larger buffer.  
_one of Low, Medium, High; default Low_

**High-priority audio threads** *(advanced)*  
Keeps the audio responsive when the computer is busy. Raises the receiver's threads above normal so a game or browser cannot starve them. Applies the next time the app starts.  
_on or off, default on_

### Monitoring

Hear your processed voice on headphones.

**Monitor device**  
The headphones used to hear yourself. Pick your headphones or speakers. Start monitoring from the header or with Ctrl+E. A wired headset gives the least delay.  


## Network

### Listening

How the PC accepts audio from the phone.

**Listening port**  
The port the phone sends audio to. The default 5001 works for the standard app. Change it only if another program already uses it, and then enter the same port on the phone. The firewall rules follow the port you choose.  


**Connection-lost timeout** *(advanced)*  
How long to wait before the connection counts as lost. If no audio arrives for this long, the app shows the connection as lost and gets ready for a new stream. Raise it on a very unreliable network so short outages are not reported.  
_0.5 s to 5.0 s, default 1.5 s_

### Connection options

Rules for finding and accepting phones.

**Announce this PC**  
Lets the phone find this computer automatically. Sends a small message every second and a half so "Scan / Auto-Detect PC" on the phone works. Turn it off on networks where broadcast messages are unwelcome, and type the address into the phone instead.  
_on or off, default on_

**Lock to the first phone**  
Ignores other phones while one is streaming. Prevents two phones from mixing into one garbled stream. A second phone is accepted as soon as the first one stops.  
_on or off, default on_

**Accept plain audio packets** *(advanced)*  
Compatibility with old app versions. Older versions of the phone app send audio without a header. Leave this on unless the receiver picks up stray network traffic as noise.  
_on or off, default on_

## Settings

### General

How the app starts and behaves.

**Start with Windows**  
Opens the receiver when you sign in. The app starts minimized so it is ready when you open the phone app.  
_on or off_

**Start minimized**  
Opens to the taskbar instead of a window. Handy together with Start with Windows. You can still open the window from the taskbar.  
_on or off, default off_

**Always on top**  
Keeps this window above other apps. Useful while you adjust settings during a game or a call. It can get in the way otherwise.  
_on or off, default off_

**Tray icon**  
Shows an icon near the clock with quick controls. Right-click the icon to mute, record or quit, and click it to open the window. The icon changes colour with the connection state. It needs the optional pystray package, which the installer and the build script include.  
_on or off, default on_

**Keep running when the window is closed**  
The close button hides the window instead of quitting. The receiver keeps working in the background, so your phone microphone stays available. Choose Quit from the tray menu to exit completely. This needs the tray icon.  
_on or off, default off_

**Show advanced settings**  
Shows every control instead of just the essentials. Simple view keeps the common controls. Advanced view adds attack and release times, filter steepness, EQ widths and types, buffer limits and more. Everything keeps working the same either way.  
_on or off, default off_

### Shortcuts

Keys that work in any app, including full-screen games.

**Global shortcuts**  
Lets the keys below work in any app, including full-screen games. The receiver watches the keys you choose while it runs in the background. It does not block them, so the game or app you are in still receives them too. Pick keys you do not use for anything else, such as an F key or a mouse side button.  
_on or off, default on_

**Mute shortcut**  
Press once to mute and again to unmute. Does the same as the Mute button: the output goes silent and the phone is asked to pause. A combination such as Ctrl+Alt+M is hard to press by accident.  


**Push-to-talk key**  
Hold the key to talk. You are silent whenever it is not held. While a push-to-talk key is set, you are silent until you hold it. The phone keeps streaming, so there is no delay when you press the key. Mouse side buttons work well. Clear the key to go back to an open microphone.  


**Push-to-mute key**  
Hold the key to go silent for a moment. Useful for a cough or a quick word with someone in the room. You are heard again the moment you let go.  


**Monitoring shortcut**  
Press to start or stop hearing yourself. Does the same as the Monitor button. Set the headphones on the Audio Devices page first.  


**Recording shortcut**  
Press to start or stop recording. Does the same as the Record button. The file is saved in your recording folder.  


**Compare shortcut**  
Press to switch every effect off and on. Lets you compare your processed voice with the plain microphone without leaving a game. Does the same as the Effects button.  


**Show window shortcut**  
Press to bring this window to the front. Handy when the app runs in the tray or is hidden behind a full-screen game. It also works while the window is minimized.  


**Sound cues**  
Plays a short beep when a shortcut mutes or unmutes you. The beep plays through your Windows default sound device, not through the receiver's output, so other people do not hear it. If your Windows default device is VB-CABLE, leave this off or they will.  
_on or off, default off_

### Appearance

How the app looks.

**Animation smoothness**  
How often meters and graphs redraw. 30 frames per second looks smooth and is light on the processor. 15 saves a little more power on slow computers. The meters are not drawn while the window is minimized.  
_one of 15 frames/s, 30 frames/s, 60 frames/s; default 30 frames/s_

**Accent colour**  
The highlight colour used across the app. Changes sliders, switches and highlights. Applies the next time the app starts.  
_one of Teal, Blue, Violet, Amber, Rose; default Teal_

### Recording

Where recordings go and what they contain.

**Recording content**  
Whether recordings include your effects. With effects records exactly what other apps hear. Raw microphone records the untouched phone signal, which is useful if you want to edit the sound yourself later.  
_one of With effects, Raw microphone; default With effects_

**Recording folder**  
Where recordings are saved. Files are 16-bit mono WAV at 48 kHz, written in the background so disk activity cannot cause dropouts.  

