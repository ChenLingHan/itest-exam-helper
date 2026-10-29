#define AppVersion "1.1.0-beta.7"
[Setup]
AppId={{961BA730-F384-44E9-A737-EB1606BC8A87}
AppName=iTEST Exam Helper
AppVersion={#AppVersion}
AppPublisher=ChenLingHan
AppPublisherURL=https://github.com/ChenLingHan/iTEST-exam-helper
DefaultDirName={localappdata}\Programs\iTEST-Exam-Helper
DefaultGroupName=iTEST Exam Helper
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=release
OutputBaseFilename=iTEST-Exam-Helper-{#AppVersion}-windows-x64-setup
SetupIconFile=assets\itest.ico
UninstallDisplayIcon={app}\iTEST.exe
LicenseFile=LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
SetupMutex=Local\iTEST.ModernDesktop

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: checkedonce

[Files]
Source: "dist\iTEST\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: ".release-tools\MicrosoftEdgeWebview2Setup.exe"; Flags: dontcopy

[Icons]
Name: "{group}\iTEST"; Filename: "{app}\iTEST.exe"; WorkingDir: "{app}\_internal"
Name: "{autodesktop}\iTEST"; Filename: "{app}\iTEST.exe"; WorkingDir: "{app}\_internal"; Tasks: desktopicon
Name: "{group}\Uninstall iTEST"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\iTEST.exe"; Description: "Launch iTEST"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2(): Boolean;
var V, K: String;
begin
  K := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := (RegQueryStringValue(HKLM32, K, 'pv', V) and (V <> '') and (V <> '0.0.0.0')) or
            (RegQueryStringValue(HKCU, K, 'pv', V) and (V <> '') and (V <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Code: Integer;
begin
  Result := '';
  if not HasWebView2() then begin
    if MsgBox('Microsoft WebView2 is required. Install it now from Microsoft? Internet access is required.', mbConfirmation, MB_YESNO) <> IDYES then begin
      Result := 'Please install Microsoft WebView2, then run Setup again.';
      exit;
    end;
    ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
    if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, Code) then begin
      Result := 'Unable to start Microsoft WebView2 Setup.';
      exit;
    end;
    if not HasWebView2() then
      Result := 'WebView2 installation did not complete. Check your connection and try again.';
  end;
end;
