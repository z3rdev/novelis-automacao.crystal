#ifndef MyAppVersion
#error Compile usando scripts/build-installer.ps1 para definir a versao real.
#endif
#ifndef CrystalRuntimeFilename
#error Compile usando scripts/build-installer.ps1 para identificar o MSI validado.
#endif

#define MyAppName "Novelis Cargo Hub"
#define MyAppPublisher "Novelis"
#define MyAppExeName "novelis-cargo-hub.exe"
#define MyAppId "{{6F3F0D7A-4B6B-4C6C-9A08-91B0D7A9E9F1}"
#ifdef PrivateConfiguration
#define ConfigurationSuffix "-PRIVADO"
#else
#define ConfigurationSuffix ""
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppPublisher={#MyAppPublisher}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Automacao Novelis
DefaultGroupName={#MyAppName}
DisableDirPage=no
UsePreviousAppDir=yes
PrivilegesRequired=lowest
MinVersion=10.0.10240
ArchitecturesAllowed=x64compatible
#ifdef CrystalDevelopment
#ifdef PrivateConfiguration
OutputDir=..\runtime\private-installer
#else
OutputDir=..\runtime\crystal-build\development\installer
#endif
#ifdef InstallerRevision
OutputBaseFilename=NovelisCargoHubSetup-{#MyAppVersion}-{#InstallerRevision}{#ConfigurationSuffix}-TESTE-NaoDistribuir
#else
OutputBaseFilename=NovelisCargoHubSetup-{#MyAppVersion}{#ConfigurationSuffix}-TESTE-NaoDistribuir
#endif
#else
#ifdef PrivateConfiguration
OutputDir=..\runtime\private-installer
#else
OutputDir=..\dist\installer
#endif
#ifdef InstallerRevision
OutputBaseFilename=NovelisCargoHubSetup-{#MyAppVersion}-{#InstallerRevision}{#ConfigurationSuffix}
#else
OutputBaseFilename=NovelisCargoHubSetup-{#MyAppVersion}{#ConfigurationSuffix}
#endif
#endif
#ifdef CrystalDevelopment
Compression=zip
#else
Compression=lzma2
SolidCompression=yes
#endif
WizardStyle=modern
WizardImageFile=..\runtime\installer-branding\wizard.bmp
WizardSmallImageFile=..\runtime\installer-branding\wizard-small.bmp
WizardImageBackColor=$0045250B
WizardSizePercent=120,110
DisableWelcomePage=no
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=..\FRONTEND-HUB\src-tauri\icons\icon.ico
SetupLogging=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "..\scripts\setup\stop-installed-stack.ps1"; Flags: dontcopy
Source: ".\crystal\runtime-probe.ps1"; Flags: dontcopy
Source: ".\crystal\inspect-runtime.ps1"; Flags: dontcopy
Source: "..\scripts\install-crystal-runtime.ps1"; Flags: dontcopy
Source: "..\runtime\installer-inputs\crystal\{#CrystalRuntimeFilename}"; Flags: dontcopy
Source: "..\runtime\installer-inputs\crystal\crystal-runtime.manifest.json"; Flags: dontcopy
Source: "..\FRONTEND-HUB\src-tauri\target\release\novelis-cargo-hub.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: ".\.automacao-novelis-install"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\runtime\installer-inputs\release\installed-release.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\runtime\installer-inputs\python312\*"; DestDir: "{app}\runtime\python312"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\runtime\installer-inputs\webview2\*"; DestDir: "{app}\installer-cache\webview2"; Flags: ignoreversion
Source: ".\cache\vc_redist.x64.exe"; DestDir: "{app}\installer-cache"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\runtime\installer-inputs\wheels\*"; DestDir: "{app}\installer-cache\wheels"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\runtime\installer-inputs\dacte-vendor\*"; DestDir: "{app}\installer-cache\dacte"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\ms-playwright\*"; DestDir: "{app}\ms-playwright"; Flags: recursesubdirs createallsubdirs ignoreversion skipifsourcedoesntexist
Source: "..\BACKEND\app\*"; DestDir: "{app}\BACKEND\app"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "__pycache__\*,*.pyc,*.pyo,*.log,.env,.env.*"
Source: "..\BACKEND\pyproject.toml"; DestDir: "{app}\BACKEND"; Flags: ignoreversion
Source: "..\runtime\installer-inputs\BACKEND.env.example"; DestDir: "{app}\BACKEND"; DestName: ".env.example"; Flags: ignoreversion
#ifdef PrivateConfiguration
Source: "..\runtime\installer-inputs\private-configuration\BACKEND.env"; DestDir: "{app}\BACKEND"; DestName: ".env"; Flags: ignoreversion
Source: "..\runtime\installer-inputs\private-configuration\profile.keys"; DestDir: "{app}\installer-cache\configuration"; Flags: ignoreversion
#else
Source: "..\runtime\installer-inputs\BACKEND.env.example"; DestDir: "{app}\BACKEND"; DestName: ".env"; Flags: onlyifdoesntexist
#endif
Source: "..\assets\reports\*"; DestDir: "{app}\assets\reports"; Flags: ignoreversion
Source: ".\dacte\*"; DestDir: "{app}\installer\dacte"; Flags: ignoreversion
Source: ".\crystal\*.ps1"; DestDir: "{app}\installer\crystal"; Flags: ignoreversion
Source: "..\docs\dacte-installer.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "..\DESKTOP\*"; DestDir: "{app}\DESKTOP"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "..\FRONTEND-HUB\dist-desktop\*"; DestDir: "{app}\FRONTEND-HUB\dist-desktop"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\FRONTEND-HUB\src-tauri\icons\icon.ico"; DestDir: "{app}"; DestName: "icon.desktop.ico"; Flags: ignoreversion
Source: "..\scripts\*"; DestDir: "{app}\scripts"; Flags: recursesubdirs createallsubdirs ignoreversion; Excludes: "__pycache__\*,*.pyc,*.pyo"
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\DESKTOP\README.md"; DestDir: "{app}\DESKTOP"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\icon.desktop.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\icon.desktop.ico"
Name: "{group}\Diagnostico DACTE"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\prepare-dacte.ps1"" -Repair -Assist"; WorkingDir: "{app}"

[Registry]
Root: HKCU; Subkey: "Software\AutomacaoNovelis"; ValueType: string; ValueName: "InstallRoot"; ValueData: "{app}"; Flags: uninsdeletekeyifempty
Root: HKCU; Subkey: "Software\AutomacaoNovelis"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"
Root: HKCU; Subkey: "Software\AutomacaoNovelis"; ValueType: string; ValueName: "ExePath"; ValueData: "{app}\{#MyAppExeName}"

[InstallDelete]
Type: files; Name: "{autodesktop}\Automação Novelis.lnk"
Type: files; Name: "{autodesktop}\Automacao Novelis.lnk"
Type: files; Name: "{group}\Automação Novelis.lnk"
Type: filesandordirs; Name: "{app}\BACKEND\.venv"
Type: filesandordirs; Name: "{app}\BACKEND\automacao_novelis_backend.egg-info"
Type: filesandordirs; Name: "{app}\runtime\python312"
Type: filesandordirs; Name: "{app}\installer-cache\wheels"
Type: files; Name: "{app}\installer-cache\python-3.12.10-amd64.exe"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ""{app}\scripts\setup\prepare-webview.ps1"""; WorkingDir: "{app}"; StatusMsg: "Verificando Microsoft WebView2..."; Flags: runhidden waituntilterminated; BeforeInstall: ResetWebViewPreparation; AfterInstall: VerifyWebViewPreparation
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""$p = '{app}\installer-cache\vc_redist.x64.exe'; if (Test-Path -LiteralPath $p) {{ & $p /install /quiet /norestart }}; exit 0"""; WorkingDir: "{app}"; StatusMsg: "Instalando runtime Visual C++..."; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "{code:BootstrapArguments}"; WorkingDir: "{app}"; StatusMsg: "Preparando Python local e validando a API do Cargo Hub..."; Flags: runhidden waituntilterminated; BeforeInstall: PrepareBackendInstallation; AfterInstall: VerifyBackendPreparation
Filename: "powershell.exe"; Parameters: "{code:DacteArguments}"; WorkingDir: "{app}"; StatusMsg: "Preparando e verificando DACTE e componentes x86..."; Flags: runhidden waituntilterminated; Check: BackendIsPrepared
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\install-desktop-service.ps1"" -SkipExecutableBuild -SkipShortcut"; WorkingDir: "{app}"; StatusMsg: "Preparando inicializacao do Cargo Hub nesta conta..."; Flags: runhidden waituntilterminated; Check: HubIsPrepared
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Description: "Abrir Novelis Cargo Hub"; Flags: nowait postinstall skipifsilent; Check: HubIsPrepared
Filename: "{app}\runtime\installation\dacte-diagnostic.html"; Description: "Ver diagnostico de instalacao DACTE"; Flags: shellexec postinstall skipifsilent; Check: DacteDiagnosticExists

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\remove-desktop-service.ps1"""; WorkingDir: "{app}"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveDesktopService"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\BACKEND\.venv"
Type: filesandordirs; Name: "{app}\runtime\python312"

[Code]
var
  OldInstallRoot: String;
  OldVersion: String;
  EnvBackupLines: TStringList;

#include "crystal\Prerequisite.iss"
#include "backend\Preparation.iss"
#include "backend\Hub.iss"
#include "backend\OperationalConfiguration.iss"
#include "branding\Theme.iss"

function BootstrapArguments(Param: String): String;
begin
  Result := '-NoProfile -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\scripts\bootstrap.ps1') + '" -SkipFrontend';
  if not WizardSilent then
    Result := Result + ' -InteractiveNetwork';
end;

function DacteArguments(Param: String): String;
begin
  Result := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\scripts\prepare-dacte.ps1') + '" -Repair -InputFile "' + ExpandConstant('{app}\runtime\dacte-installation-inputs.json') + '"';
  if WizardSilent then
    Result := Result + ' -Silent -NoElevation'
  else
    Result := Result + ' -Assist';
end;

function DacteDiagnosticExists: Boolean;
begin
  Result := BackendIsPrepared and
    FileExists(ExpandConstant('{app}\runtime\installation\dacte-diagnostic.html'));
end;

procedure SaveDacteInstallerInputs;
begin
  ForceDirectories(ExpandConstant('{app}\runtime'));
  SaveStringToFile(ExpandConstant('{app}\runtime\dacte-installation-inputs.json'), '{}', False);
end;

function NormalizePath(Value: String): String;
begin
  Result := Lowercase(Value);
  while (Length(Result) > 3) and (Copy(Result, Length(Result), 1) = '\') do
    Delete(Result, Length(Result), 1);
end;

function EnvFilePath(Dir: String): String;
begin
  Result := AddBackslash(Dir) + 'BACKEND\.env';
end;

{ Preserve local configuration before updating BACKEND. Only sanitized factory
  defaults are shipped; the user's values are restored locally after installation. }
procedure BackupExistingEnv(Dir: String);
var
  EnvPath: String;
begin
  if EnvBackupLines <> nil then
  begin
    EnvBackupLines.Free;
    EnvBackupLines := nil;
  end;
  EnvPath := EnvFilePath(Dir);
  if FileExists(EnvPath) then
  begin
    EnvBackupLines := TStringList.Create;
    EnvBackupLines.LoadFromFile(EnvPath);
  end;
end;

{ Inno Setup's Pascal Script TStringList has no Names[]/IndexOfName/Values-by-key
  support, so KEY=VALUE lines are parsed by hand below. }
function EnvLineKey(Line: String): String;
var
  EqPos: Integer;
begin
  Result := '';
  Line := Trim(Line);
  if (Line = '') or (Copy(Line, 1, 1) = '#') then
    Exit;
  EqPos := Pos('=', Line);
  if EqPos < 1 then
    Exit;
  Result := Trim(Copy(Line, 1, EqPos - 1));
end;

function EnvBackupValue(Key: String; var OldValue: String): Boolean;
var
  I, EqPos: Integer;
begin
  Result := False;
  OldValue := '';
  if EnvBackupLines = nil then
    Exit;
  for I := 0 to EnvBackupLines.Count - 1 do
  begin
    if EnvLineKey(EnvBackupLines[I]) = Key then
    begin
      EqPos := Pos('=', EnvBackupLines[I]);
      OldValue := Copy(EnvBackupLines[I], EqPos + 1, Length(EnvBackupLines[I]) - EqPos);
      Result := True;
      Exit;
    end;
  end;
end;

{ Keeps every key the user already had (their value wins), while letting brand-new
  keys introduced by this version keep the default shipped in the new .env. }
procedure MergeEnvAfterInstall(Dir: String);
var
  NewEnvPath: String;
  NewLines: TStringList;
  I, J: Integer;
  Key, OldValue: String;
begin
  if (EnvBackupLines = nil) or (EnvBackupLines.Count = 0) then
    Exit;
  NewEnvPath := EnvFilePath(Dir);
  if not FileExists(NewEnvPath) then
    Exit;
  NewLines := TStringList.Create;
  try
    NewLines.LoadFromFile(NewEnvPath);
    for I := 0 to NewLines.Count - 1 do
    begin
      Key := EnvLineKey(NewLines[I]);
      if (Key <> '') and not IsOperationalProfileKey(Key) and EnvBackupValue(Key, OldValue) then
        NewLines[I] := Key + '=' + OldValue;
    end;
    for I := 0 to EnvBackupLines.Count - 1 do
    begin
      Key := EnvLineKey(EnvBackupLines[I]);
      if Key <> '' then
      begin
        J := 0;
        while (J < NewLines.Count) and (EnvLineKey(NewLines[J]) <> Key) do
          J := J + 1;
        if J = NewLines.Count then
          NewLines.Add(EnvBackupLines[I]);
      end;
    end;
    NewLines.SaveToFile(NewEnvPath);
  finally
    NewLines.Free;
  end;
end;

function InstalledMarkerPath(Dir: String): String;
begin
  Result := AddBackslash(Dir) + '.automacao-novelis-install';
end;

function IsAutomacaoInstallDir(Dir: String): Boolean;
begin
  Result := (Dir <> '') and FileExists(InstalledMarkerPath(Dir));
end;

procedure RunPowerShell(Command: String);
var
  ResultCode: Integer;
begin
  Exec(
    'powershell.exe',
    '-NoProfile -ExecutionPolicy Bypass -Command "' + Command + '"',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

function StopInstallationProcesses(Dir: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  if not IsAutomacaoInstallDir(Dir) then Exit;
  ExtractTemporaryFile('stop-installed-stack.ps1');
  Result := Exec('powershell.exe',
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{tmp}\stop-installed-stack.ps1') + '" -InstallRoot "' + Dir + '"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := Result and (ResultCode = 0);
  Log('Owned Cargo Hub process shutdown completed: ' + IntToStr(ResultCode));
end;

procedure CleanCurrentInstallDir(Dir: String);
begin
  if not IsAutomacaoInstallDir(Dir) then
    Exit;
  DelTree(AddBackslash(Dir) + 'BACKEND', True, True, True);
  DelTree(AddBackslash(Dir) + 'DESKTOP', True, True, True);
  DelTree(AddBackslash(Dir) + 'FRONTEND', True, True, True);
  DelTree(AddBackslash(Dir) + 'FRONTEND-HUB', True, True, True);
  DelTree(AddBackslash(Dir) + 'scripts', True, True, True);
  DelTree(AddBackslash(Dir) + '_internal', True, True, True);
  DeleteFile(AddBackslash(Dir) + '{#MyAppExeName}');
  DeleteFile(AddBackslash(Dir) + 'AutomacaoNovelis.exe');
end;

procedure DeleteOldInstallIfMoved(NewDir: String);
begin
  if (OldInstallRoot = '') then
    Exit;
  if NormalizePath(OldInstallRoot) = NormalizePath(NewDir) then
    Exit;
  if IsAutomacaoInstallDir(OldInstallRoot) then
    DelTree(OldInstallRoot, True, True, True);
end;

procedure InitializeWizard;
var
  InfoPage: TWizardPage;
  InfoLabel: TNewStaticText;
  InfoText: String;
begin
  RegQueryStringValue(HKCU, 'Software\AutomacaoNovelis', 'InstallRoot', OldInstallRoot);
  RegQueryStringValue(HKCU, 'Software\AutomacaoNovelis', 'Version', OldVersion);

  InfoPage := CreateCustomPage(
    wpWelcome,
    'Instalação atual',
    'Confira a versão instalada antes de continuar.'
  );
  InfoLabel := TNewStaticText.Create(InfoPage);
  InfoLabel.Parent := InfoPage.Surface;
  InfoLabel.Left := 0;
  InfoLabel.Top := 0;
  InfoLabel.Width := InfoPage.SurfaceWidth;
  InfoLabel.WordWrap := True;
  if OldInstallRoot <> '' then
    InfoText := 'Versão instalada: ' + OldVersion + #13#10 +
      'Local atual: ' + OldInstallRoot + #13#10#13#10 +
      'O instalador vai encerrar a automação atual, atualizar os atalhos e remover a instalação antiga se o caminho mudar.'
  else
    InfoText := 'Nenhuma instalação anterior registrada.' + #13#10#13#10 +
      'Você poderá escolher o caminho da instalação na próxima tela.';
  InfoLabel.Caption := InfoText;
  #ifdef PrivateConfiguration
  InfoLabel.Caption := InfoLabel.Caption + #13#10#13#10 +
    'Pacote privado com configuracao operacional. Os valores predefinidos do ambiente serao aplicados; as demais configuracoes locais serao preservadas.';
  #endif
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  NewDir: String;
begin
  Result := '';
  NewDir := ExpandConstant('{app}');
  if not StopInstallationProcesses(NewDir) then
  begin
    Result := 'Nao foi possivel encerrar os processos desta instalacao. Feche o Cargo Hub e tente novamente.';
    Exit;
  end;
  if (OldInstallRoot <> '') and (NormalizePath(OldInstallRoot) <> NormalizePath(NewDir)) then
    if not StopInstallationProcesses(OldInstallRoot) then
    begin
      Result := 'Nao foi possivel encerrar a instalacao anterior do Cargo Hub.';
      Exit;
    end;
  Result := EnsureCrystalRuntime(NeedsRestart);
  if Result <> '' then Exit;
  BackupExistingEnv(NewDir);
  if (EnvBackupLines = nil) and (OldInstallRoot <> '') then
    BackupExistingEnv(OldInstallRoot);
  CleanCurrentInstallDir(NewDir);
  DeleteOldInstallIfMoved(NewDir);
  Result := '';
end;

#include "backend\Configuration.iss"
