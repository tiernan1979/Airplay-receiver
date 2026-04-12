[Setup]
AppName=AirPlay Receiver
AppVersion=1.0
DefaultDirName={autopf}\AirPlayReceiver
DefaultGroupName=AirPlay Receiver
OutputBaseFilename=AirPlayReceiverSetup
Compression=lzma
SolidCompression=yes
UninstallDisplayIcon={app}\AirPlayReceiver.exe
DisableDirPage=no
RestartApplications=yes
CloseApplications=yes
SetupIconFile=app.ico

[Files]
Source: "..\..\dist\AirPlayReceiver.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\AirPlay Receiver"; Filename: "{app}\AirPlayReceiver.exe"; IconFilename: "{app}\app.ico"
Name: "{commondesktop}\AirPlay Receiver"; Filename: "{app}\AirPlayReceiver.exe"; Tasks: desktopicon; IconFilename: "{app}\app.ico"

[Tasks]
Name: "desktopicon"; Description: "Create Desktop Icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\AirPlayReceiver.exe"; Description: "Launch AirPlay Receiver"; Flags: nowait postinstall skipifsilent