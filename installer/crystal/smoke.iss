; Compile-only harness for the actual prerequisite include; never execute this setup.
[Setup]
AppName=Novelis Crystal prerequisite compile check
AppVersion=1.0.1
DefaultDirName={localappdata}\NovelisCrystalCompileCheck
PrivilegesRequired=lowest
OutputDir=..\..\runtime\crystal-build\development\compile-only
OutputBaseFilename=compile-check-do-not-install
Compression=none
Uninstallable=no
[Files]
Source: "runtime-probe.ps1"; Flags: dontcopy
Source: "inspect-runtime.ps1"; Flags: dontcopy
Source: "..\..\scripts\install-crystal-runtime.ps1"; Flags: dontcopy
Source: "..\..\runtime\installer-inputs\crystal\NovelisCrystalRDC-x86-1.0.1.msi"; Flags: dontcopy
Source: "..\..\runtime\installer-inputs\crystal\crystal-runtime.manifest.json"; Flags: dontcopy
[Code]
#include "Prerequisite.iss"
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := EnsureCrystalRuntime(NeedsRestart);
end;
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then SetCrystalProgId;
end;
