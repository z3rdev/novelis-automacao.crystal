{ Native controls retain keyboard and accessibility support. }
<event('InitializeWizard')>
procedure InitializeCargoHubTheme;
begin
  WizardForm.Color := $00F9F6F3;
  WizardForm.MainPanel.Color := $0045250B;
  WizardForm.PageNameLabel.Font.Color := clWhite;
  WizardForm.PageNameLabel.Font.Style := [fsBold];
  WizardForm.PageDescriptionLabel.Font.Color := $00EFE5D2;
  WizardForm.WelcomeLabel1.Font.Color := $0045250B;
  WizardForm.WelcomeLabel1.Font.Size := 15;
  WizardForm.FinishedHeadingLabel.Font.Color := $0045250B;
  WizardForm.BeveledLabel.Caption := 'Cargo Hub  |  Z3ro.dev';
  WizardForm.BeveledLabel.Font.Color := $0080726B;
end;
