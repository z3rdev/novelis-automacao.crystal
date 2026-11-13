{ Verify the bootstrap's fresh completion marker before starting dependent steps. }
var
  BackendPrepared: Boolean;
  BackendPreparationFailed: Boolean;

procedure ResetBackendPreparation;
begin
  BackendPrepared := False;
  BackendPreparationFailed := True;
  DeleteFile(ExpandConstant('{app}\runtime\bootstrap-result.json.exitcode'));
end;

procedure VerifyBackendPreparation;
var
  ExitText: AnsiString;
begin
  BackendPrepared :=
    LoadStringFromFile(ExpandConstant('{app}\runtime\bootstrap-result.json.exitcode'), ExitText);
  if BackendPrepared then
    BackendPrepared := (Trim(String(ExitText)) = '0') and
      FileExists(ExpandConstant('{app}\BACKEND\.venv\Scripts\python.exe'));
  BackendPreparationFailed := not BackendPrepared;
  if BackendPreparationFailed then
  begin
    Log('Backend preparation failed. Application launch and service configuration skipped.');
    if not WizardSilent then
      SuppressibleMsgBox('A preparacao do backend falhou. A aplicacao nao sera iniciada.' + #13#10 +
        'Consulte ' + ExpandConstant('{app}\runtime\bootstrap.log') + #13#10 +
        'e bootstrap-result.json na mesma pasta.', mbError, MB_OK, IDOK);
  end;
end;

function BackendIsPrepared: Boolean;
begin
  Result := BackendPrepared and not BackendPreparationFailed;
end;

<event('GetCustomSetupExitCode')>
function BackendSetupExitCode: Integer;
begin
  Result := 0;
  if BackendPreparationFailed then Result := 20;
end;

<event('CurPageChanged')>
procedure BackendFinishedPage(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and BackendPreparationFailed then
  begin
    WizardForm.FinishedHeadingLabel.Caption := 'Instalacao incompleta';
    WizardForm.FinishedLabel.Caption :=
      'Os arquivos foram copiados, mas a preparacao do backend falhou. ' +
      'Consulte runtime\bootstrap.log e runtime\bootstrap-result.json na pasta instalada. ' +
      'O aplicativo e o servico nao foram iniciados pelo instalador.';
  end;
end;
