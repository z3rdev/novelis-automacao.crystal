# Prévia para revisão — 14/11/2026

Esta etapa modifica o código e executa a janela Tauri em desenvolvimento. Não gera nem publica instalador ou release. O instalador privado criado anteriormente não contém estas alterações.

A revisão seguinte adicionou **Tarifas e tonelagem**, com catálogo real e cálculo. Veja [o diagnóstico e as evidências dessa funcionalidade](tarifas-tonelagem.md). A suíte atual completa passou com 443 testes backend e 48 frontend, além de 4 testes backend ignorados.

## O que conferir

1. **Entrada:** identificação Windows pela janela nativa; tentativas automáticas de conexão, com indicação de progresso e sem botão obrigatório de repetição.
2. **Período personalizado:** rótulos acima dos campos; controles com altura uniforme; De e Até permanecem juntos, inclusive no painel de execução estreito. Ações quebram para outra linha quando necessário.
3. **Chamados Novelis:** clique na linha ou pressione Enter/Espaço para abrir o painel lateral. Detalhes, responsável, status original, datas, percurso, número e chave vêm do catálogo. Informações ausentes são indicadas. O botão externo usa a rota de chamado configurada no backend.
4. **Senha mestre:** tela exclusiva em Desenvolvimento → Senha mestre para cadastrar e alterar a senha no banco compartilhado. A tela de configurações permite apenas desbloqueio. Conteúdo e diagnósticos ficam protegidos também na API.
5. **Notificações:** botão do cabeçalho abre uma página com lista, leitura, busca e filtros. A marcação de leitura é explícita. Avisos novos continuam abrindo automaticamente fora dessa página.
6. **Ajuda:** guias por assunto, progresso da visita, busca, perguntas frequentes e um laboratório fictício de documentos que não inicia automações.
7. **Janela nativa:** Ctrl+P e Ctrl+Shift+P são interceptados. O bloqueio não afeta o navegador comum.
8. **Fila de abertura:** a carga inicial usa os últimos **2 dias**, conforme definido pelo usuário. CT-es encontrados permanecem no banco compartilhado até existir chamado; uma consulta menor ou um lote manual de PDF/XML não substitui a fila.
9. **Visual:** Notificações e Usuários e dispositivos sem os banners. Dispositivos abrem detalhes pela lateral. O monitor apresenta uma lista de atividades com busca, filtros, pausa e detalhes laterais, em vez da tabela técnica de logs.
10. **Chamados:** o indicador se chama **Em análise** e conta os chamados nesse andamento.

## Senha única

- A política fica no SQLite operacional compartilhado configurado em `NOVELIS_SQLITE_PATH`, em `hub_master_policy`. Não depende de copiar uma senha para cada instalação.
- Somente hash PBKDF2-HMAC-SHA256, salt aleatório e metadados são persistidos; nenhuma senha foi predefinida ou incluída em código, logs ou relatórios.
- Cadastro e alteração exigem modo desenvolvedor (`CONFIG.dev` e `credentials.json` locais), inclusive na API. A tela fica fora do bloqueio das configurações para permitir a gestão da senha. Cada alteração troca o salt/hash e a revisão da política, invalidando os desbloqueios anteriores em todos os backends. A gestão não desbloqueia configurações automaticamente.
- Cada sessão de operador precisa desbloquear as configurações. A autorização local expira em 15 minutos e pode ser encerrada em **Bloquear acesso**. A sessão encerrada não pode reutilizá-la.
- Após cinco erros, novas tentativas daquela identidade/dispositivo aguardam um minuto. O contador é compartilhado entre processos.
- Banco compartilhado indisponível mantém o acesso bloqueado, com resposta 503. Não existe senha de emergência embutida.
- O cadastro da senha real deve ser feito pelo responsável dentro do app. Os testes usam apenas bancos temporários e senhas fictícias.

## Executar a prévia

```powershell
Set-Location -LiteralPath 'E:\PROJETOS\AUTOMAÇÃO NOVELIS'
& '.\scripts\start-hub-preview.ps1'
```

O script usa backend separado em `127.0.0.1:18036`, Vite em `127.0.0.1:1420` e identificador Tauri de prévia. Não encerra a aplicação instalada. Requer o Python de desenvolvimento, Node, Rust MSVC e ferramentas C++ já preparadas neste PC. Executa `tauri dev`, sem empacotamento.

O backend da prévia usa o modo de verificação de prontidão para não iniciar agendamentos, recuperação de execuções, limpeza de documentos ou presença em segundo plano. A interface usa as configurações privadas e fontes de dados existentes. Não iniciar fluxos reais durante uma revisão apenas visual.

Para alterações somente Python/React, sem mudanças nativas, `scripts/start-hub-preview-fast.ps1` reutiliza o executável de desenvolvimento existente e abre os mesmos serviços. Recusa a reutilização quando os fontes nativos estiverem mais novos. Não recompila o executável nem gera instalador. Encerrar a execução anterior antes de iniciar outra prévia.

## Verificações executadas

- Backend completo atualizado: **435 aprovados, 4 ignorados**, incluindo fila persistente e conferência de documentos. O conjunto direcionado anterior de acesso e detalhes resultou em **21 aprovados**.
- Frontend atualizado: **46 aprovados**, incluindo reconexão automática sem clique, identidade nativa independente, bloqueio de montagem do conteúdo protegido, cadastro/alteração da senha na tela de desenvolvedor, leitura de notificações, atalhos de impressão e lista de atividades.
- TypeScript: `tsc --noEmit`.
- UI no servidor Vite de desenvolvimento, com respostas de teste identificadas como fictícias: larguras 1920, 1280, 1024 e ajuda a 800 px; alturas dos controles, ausência de transbordamento, painel lateral por teclado, página de notificações, leitura explícita e laboratório de documentos. Sem erros JavaScript.
- PostgreSQL real, somente leitura: catálogo de **11.071** registros, recuperação de detalhe, status original e chave de 44 dígitos. Nenhuma alteração de chamados foi executada.
- Janela Tauri de desenvolvimento aberta e observada conectada no PC. A verificação de Ctrl+P por teclado nativo foi adiada ao detectar interação do usuário na janela; o bloqueio passou no teste automatizado de eventos.

Evidências locais em `runtime/dev-preview/`: `backend-tests.log`, `access-details-tests.log`, `frontend-v2-tests.log`, `typecheck-v2.log`, `ui-validation-v2.json`, `chamado-real-read.json` e capturas das telas. O teste de UI usa fixtures; não representa consulta fiscal nem abertura real de chamado.

## Pendências da revisão

- Responsável cadastrar a senha mestre real na interface.
- Conferir a navegação autenticada do link de um chamado no portal Novelis. A rota é a mesma reconhecida pelo fluxo existente; a abertura autenticada não foi executada pelo teste de UI.
- Aprovação visual do usuário antes de qualquer novo instalador/release.
- Homologação do próximo pacote em instalação limpa e atualização continua necessária após autorização de empacotamento.

## Fila persistente e revisão das telas

- A fila fica em `hub_pending_ctes`, no SQLite operacional compartilhado. A identidade usa a chave de acesso; quando ausente, o identificador completo filial/série/número. Registros de chamados abertos são conferidos por consulta indexada ao PostgreSQL e pelo histórico de criação bem-sucedida. Uma indisponibilidade de consulta é informada como erro, sem apresentar confirmação falsa.
- A migração aceita planos confirmados pelo filtro Novelis e conserva os itens já encontrados. O fluxo registra a fila mesmo com a interface fechada. Planos manuais novos e consultas SQL ainda não confirmadas não entram como fila de abertura.
- A inicialização real autorizada foi executada com `scripts/initialize-pending-queue.py --days 2 --apply`: **20 CT-es sem chamado**, sendo 11 com emissão em 13/11 e 9 em 14/11. Nenhum chamado foi aberto por esse procedimento. O comando exige relatório Novelis compartilhado recente e não imprime credenciais.
- A API real `/api/hub/ctes` retornou HTTP 200 nas duas verificações, com os mesmos 20 itens, **17 PDFs e 17 XMLs** reconhecidos. Os tempos medidos com a janela conectada foram **23,047 s e 23,453 s**. O acesso ao compartilhamento ainda influencia a latência; não é uma medição de instalação limpa.
- A conferência agora lista cada pasta uma vez por consulta e usa até seis leituras paralelas. O índice é descartado após a consulta, para detectar criação e exclusão na próxima verificação. O XML continua validado por conteúdo, chave, série e número; PDFs mantêm identificação completa e assinatura de arquivo. Não foram alterados documentos reais.
- Testes direcionados da fila/documentos/API: **47 aprovados**. Cobrem preservação entre dias/computadores, fechamento apenas quando há chamado, reutilização de número com chave diferente, lote manual, criação/exclusão de arquivos, chave XML incorreta e caminhos atuais/legados de PDF.
- Frontend atualizado: **46 testes aprovados**, TypeScript sem erros. UI v3 verificada no Vite com dados fictícios, incluindo as telas sem banner, fila de dias diferentes, painéis laterais e lista de eventos. As capturas são exemplos de teste, não sessões reais publicadas.

Evidências adicionais em `runtime/dev-preview/`: `queue-initialization.json`, `queue-real-api.json`, `queue-final-tests.log`, `backend-final-tests.log`, `frontend-v3-tests.log`, `typecheck-v3.log`, `ui-validation-v3.json`, `usuarios-v3.png`, `usuario-lateral-v3.png`, `atividade-v3.png` e `evento-lateral-v3.png`. Os arquivos locais de execução não são conteúdo de distribuição.

**O instalador anterior não foi reconstruído.** Esta revisão continua pendente de aprovação visual antes do empacotamento.

## Ajustes após a revisão visual

- Novo lote ocupa uma área maior. Em 1920, 1280 e 1024 px, período, De e Até ficam na mesma linha, com controles de 36 px. Em larguras menores o painel se reorganiza.
- Logo e cabeçalho têm altura de 48 px; alinhamento conferido com menu aberto e recolhido.
- Removidos os parágrafos auxiliares destacados de inicialização, desenvolvedor, mensagens e documentos. Variáveis de mensagem ficam em uma seção expansível.
- Removida a opção XML arquivado. A ação desta tela envia sempre `crystal`; o download de XML continua nos seus fluxos próprios.
- Gestão da senha: **22 testes direcionados aprovados** no backend, incluindo rotação e revogação entre backends. A revisão visual usa senhas fictícias e não altera a política real.

## Seleção do certificado

A solicitação informada pelo usuário é a lista de escolha do certificado. É diferente de autorização de chave privada ou PIN.

O projeto já resolve o certificado do usuário Windows por CNPJ ou thumbprint em `sefaz_certificate.py`, e prepara um perfil Chromium isolado em `sefaz_browser_profile.py`, com regra limitada a `https://[*.]cte.fazenda.gov.br` e filtros de titular/emissor. A verificação executada nesta etapa encontrou o certificado configurado e confirmou a regra carregada no navegador em execução (`chrome://prefs-internals`). Nenhuma chave privada foi exportada e nenhuma política global do Windows foi alterada.

Isso valida a preparação da seleção, **não comprova uma autenticação TLS real nem que a lista deixou de aparecer no PC de teste**. Essa confirmação depende de uma nova consulta autorizada naquela máquina. O evento do fluxo foi corrigido para informar que o certificado foi preparado, sem anunciar seleção concluída antes da autenticação.

Evidências: `certificate-config-check.json` e `certificate-browser-check.json` em `runtime/dev-preview/`.

Fontes oficiais:

- [Microsoft — AutoSelectCertificateForUrls](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/autoselectcertificateforurls): seleção por domínio e filtros do certificado, sujeita ao pedido do servidor.
- [Chromium — preferência de seleção](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/content_settings/core/common/pref_names.h) e [leitura das regras](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/content_settings/core/browser/content_settings_policy_provider.cc).
- [Microsoft — acesso à chave privada](https://learn.microsoft.com/en-us/windows/win32/api/wincrypt/nf-wincrypt-cryptacquirecertificateprivatekey): seleção automática não elimina exigências de interface do provedor criptográfico.
