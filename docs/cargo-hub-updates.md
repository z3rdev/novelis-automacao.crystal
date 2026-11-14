# Configuração de desenvolvedor e atualizações

## Modo desenvolvedor

O painel Desenvolvedor aparece em Configurações e diagnóstico quando os dois arquivos locais existem na pasta BACKEND da cópia em execução.

- `credentials.json` contém o perfil S3 já fornecido, com `url`, `accessKey`, `secretKey`, `api` e `path`.
- `CONFIG.dev` contém `DEVMODE=1`. O valor `0` desativa o painel.

O caminho acompanha a instalação ou checkout. Neste checkout, a pasta é `E:\PROJETOS\AUTOMAÇÃO NOVELIS\BACKEND`.

O backend reavalia a presença dos arquivos em cada acesso. A tela atualiza essa identificação a cada 15 segundos. A API exige uma sessão de operador ativa para testar a conexão autenticada. O teste lista até 20 objetos do prefixo e consulta a existência do manifesto.

As credenciais permanecem no backend. Ambos os arquivos estão no `.gitignore`. O Inno Setup inclui os arquivos da aplicação por seleção explícita e mantém esses dois arquivos fora do pacote.

O SDK Boto3 integra as dependências do backend e o próximo instalador. O build completa o cache offline quando as dependências do projeto mudam. Para atualizar um checkout de desenvolvimento, instale as dependências do projeto.

```powershell
& '.\BACKEND\.venv\Scripts\python.exe' -m pip install -e '.\BACKEND[dev]'
```

## Servidor

O console de administração indicado pelo usuário é `https://minio.nexusnerds.com.br/browser/z3-releases/cargo-hub`.

O perfil S3 local identifica o endpoint `https://s3.nexusnerds.com.br`. O aplicativo consulta o bucket `z3-releases` e o prefixo `cargo-hub/`.

O manifesto fica em `https://s3.nexusnerds.com.br/z3-releases/cargo-hub/latest.json`. O campo opcional `object_key` identifica o pacote por SHA-256 em `packages/<sha256>/<arquivo.exe>`. Manifestos anteriores com apenas `file` continuam aceitos.

Com o modo desenvolvedor ativo, as consultas e downloads usam autenticação S3 com o perfil local do backend. O erro HTTP 403 da consulta anônima foi corrigido para esse modo. Computadores sem o perfil de desenvolvimento continuam usando HTTPS para leitura pública e precisam da permissão de leitura definida pelo administrador para esses objetos. As credenciais de publicação permanecem no computador do desenvolvedor.

A política fornecida para o bucket libera apenas `danfe-workspace/*`. A proposta
em [`config/minio/z3-releases-public-read.policy.json`](../config/minio/z3-releases-public-read.policy.json)
mantém essa regra e acrescenta `s3:GetObject` para `cargo-hub/latest.json`,
`cargo-hub/packages/*` e `cargo-hub/notifications/feed.json`. Os clientes usam
esses endereços para consultar atualizações, baixar pacotes aprovados e ler
avisos. Publicação, remoção, listagem do bucket, registros internos e diagnósticos
continuam sujeitos às permissões autenticadas.

Para aplicar, o administrador deve abrir o bucket `z3-releases` no console
MinIO, editar a política personalizada e usar o JSON completo da proposta.
Confira outras regras eventualmente existentes antes de substituir a política.
Leitura pública permite que qualquer pessoa com o endereço leia esses objetos.
A proposta não foi aplicada automaticamente. A verificação de 13/11/2026
retornou HTTP 403 nas leituras anônimas do manifesto e do catálogo de avisos.
Após a alteração, o catálogo existente deve responder HTTP 200. O manifesto
responderá HTTP 200 quando uma release autorizada estiver publicada.
O escopo dos objetos em `Resource` segue a
[documentação oficial de permissões S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-policy-language-overview.html).

Em 13/11/2026, a consulta autenticada retornou o estado `not_published`, pois o manifesto de produto está ausente. O teste real de publicação utilizou pacotes sintéticos e um prefixo temporário em `_diagnostics`, validou duas publicações e um download autenticado e removeu os objetos criados. Os resultados estão em `runtime/ui-review/publish-authenticated-probe.json` e `runtime/ui-review/publish-real-end-to-end.json`.

## Publicar pelo aplicativo

1. Entre no Cargo Hub e abra Configurações e diagnóstico.
2. No painel Desenvolvedor, selecione o instalador `.exe`. O aplicativo identifica a versão pelo nome do pacote.
3. Confira a versão, informe as notas e confirme a autorização de distribuição.
4. Clique em Publicar atualização e acompanhe o progresso até a confirmação.

O backend prepara uma cópia local estável, calcula SHA-256 e valida a estrutura executável, o nome, a versão e o inventário de distribuição disponível. Pacotes identificados como privados, de teste, com configuração operacional privada ou aprovação pendente recebem uma mensagem de bloqueio compatível com as restrições de distribuição já definidas para o projeto.

O pacote é enviado por HTTPS e conferido no servidor antes da publicação dos metadados. Cada pacote usa um caminho associado ao seu hash. O catálogo `releases/<versão>/<sha256>.json` permite reconciliar `latest.json` com a versão mais recente quando ocorrem publicações simultâneas. Conflitos entre pacotes diferentes da mesma versão exigem uma versão nova.

O servidor atual aceitou uma escrita com `If-Match` desatualizado durante a verificação isolada. A publicação utiliza a conferência posterior do catálogo para lidar com esse comportamento. O teste real confirmou a recuperação de um ponteiro de versão desatualizado. Os testes de gravação usaram exclusivamente objetos temporários isolados.

O painel exige os dois arquivos de desenvolvimento e uma sessão ativa. O backend verifica novamente o modo antes da publicação dos metadados. A API exige a confirmação explícita de distribuição do pacote selecionado.

## Preparar uma release

O build Inno existente gera `installed-release.json` com a versão e revisão, como `0.1.34-r9`. Essa identificação permite comparar revisões que compartilham a mesma versão base.

Prepare um manifesto para um instalador já gerado, usando o nome real do arquivo, a versão correspondente e um arquivo UTF-8 com as notas.

```powershell
& '.\BACKEND\.venv\Scripts\python.exe' '.\scripts\prepare-hub-release.py' `
  --installer 'C:\Releases\NovelisCargoHubSetup-0.1.35.exe' `
  --version '0.1.35' `
  --notes-file 'C:\Releases\notas.txt' `
  --output '.\runtime\release\latest.json'
```

O manifesto contém `schema_version`, `version`, `title`, `notes`, `published_at`, `file`, `sha256`, `size`, `architecture` e o campo opcional `object_key`. O script calcula tamanho e SHA-256 a partir do instalador. As versões aceitas seguem `major.minor.patch` e a revisão opcional `-rN`.

Após a aprovação de distribuição aplicável ao pacote, publique primeiro o instalador completo no prefixo e depois substitua `latest.json`. Preserve a imutabilidade do nome de cada instalador publicado. O manifesto aponta para um arquivo já disponível.

Os pacotes privados de teste existentes contêm componentes Crystal e configuração operacional. Sua publicação continua sujeita às restrições de licenciamento e procedência já estabelecidas para o projeto.

## Modal e instalação

O aplicativo consulta o servidor dois segundos após entrar na sessão e a cada cinco minutos. Uma versão superior abre o modal uma vez por sessão. O botão Atualizações permite consultar e reabrir o modal manualmente.

O operador inicia o download. O backend mostra os bytes recebidos, valida o tamanho, SHA-256 e o cabeçalho executável Windows e só então disponibiliza a instalação. Downloads incompletos são removidos, e uma nova tentativa pode ser iniciada pela consulta. O pacote completo pode ser reutilizado após reiniciar o backend mediante nova validação.

A instalação exige uma sessão de operador ativa, a cópia instalada identificada pelo marcador `.automacao-novelis-install` e a automação encerrada. O backend verifica novamente o arquivo antes de abrir o assistente Inno com `/DIR`, `/CLOSEAPPLICATIONS` e `/NORESTART`. O assistente conserva o tratamento de elevação e preparação do ambiente existente.

Os testes automatizados usam transporte HTTP local de teste e um arquivo de teste com hash conhecido. A instalação real de uma atualização em máquina limpa permanece pendente de uma release autorizada disponível no servidor.

## Referências

- [Endpoints oficiais MinIO](https://docs.min.io/aistor/reference/aistor-server/http-endpoints/)
- [SDK S3 Boto3](https://docs.aws.amazon.com/boto3/latest/reference/services/s3.html)
- [Compatibilidade S3 MinIO](https://docs.min.io/aistor/developers/s3-api-compatibility/)
- [Parâmetros oficiais Inno Setup](https://jrsoftware.org/ishelp/topic_setupcmdline.htm)
