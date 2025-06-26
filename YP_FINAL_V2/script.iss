[Setup]
AppName=Lyrics Insight
AppVersion=1.0
DefaultDirName={pf}\Lyrics Insight
DefaultGroupName=Lyrics Insight
OutputBaseFilename=LyricsInsightInstaller
Compression=lzma
SolidCompression=yes
DefaultDialogFontName=Segoe UI
WizardStyle=modern
SetupIconFile=lyrics_insight.ico

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "dist\Lyrics Insight\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "dist\Lyrics Insight\.env"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Lyrics Insight"; Filename: "{app}\Lyrics Insight.exe"; WorkingDir: "{app}"
Name: "{group}\Удалить Lyrics Insight"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Lyrics Insight.exe"; Description: "Запустить Lyrics Insight"; Flags: nowait postinstall skipifsilent
