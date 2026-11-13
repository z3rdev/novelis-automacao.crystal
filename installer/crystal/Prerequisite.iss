{ Included from the existing installer. No proprietary files live in source control. }
procedure ExtractCrystalTools;
begin
  ExtractTemporaryFile('runtime-probe.ps1');
  ExtractTemporaryFile('inspect-runtime.ps1');
  ExtractTemporaryFile('install-crystal-runtime.ps1');
end;

function CrystalRuntimeFunctional: Boolean;
var
  ExitCode: Integer;
begin
  Result := Exec(ExpandConstant('{syswow64}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -NonInteractive -STA -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{tmp}\inspect-runtime.ps1') + '"', '', SW_HIDE, ewWaitUntilTerminated, ExitCode);
  Result := Result and (ExitCode = 0);
end;

function EnsureCrystalRuntime(var NeedsRestart: Boolean): String;
var
  ExitCode, LaunchError: Integer;
  Arguments, ResultPath: String;
  ExitText: AnsiString;
begin
  Result := '';
  ExtractCrystalTools;
  if CrystalRuntimeFunctional then
    Exit;
  ExtractTemporaryFile('NovelisCrystalRDC-x86-1.0.1.msi');
  ExtractTemporaryFile('crystal-runtime.manifest.json');
  ResultPath := ExpandConstant('{tmp}\crystal-install-result.json');
  Arguments := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' +
    ExpandConstant('{tmp}\install-crystal-runtime.ps1') + '" -ManifestPath "' +
    ExpandConstant('{tmp}\crystal-runtime.manifest.json') + '" -ProbeDirectory "' +
    ExpandConstant('{tmp}') + '" -ResultPath "' + ResultPath + '"';
  #ifdef CrystalDevelopment
  Arguments := Arguments + ' -AllowDevelopment';
  #endif
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    Arguments, '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
  begin
    Result := 'Nao foi possivel iniciar o pre-requisito Crystal.';
    Exit;
  end;
  if ExitCode = 740 then
  begin
    if WizardSilent then
    begin
      Result := 'O runtime Crystal requer uma etapa administrativa. Execute a implantacao elevada.';
      Exit;
    end;
    if not ShellExec('runas', ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      Arguments, '', SW_HIDE, ewWaitUntilTerminated, LaunchError) then
    begin
      Result := 'A elevacao do pre-requisito Crystal nao foi concluida.';
      Exit;
    end;
    if not LoadStringFromFile(ResultPath + '.exitcode', ExitText) then
    begin
      Result := 'O pre-requisito Crystal nao informou o resultado da instalacao.';
      Exit;
    end;
    ExitCode := StrToIntDef(Trim(ExitText), 2);
  end;
  { Preserve a sanitized installation event report; it never contains PIDKEY. }
  ForceDirectories(ExpandConstant('{app}\runtime\installation'));
  FileCopy(ResultPath, ExpandConstant('{app}\runtime\installation\crystal-install-result.json'), False);
  if (ExitCode = 3010) or (ExitCode = 1641) then
  begin
    NeedsRestart := True;
    Result := 'Reinicie o Windows para concluir o pre-requisito Crystal e execute o setup novamente.';
  end
  else if (ExitCode <> 0) or not CrystalRuntimeFunctional then
    Result := 'O runtime Crystal nao passou na verificacao funcional x86. Codigo: ' + IntToStr(ExitCode);
end;

procedure SetCrystalProgId;
var
  Lines: TStringList;
  I: Integer;
  Found: Boolean;
  Path: String;
begin
  Path := ExpandConstant('{app}\BACKEND\.env');
  if not FileExists(Path) then Exit;
  Lines := TStringList.Create;
  try
    Lines.LoadFromFile(Path);
    Found := False;
    for I := 0 to Lines.Count - 1 do
      if Pos('CRYSTAL_REPORTS_PROGID=', Trim(Lines[I])) = 1 then
      begin
        Lines[I] := 'CRYSTAL_REPORTS_PROGID=CrystalDesignRunTime.Application.11';
        Found := True;
      end;
    if not Found then Lines.Add('CRYSTAL_REPORTS_PROGID=CrystalDesignRunTime.Application.11');
    Lines.SaveToFile(Path);
  finally
    Lines.Free;
  end;
end;
