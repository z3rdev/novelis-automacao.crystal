# Revisão r3 privada: configuração operacional preenchida

O diagnóstico posterior da consulta SQL e os ajustes da revisão r4 estão em
[Revisão r4 e consulta SQL](instalador-cargo-hub-r4-consulta.md).

[Instalador r3 privado](../runtime/private-installer/NovelisCargoHubSetup-0.1.34-r3-PRIVADO-TESTE-NaoDistribuir.exe)
gerado em 12/11/2026: 741.409.380 bytes. SHA-256:
`af2692307d16b275b35adfc695a3b8b1ed2881bd7c91c218e3620d0b4fe2695e`.
O [manifesto](../runtime/private-installer/NovelisCargoHubSetup-0.1.34-r3-PRIVADO-TESTE-NaoDistribuir.manifest.json)
registra o perfil privado sem incluir seus valores. A integridade do EXE e a
restrição de acesso foram conferidas. O arquivo não foi copiado para a pasta
compartilhada.

Esta revisão atende à solicitação de enviar o `.env` com os dados do ambiente.
O arquivo recebido, `- Copia.env`, continha campos de servidor SQL, usuários e
senhas vazios. Eles vinham do modelo sanitizado usado nos pacotes anteriores.

O pacote privado usa os valores já preenchidos no `BACKEND/.env` de
desenvolvimento e completa as opções novas com os padrões atuais. Os valores
não foram exibidos nos relatórios, gravados no código-fonte nem adicionados ao
repositório. O relatório de conferência contém apenas estados e contagens.

## O que é instalado

O arquivo ativo é **`BACKEND\.env`**. O arquivo `.env.example` continua sendo
um modelo sem credenciais.

O perfil contém 254 variáveis autoritativas: os valores preenchidos da origem
e os ajustes de execução do aplicativo. Na atualização, essas variáveis recebem
os valores do pacote, corrigindo também os campos vazios ou antigos deixados
pelas instalações anteriores. Configurações locais que não fazem parte do
perfil são preservadas.

A configuração é aplicada antes de iniciar o bootstrap, mantendo a correção
de ordem da r2. O `.env` instalado recebe ACL restrita à conta da instalação,
SYSTEM e Administradores. A configuração privada de build e o EXE ficam em
diretórios locais protegidos; não são publicados automaticamente.

O pacote contém dados de acesso e deve permanecer restrito ao teste autorizado.
Proteção de arquivo por ACL não representa criptografia do conteúdo do EXE.

Chaves de licença, como PIDKEY, serial e registro Crystal, são recusadas no
perfil operacional. O MSI Crystal 1.0.1 e o executável Tauri 0.1.34 permanecem
os mesmos da entrega anterior.

## Conferências realizadas

- Os valores ativos de SQL, portais e SQLite foram comparados com a origem,
  sem registrar seu conteúdo: `runtime/crystal-tests/hub-r3-configuration-checks.json`.
- A configuração resultante do Crystal está completa. Como
  `CRYSTAL_DB_USE_CONSULTA=true`, ele utiliza os valores de `CONSULTA_DB_*`.
  Campos específicos `CRYSTAL_DB_*` vazios são opcionais nesse modo.
- 69 testes passaram em `runtime/crystal-tests/hub-r3-validation.log`.
- Um instalador Inno sintético comprovou que os valores privados substituem
  campos vazios e antigos, preservam uma opção local fora do perfil e protegem
  o `.env` antes da execução seguinte.
- O build geral continua usando padrões sanitizados quando nenhum perfil
  operacional é informado.

Os testes de mesclagem e permissões usaram credenciais fictícias. A conferência
do perfil real apenas comparou valores em memória. Não foram executados SQL,
logins nos portais nem geração DACTE com os dados reais durante essa etapa.

## Build controlado

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-installer.ps1 `
  -BuildMode development -InstallerRevision r3 `
  -OperationalEnvPath .\BACKEND\.env `
  -CrystalManifest .\runtime\crystal-build\development\NovelisCrystalRDC-x86-1.0.1.manifest.json
```

O resultado fica em `runtime\private-installer`, com `PRIVADO` no nome.
As permissões são restringidas antes de gravar a configuração de build e antes
de compilar o EXE. O manifesto informa a presença do perfil privado, sem
registrar valores ou hashes individuais de credenciais.

## Instalação no PC de teste

Execute o instalador r3 privado na mesma pasta da instalação atual. Confira os
dados no arquivo ativo `BACKEND\.env` após o término. A verificação da API
ocorre com esse arquivo já preenchido.

Continuam pendentes a conclusão da instalação no PC físico, o acesso SQL real,
os logins, o DACTE/PDF, a decodificação dos códigos e as aprovações de licença
e procedência. O pacote é de teste e não está liberado para produção.

## Resultado recebido do PC físico

Na tentativa de 12/11/2026 às 16:46, Python, `.venv`, pacotes e Chromium passaram.
A inicialização do banco operacional falhou com **WinError 1326** ao consultar
`\\192.168.254.250\rede\Publico\novelis-automacao`: o servidor recusou a
autenticação Windows da conta `NB-GFR-VIN-05\user`.

Essa autenticação SMB é separada das credenciais SQL e de portais do perfil.
A conta que executa o backend precisa abrir esse compartilhamento autenticada
e ter leitura/gravação no SQLite e nos arquivos auxiliares da mesma pasta.
Após regularizar esse acesso no PC de teste, execute a mesma r3 para repetir a
verificação. Não foi gerado outro instalador para essa falha de autenticação.

Evidências: `runtime/crystal-tests/physical-pc-20261112/r3-install-failure/20261112T164656/`.
