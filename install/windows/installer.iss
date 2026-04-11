[Setup]
AppName=AirPlay Receiver
AppVersion=1.0
DefaultDirName={pf}\AirPlayReceiver
DefaultGroupName=AirPlay Receiver
OutputBaseFilename=AirPlayReceiverSetup
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\..\dist\AirPlayReceiver.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AirPlay Receiver"; Filename: "{app}\AirPlayReceiver.exe"
Name: "{commondesktop}\AirPlay Receiver"; Filename: "{app}\AirPlayReceiver.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create Desktop Icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\AirPlayReceiver.exe"; Description: "Launch AirPlay Receiver"; Flags: nowait postinstall skipifsilent