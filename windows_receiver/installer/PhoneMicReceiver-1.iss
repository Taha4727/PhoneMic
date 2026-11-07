; PhoneMic Receiver installer - compile with Inno Setup 6 (https://jrsoftware.org/isinfo.php)
; Easiest: run installer\build_installer.bat, which builds the program folder first and then calls the compiler.

#define AppName "PhoneMic Receiver"
#define AppVersion "0.11.0"
#define AppExe "PhoneMicReceiver.exe"
#define AppPort "5001"

[Setup]
; AppId identifies this program to Windows so updates replace it instead of installing a second copy. Never change it.
AppId={{6F1D2C7A-3B54-4C0E-9E21-5A8B7D43C9A1}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=PhoneMic
DefaultDirName={autopf}\PhoneMic Receiver
DefaultGroupName=PhoneMic Receiver
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\assets\phonemic.ico
OutputDir=..\installer-output
OutputBaseFilename=PhoneMicReceiver-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Administrator rights are needed to create the firewall rules, which is what makes USB tethering work out of the box.
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\PhoneMicReceiver\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\SETTINGS.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\PhoneMic Receiver"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\PhoneMic Receiver"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
; Inbound firewall rules, same names the app itself checks for (so "Fix firewall" never has to be pressed).
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PhoneMic Receiver (UDP {#AppPort})"""; Flags: runhidden; StatusMsg: "Configuring Windows Firewall..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""PhoneMic Receiver (UDP {#AppPort})"" dir=in action=allow protocol=UDP localport={#AppPort} profile=any enable=yes"; Flags: runhidden; StatusMsg: "Configuring Windows Firewall..."
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PhoneMic Receiver (TCP {#AppPort})"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""PhoneMic Receiver (TCP {#AppPort})"" dir=in action=allow protocol=TCP localport={#AppPort} profile=any enable=yes"; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PhoneMic Receiver App"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""PhoneMic Receiver App"" dir=in action=allow program=""{app}\{#AppExe}"" profile=any enable=yes"; Flags: runhidden
Filename: "{app}\{#AppExe}"; Description: "Start PhoneMic Receiver"; Flags: nowait postinstall skipifsilent
Filename: "https://vb-audio.com/Cable/"; Description: "Open the VB-CABLE download page (free; lets Discord, OBS and others use your phone as a microphone)"; Flags: shellexec postinstall skipifsilent unchecked

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PhoneMic Receiver (UDP {#AppPort})"""; Flags: runhidden; RunOnceId: "FirewallUdp"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PhoneMic Receiver (TCP {#AppPort})"""; Flags: runhidden; RunOnceId: "FirewallTcp"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""PhoneMic Receiver App"""; Flags: runhidden; RunOnceId: "FirewallApp"

[Code]
function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  { make sure the program (and its tray icon) is closed so every file can be removed }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#AppExe}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    if MsgBox('Also remove your PhoneMic settings and saved presets?', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(ExpandConstant('{localappdata}\PhoneMic'), True, True, True);
  end;
end;
