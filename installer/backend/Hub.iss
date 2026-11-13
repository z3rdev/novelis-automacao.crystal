var
  WebViewPrepared: Boolean;

procedure ResetWebViewPreparation;
begin
  WebViewPrepared := False;
  DeleteFile(ExpandConstant('{app}\runtime\webview2-result.exitcode'));
end;

procedure VerifyWebViewPreparation;
var
  Text: AnsiString;
begin
  WebViewPrepared := LoadStringFromFile(ExpandConstant('{app}\runtime\webview2-result.exitcode'), Text);
  if WebViewPrepared then WebViewPrepared := Trim(String(Text)) = '0';
  if not WebViewPrepared then
    Log('WebView2 verification failed. See runtime\webview2-result.json.');
end;

function HubIsPrepared: Boolean;
begin
  Result := BackendIsPrepared and WebViewPrepared;
end;

<event('GetCustomSetupExitCode')>
function HubSetupExitCode: Integer;
begin
  Result := 0;
  if not WebViewPrepared then Result := 21;
end;

<event('CurPageChanged')>
procedure HubFinishedPage(CurPageID: Integer);
begin
  if (CurPageID = wpFinished) and not WebViewPrepared then
  begin
    WizardForm.FinishedHeadingLabel.Caption := 'Instalacao incompleta';
    WizardForm.FinishedLabel.Caption := 'O Microsoft WebView2 nao ficou disponivel. ' +
      'Consulte runtime\webview2-result.json na pasta instalada. O Cargo Hub nao sera aberto.';
  end;
end;

procedure SetHubDatabaseDefault;
var
  Lines: TStringList;
  Path, Line: String;
  I, Eq: Integer;
  Found: Boolean;
begin
  Path := ExpandConstant('{app}\BACKEND\.env');
  Lines := TStringList.Create;
  try
    Lines.LoadFromFile(Path);
    Found := False;
    for I := 0 to Lines.Count - 1 do
    begin
      Line := Trim(Lines[I]);
      Eq := Pos('=', Line);
      if (Eq > 0) and (Trim(Copy(Line, 1, Eq - 1)) = 'NOVELIS_SQLITE_PATH') then
      begin
        Found := True;
        Line := Trim(Copy(Line, Eq + 1, Length(Line)));
        if (Line = '') or (Line = '""') or (Line = '''''') then
          Lines[I] := 'NOVELIS_SQLITE_PATH=\\192.168.254.250\rede\Publico\novelis-automacao\novelischamado.sqlite';
      end;
    end;
    if not Found then
      Lines.Add('NOVELIS_SQLITE_PATH=\\192.168.254.250\rede\Publico\novelis-automacao\novelischamado.sqlite');
    Lines.SaveToFile(Path);
  finally
    Lines.Free;
  end;
end;
