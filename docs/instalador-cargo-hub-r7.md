# Cargo Hub r7

Revisão privada de teste da versão 0.1.34, preparada em 13/11/2026.

O pacote foi gerado em `runtime\private-installer\NovelisCargoHubSetup-0.1.34-r7-PRIVADO-TESTE-NaoDistribuir.exe`, com 742.129.502 bytes. Seu manifesto adjacente registra os hashes dos fontes e componentes.

```text
SHA-256 03a774e7b1ec783efcd1b5945905a0ab492cc41aa254881ded4059a74bff1ddb
```

## Alterações implementadas

### Arquivos dos CT-es

A tela CT-es pendentes consulta a disponibilidade dos arquivos a cada dois segundos enquanto estiver ativa e também ao recuperar o foco. Cada resposta confere as pastas configuradas de PDF, XML e comprovantes. O tempo efetivo de atualização inclui a latência do compartilhamento.

A conferência reutiliza as regras de identificação de arquivos da automação, incluindo `cte-<numero>`, identificação completa por filial/série/número e validação do conteúdo dos XMLs. A listagem de diretórios é reutilizada somente dentro de uma conferência. A próxima consulta faz uma nova leitura.

O painel de detalhes acompanha a mesma linha atualizada da tabela. Falhas de acesso ao compartilhamento geram aviso e mantêm os últimos dados disponíveis na interface. O botão Consultar CT-es realiza uma nova consulta SQL para incluir documentos no período selecionado.

### Período

As telas de visão geral, execução e CT-es pendentes oferecem Dia atual, Últimos 5 dias, Últimos 10 dias, Últimos 20 dias e Últimos 30 dias.

Foi adotado o período de dias corridos incluindo o dia atual, segundo a data do SQL Server. Dia atual é transmitido como `0`. Cinco dias corresponde a hoje e aos quatro dias anteriores.

### Operador e dispositivo

O modo backend local apresenta uma tela de entrada com nome do operador, conta Windows, computador e endereços MAC das interfaces ativas. A identificação do Windows e do dispositivo vem do processo do backend. O nome do operador é informado nessa tela.

Os registros são sincronizados para `\\192.168.254.250\rede\Publico\novelis-automacao\logs\sessoes.sqlite`, derivado da pasta do banco operacional. `LOGIN_AUDIT_DB_PATH` permite informar explicitamente outro caminho.

O banco compartilhado contém as tabelas `sessions` e `automation_events`. Guarda operador, conta Windows, computador, MACs, login, último contato, saída, execução vinculada e transições de estado. Os horários são armazenados em UTC, formato ISO 8601.

Os estados registrados são `stopped`, `running`, `stopping`, `completed`, `broken` e `cancelled`. A sessão recebe `active`, `logged_out` ou `interrupted`. Reiniciar o backend interrompe as sessões anteriores. A execução conserva a identificação de quem a iniciou após saída do operador.

Uma fila SQLite local em `runtime\login-audit.sqlite` preserva os registros antes da sincronização. A cópia ao compartilhamento ocorre a cada 15 segundos, com transações curtas, trava de escrita e eventos idempotentes. A interface avisa quando a sincronização falha. Chamadas legadas sem sessão preservam o registro da conta Windows e do dispositivo.

## Arquivos principais

- Backend de sessões em `app/api/routers/sessions.py`, `services/session_audit.py`, `services/device_identity.py` e `infrastructure/session_audit_db.py`.
- Conferência de documentos em `services/pending_documents.py`, `services/hub_service.py`, `services/cte_xml_files.py` e no planejador de pendentes.
- Captura de transições em `domain/run_state.py` e inicialização em `app/main.py`.
- Login e seleção de período em `FRONTEND-HUB/src/components/app/session-gate.tsx` e `period-select.tsx`, com integração às telas e ao adaptador HTTP.
- Manifesto de build atualizado em `scripts/setup/installer_receipt.py` para vincular o instalador aos fontes de sessões e documentos.
- Investigação independente da SEFAZ em `docs/sefaz-cte-teste-2026-11-13.md`, código em `tools/sefaz-cte-poc` e resultados sanitizados em `docs/evidence/sefaz-cte-2026-11-13.json`.

## Validação executada

- Suíte completa do backend com 254 testes aprovados e quatro ignorados pelas condições declaradas nos testes.
- Frontend com sete testes aprovados e verificação TypeScript concluída.
- PoC SEFAZ com cinco testes unitários aprovados, além das consultas reais documentadas no relatório específico.
- SQLite compartilhado criado com esquema versão 1 e `integrity_check=ok`, inicialmente sem registros de operadores ou execuções fictícias.
- Testes de replicação com SQLite reais em diretórios isolados, incluindo indisponibilidade do destino, retomada e identidade preservada após logout.
- Interface conferida em desktop e celular, com entrada, saída, cinco opções de período, PDF aparecendo e sendo removido e painel de detalhes atualizado durante a consulta automática. O navegador terminou sem erros de JavaScript.
- Preparação em diretório novo usando o Python e os wheels empacotados, com downloads de dependências desabilitados. Bootstrap concluiu com saída `0`, a API respondeu e o login/logout com replicação de auditoria passou no backend preparado.
- Hash SHA-256 do executável conferido com o manifesto. Os fontes registrados e o frontend do teste offline coincidiram com os inputs do instalador.

Os resultados sanitizados estão em `docs/evidence/hub-r7-tests.json`. Os logs completos locais estão em `runtime/crystal-tests/hub-r7-all-backend-tests-final.log`, `hub-r7-frontend-tests.log`, `hub-r7-private-build.log` e `hub-r7-offline-installation.log`.

O primeiro ciclo completo identificou uma dependência de temporização no teste da trava do bootstrap. O teste foi ajustado para aguardar o aviso real de contenção emitido pelo subprocesso. A suíte completa passou após esse ajuste. O comportamento de instalação foi preservado.

## Pendências de implantação

A homologação física no NB-GFR-VIN-05 continua pendente. Deve conferir instalação limpa, permissões da conta Windows para os compartilhamentos, entrada de operador, atualização de arquivos, registro das transições e geração real do DACTE.

As aprovações de licença e procedência do Crystal continuam pendentes. O pacote mantém o modo de desenvolvimento, uso privado de teste e `production_ready=false`. O módulo de distribuição SEFAZ foi entregue como PoC executável independente, com seus limites e resultados documentados.
