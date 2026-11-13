{ All application configuration must be ready before [Run] launches Python. }
procedure PrepareBackendInstallation;
begin
  ResetBackendPreparation;
  MergeEnvAfterInstall(ExpandConstant('{app}'));
  SetCrystalProgId;
  SetHubDatabaseDefault;
  SaveDacteInstallerInputs;
  #ifdef PrivateConfiguration
  ProtectOperationalConfiguration;
  #endif
end;
