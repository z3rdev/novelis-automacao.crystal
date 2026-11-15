# Central de diagnóstico do desenvolvedor

Acesso: **Configurações → Central de diagnóstico**. Exige sessão de operador válida e modo desenvolvedor local ativo (`BACKEND/CONFIG.dev` com `DEVMODE=1` e `BACKEND/credentials.json`). A API verifica essas condições em todas as rotas; ocultar o menu não é a única proteção.

## Uso

1. Selecione um computador conectado com agente compatível.
2. Escolha as últimas 5, 10 ou 20 execuções e o período de 1, 7 ou 30 dias.
3. Clique em **Solicitar diagnóstico**. A solicitação passa por **Na fila → Coletando → Concluído**, ou informa falha/tempo esgotado/ausência de resposta.
4. Abra a solicitação na lista. O painel lateral tem **Resumo**, **Execuções**, **HTTP** e **Ambiente**. **Baixar JSON** salva o relatório já sanitizado.

“Concluído” significa que a coleta respondeu. Não significa que as automações tiveram sucesso ou que todas as dependências estão corretas. O resumo e as verificações indicam as falhas. Uma coleta interrompida pode retornar dados **Parciais**.

Computadores com uma versão anterior do backend aparecem como **Atualizar cliente**. A presença no painel de usuários, sozinha, não comprova que o agente de diagnóstico está disponível. É necessário instalar a versão que contém estes arquivos ou reiniciar o backend atualizado na prévia. Não foi criado instalador nesta alteração.

## Dados coletados

| Item | Verificação |
| --- | --- |
| Execuções | Histórico persistido deste computador, limitado por período/quantidade; situação, horários, falhas e eventos relevantes |
| Chamados HTTP | `save_http`, `readback_http`, confirmação registrada, número/link, CT-e, arquivos anexados e visibilidade registrada dos anexos |
| Conta e sistema | Conta Windows real do processo coletor, computador, versão, Windows, Python e arquitetura |
| Certificado | Seleção pelo CNPJ/thumbprint configurado no repositório `CurrentUser/My`, validade e associação a chave privada |
| Crystal | Processo x86, ProgID `CrystalDesignRunTime.Application.11`, criação COM e arquitetura/versão do runtime |
| Bibliotecas | Carregamento de `craxddrt.dll`, `crpe32.dll`, `crdb_ado.dll`, `u2lcom.dll` e `crxf_pdf.dll` |
| Dados do DACTE | Criação do SQLOLEDB x86; conexão SQL com `SELECT 1`, sem executar consulta fiscal |
| Relatório | Presença/hash do RPT e inspeção das fórmulas, fontes e geradores configurados de QR/Code 128 |
| PDF | Disponibilidade do mecanismo/impressora configurados, sem exportar nem imprimir |
| Instalação | Leitura do diagnóstico de instalação anterior, claramente identificado como histórico |

### Limites das evidências

- HTTP 200 sozinho não é confirmação de chamado. A confirmação apresentada vem do evento histórico correspondente. A coleta não repete a requisição ao portal.
- Ausência de eventos não comprova sucesso. Eventos e relatórios extensos são limitados e sinalizados como amostra.
- Certificado encontrado com chave privada associada não comprova que o provedor permitirá utilizá-la sem interação. Não há assinatura, exportação da chave, autenticação SEFAZ nem seleção de certificado no navegador nesta coleta.
- Disponibilidade dos geradores não equivale a validar os códigos de um novo PDF. Exportação fiscal, `ReadRecords`, `AddPictureObject`, impressão e decodificação de um documento novo continuam sendo testes separados.
- Um diagnóstico anterior de instalação não substitui homologação atual. Um resultado técnico positivo não altera o licenciamento do Crystal.

## Comunicação e isolamento

As solicitações e os resultados ficam no **PostgreSQL autenticado de comunicação já configurado**, nas tabelas:

- `public.cargo_hub_diagnostic_agents`
- `public.cargo_hub_diagnostic_requests`

Não são publicados no bucket MinIO de atualizações. A conta do banco precisa poder criar essas duas tabelas/índice no primeiro uso e consultar/atualizar os registros. Não é necessário permissão para criar schemas. O transporte respeita `CHAMADOS_PG_SSLMODE`, cuja configuração não foi alterada nesta etapa.

O backend atualizado de cada operador registra a capacidade de diagnóstico e verifica a fila a cada **15 segundos**, inclusive na bandeja e sem exigir que o operador abra a central. O sinal perde validade depois de **90 segundos**. `DIAGNOSTICS_AGENT_ENABLED=false` no ambiente legado desativa o agente naquele backend.

Uma solicitação não atendida expira em **10 minutos**. O agente recebe uma reserva de **4 minutos** e executa a inspeção em um processo Python local separado, com limite de **180 segundos**. O encerramento por tempo limite atinge apenas a árvore de processos criada pelo coletor, verificando a identidade do processo. Os dados parciais já recebidos podem ser preservados.

O protocolo aceita somente UUID do dispositivo e limites numéricos validados. Não aceita comandos, scripts, caminhos de arquivo nem URLs escolhidos pelo solicitante. Há apenas uma coleta ativa por dispositivo. Resultados de outra instância ou com reserva vencida não substituem o resultado atual.

As credenciais do PostgreSQL continuam locais ao backend. O controle de desenvolvedor usa a configuração local existente; não é um novo serviço de autenticação central/RBAC. O protocolo pressupõe computadores e credenciais do banco sob administração confiável.

## Proteção dos dados

O coletor aplica uma lista permitida de campos aos eventos HTTP e remove cabeçalhos, cookies, corpos completos de requisição/resposta e caminhos completos dos anexos. Links de chamados são reconstruídos somente para o domínio oficial configurado no código, sem parâmetros.

Senhas, tokens, PIDKEY, seriais, cadeias de conexão, autenticação e material de chave privada são removidos antes de sair do processo coletor; o agente faz uma segunda sanitização antes de gravar no PostgreSQL. A saída de erro do subprocesso não é repassada. O relatório ainda contém dados operacionais necessários ao suporte, como CT-e, número do chamado, conta Windows e caminhos técnicos; permanece na comunicação privada.

## Arquivos principais

- `BACKEND/app/domain/remote_diagnostics.py`: contrato de solicitações.
- `BACKEND/app/infrastructure/diagnostic_queue.py`: fila PostgreSQL, sinais, reserva e expiração.
- `BACKEND/app/services/remote_diagnostics/`: agente, subprocesso, histórico, verificações e sanitização.
- `BACKEND/app/api/routers/developer_diagnostics.py`: API protegida.
- `BACKEND/app/main.py`, `BACKEND/app/api/router.py`: integração ao ciclo de vida e às rotas.
- `FRONTEND-HUB/src/services/remote-diagnostics.ts`: contrato da interface; adaptadores em `http.ts`/`mock.ts`.
- `FRONTEND-HUB/src/components/app/diagnostics/`: central, painel lateral e eventos HTTP.
- `FRONTEND-HUB/src/routes/diagnosticos-dev.tsx`, `components/app/navigation.ts`: página e menu exclusivo.

## Validação desta alteração — 15/11/2026

- Suíte geral do backend: **707 aprovados**, 9 ignorados naquele teste, incluindo 5 testes PostgreSQL que exigem ativação explícita.
- Cinco testes PostgreSQL executados separadamente, todos aprovados, em tabelas temporárias de QA com prefixo único: concorrência, deduplicação, identidade do alvo, reservas vencidas e substituição de instância. As tabelas de QA foram removidas pelo próprio teste.
- Testes da interface da central, navegação e painel de usuários: **17 aprovados**.
- TypeScript, ESLint dos componentes novos e Ruff dos módulos novos verificados. Os adaptadores antigos possuem formatação preexistente fora do padrão Prettier; não foram reformatados integralmente nesta alteração.
- Coleta **real neste PC de desenvolvimento**, sem ações fiscais: histórico das últimas 10 execuções, certificado, COM x86, bibliotecas, RPT, fontes, geradores e `SELECT 1`. Resultado sanitizado em `runtime/remote-diagnostics/local-probe.json` (ignorado pelo Git).
- Teste adicional de ponta a ponta **aprovado**: API protegida de teste → fila PostgreSQL isolada → agente → subprocesso real deste PC → leitura do resultado pela API. Coleta completa em 14,25 s, incluindo `craxddrt.dll` e SQLOLEDB x86. Resultado sanitizado em `runtime/remote-diagnostics/local-round-trip.json`; não houve ação fiscal nem solicitação a outro computador. São **6 testes de integração PostgreSQL** aprovados ao todo, executados separadamente da suíte geral.
- Inspeção visual com dados controlados em Edge headless: temas claro/escuro, página em 1440/1024 px e painel lateral em 1440/1024/695 px; sem erro JavaScript ou transbordamento lateral. As capturas de QA não são evidência de coleta remota em outro computador.

Os testes não enviam solicitações a computadores de outros operadores. A homologação em cliente instalado depende de atualizar o backend desse computador e solicitar a coleta autorizada pela central.

Comandos dos testes, a partir da raiz do projeto:

```powershell
& '.\BACKEND\.venv\Scripts\python.exe' -m pytest BACKEND/tests/test_remote_diagnostics_history.py BACKEND/tests/test_remote_diagnostics_api.py BACKEND/tests/test_remote_diagnostics_agent.py BACKEND/tests/test_remote_diagnostics_checks.py BACKEND/tests/test_remote_diagnostics_process.py -q

# Integração real usando apenas tabelas de QA próprias no banco configurado.
$env:NOVELIS_DIAGNOSTIC_PG_TEST = '1'
& '.\BACKEND\.venv\Scripts\python.exe' -m pytest BACKEND/tests/test_remote_diagnostics_postgres.py -q
Remove-Item Env:NOVELIS_DIAGNOSTIC_PG_TEST

Push-Location FRONTEND-HUB
npx.cmd vitest run src/components/app/diagnostics/diagnostics.test.tsx
npx.cmd tsc --noEmit
Pop-Location
```

Para carregar o novo serviço na prévia, use **Sair do Cargo Hub** na bandeja e execute:

```powershell
& 'E:\PROJETOS\AUTOMAÇÃO NOVELIS\scripts\start-hub-preview-fast.ps1'
```

A prévia foi reiniciada em 15/11/2026 com parada normal dos serviços e reabertura da janela nativa. O script de abertura usa `Invoke-WebRequest -UseBasicParsing` para evitar a confirmação interativa do Windows PowerShell. Frontend e API responderam HTTP 200; a rota da central respondeu HTTP 401 sem sessão, conforme esperado. Nenhum instalador ou pacote oficial foi gerado.
