{ The private profile explicitly supplies authoritative values; never log them. }
function IsOperationalProfileKey(Key: String): Boolean;
var
  Lines: TStringList;
  Path: String;
begin
  Result := False;
  #ifdef PrivateConfiguration
  Path := ExpandConstant('{app}\installer-cache\configuration\profile.keys');
  if not FileExists(Path) then
    RaiseException('Lista do perfil operacional ausente.');
  Lines := TStringList.Create;
  try
    Lines.LoadFromFile(Path);
    Result := Lines.IndexOf(Key) >= 0;
  finally
    Lines.Free;
  end;
  #endif
end;

procedure ProtectOperationalConfiguration;
var
  ExitCode: Integer;
begin
  #ifdef PrivateConfiguration
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{app}\scripts\setup\protect-operational-env.ps1') + '"', '',
    SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
    RaiseException('Nao foi possivel proteger a configuracao operacional.');
  #endif
end;
