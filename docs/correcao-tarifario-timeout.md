# Correção da importação do tarifário — 15/11/2026

## Causa reproduzida

O cliente PostgreSQL de comunicação define `statement_timeout=10000` para suas consultas. Esse limite também alcançava o `COPY` da importação completa do tarifário. O tempo de transferência e preparação das linhas pelo cliente conta durante o `COPY`.

Em uma reprodução com o catálogo real e tabelas temporárias, a importação falhou com SQLSTATE **57014**. Não houve escrita nas tabelas públicas nessa reprodução. Os erros históricos apresentados pelo operador não guardaram esse código, portanto o código exato de cada tentativa anterior não pode ser reconstituído; a falha de timeout foi reproduzida diretamente.

O catálogo público permaneceu com **10.027 tarifas e 5.583 cidades**. Também foi encontrada uma coleta marcada como em gravação, iniciada antes da reinicialização do aplicativo. O lease dessa coleta deve expirar normalmente; não foi removido à força, pois coordena vários computadores.

## Alteração

- `TariffsPostgres.save()` usa `SET LOCAL statement_timeout = '120s'`, limitado à transação da importação. O limite das consultas comuns e o `lock_timeout` não mudam.
- A carga continua transacional, com controle de lease e preservação do catálogo se houver falha.
- Falhas de sincronização usam mensagens fixas e códigos permitidos. O evento `tariffs.refresh_failed` e o nó do fluxo passam a registrar etapa e código, sem exceções brutas, credenciais, cookies ou respostas do portal.

## Validação real

`runtime/dev-preview/probe-tariff-import-timeout.py` executa o importador com dados reais, redirecionando as quatro tabelas para cópias temporárias na própria conexão. A transação é sempre desfeita. Não altera o catálogo público nem seu lease.

| Verificação | Resultado observado |
| --- | --- |
| Reprodução inicial com limite de 10 s | Falhou com 57014 |
| Importação com limite local de 120 s | Aprovada; 10.027 tarifas e 5.583 cidades |
| COPY das tarifas nessa execução | 22,927 s |
| Importação completa nessa execução | 30,948 s |
| Repetição posterior com limite antigo | Aprovada, COPY em 2,556 s; confirma variação da duração |

Os 120 segundos são um limite máximo por comando, não uma espera fixa. O comportamento depende da rede e da carga; uma tentativa rápida pode passar com o limite antigo, enquanto uma transferência mais lenta falha.

Evidências sanitizadas: `runtime/dev-preview/tariff-import-timeout-fixed.json`, `tariff-import-timeout-baseline.json` e `tariff-timeout-backend-tests.log`. Esses arquivos são locais de diagnóstico, não conteúdo do instalador.

## Aplicação local e atualização completa

Após **638 testes aprovados e 4 ignorados**, os cinco arquivos Python da correção foram aplicados à instalação deste PC. Os originais e seus hashes foram preservados em `runtime/hotfix/tariff-timeout-20261115T121942Z/` dentro da instalação. Somente o backend Python reconhecido dessa instalação foi reiniciado, depois de confirmar que não havia fluxo em execução. A janela nativa permaneceu aberta; a API voltou com saúde `ok`.

- Sincronização automática após reiniciar: concluída em **15/11/2026 às 09:20:02**, horário de São Paulo, com 10.027 tarifas.
- Primeiro teste do nó personalizado: aprovado reaproveitando a sincronização recente, conforme o intervalo mínimo de 60 s. Não realizou outra leitura do portal.
- Segundo teste do nó personalizado: **nova leitura real do portal e commit real no PostgreSQL**, concluído às **09:22:00**, com 10.027 tarifas e 5.583 cidades; execução completa de validação em **24,723 s**. Nenhum chamado foi aberto nem documento fiscal gerado nesse teste.
- Próxima conferência automática compartilhada: **16/11/2026 às 00:00**, horário de São Paulo.

Evidências adicionais: `runtime/dev-preview/tariff-hotfix-applied.json`, `tariff-workflow-reuse-validation.json` e `tariff-workflow-live-validation.json`. O último identifica explicitamente `actual_portal=true` e `reused_recent_sync=false`.

Os registros de erro de execuções antigas permanecem como histórico. O aplicativo já pode executar uma nova tentativa com o backend corrigido. Outros computadores só receberão a alteração com uma atualização posterior. **Não foi gerado nem publicado instalador.**
