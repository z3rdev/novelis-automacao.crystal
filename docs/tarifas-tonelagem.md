# Tarifas e tonelagem — prévia de 14/11/2026

Nova tela em **Operação → Tarifas e tonelagem**. A entrega atual é de código e prévia Tauri; nenhum instalador foi reconstruído ou publicado.

## Consulta e uso

- Filtros por origem, destino, veículo, vigência e busca textual; paginação no PostgreSQL, com 50 tarifas por página.
- Cada linha abre um painel lateral com IDs de tarifa/rota, transportadora, faturamento, operação, capacidade, valores, datas, ranking, share e link para os detalhes no portal.
- O cálculo recebe **toneladas da carga** e multiplica pela tarifa por tonelada usando `Decimal`, com arredondamento do resultado para centavos. A capacidade do veículo é uma informação distinta; não preenche automaticamente a carga. Excesso de capacidade e vigência fora do período são indicados.
- O total informado pelo portal é preservado separadamente. A estimativa não acrescenta ICMS, adValorem nem outros custos. Não há escrita de tarifa, faturamento ou chamado no portal por estas ações.
- Datas de calendário ISO são exibidas no dia correto, sem o deslocamento UTC que antecipava a vigência em um dia.

## Origem dos dados

Foi inspecionado o JavaScript servido pela própria página [Tarifário Novelis](https://novelis.wtmh.com.br/tarifa/tarifario). A tela usa `POST /tarifa/get_tarifas/`, recebe todos os dados autorizados e pagina no navegador. A coleta utiliza esse mesmo pedido de leitura, sem filtros de origem, destino, veículo ou período. Isso recupera todas as rotas disponibilizadas **à conta autenticada**, incluindo o histórico; não fabrica rotas inexistentes nem executa um produto cartesiano dos municípios.

O cliente autentica a conta configurada em `NOVELIS_TARIFARIO_USER` e `NOVELIS_TARIFARIO_PASS`, com a sessão e CSRF do portal. Senha, cookies e respostas de autenticação não são persistidos no catálogo, enviados à interface ou impressos nos logs. Redirecionamentos de POST não podem reenviar credenciais a outro host. Não foram usados endpoints de alteração/exclusão, CAPTCHA ou controles contornados.

O endpoint é o utilizado pelo site, não uma API pública com contrato documentado. Mudanças de login ou de resposta interrompem a atualização e conservam o catálogo anterior.

## Municípios

Referência do repositório [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros), fixada no commit `503e2f70bbf1b4b7ec0b1f68b09086ccc38fe861`. O arquivo efetivamente obtido contém **5.571 municípios**. Originais, hashes SHA-256, procedência e licença MIT foram incluídos em `BACKEND/app/resources/municipios/`.

O identificador do Selectize do portal **não é código IBGE**. Ambos são guardados separadamente. A correspondência utiliza UF e nome, ignorando acentos, maiúsculas e separadores, preservando o rótulo original para consulta. Ex.: `ES-Cariacica`, `PB-Cabedelo`. Nomes divergentes não recebem um IBGE por aproximação.

Na coleta real foram obtidas **5.583 opções de cidades**; **26 não tiveram correspondência exata com a referência**. Permanecem disponíveis com o nome/ID do portal e IBGE ausente. Isso requer revisão cadastral se for necessário atribuir IBGE a essas opções; não impede mostrar a tarifa original.

## Persistência e atualização

Tabelas dedicadas no PostgreSQL de comunicação já configurado:

| Tabela | Conteúdo |
| --- | --- |
| `public.cargo_hub_tarifas` | Catálogo, origem/destino, vigência, situação de presença no portal e última conferência |
| `public.cargo_hub_tarifa_versions` | Versões anteriores quando os dados de uma tarifa mudam |
| `public.cargo_hub_tarifa_cidades` | IDs e rótulos do portal, nome normalizado e IBGE quando confirmado |
| `public.cargo_hub_tarifa_sync` | Coleta compartilhada, exclusão mútua por lease, resultado e próxima consulta |

A importação é transacional e usa COPY. Uma resposta inválida ou vazia após existir catálogo não apaga a carga anterior. Tarifas que desaparecem da resposta mantêm histórico e são marcadas como ausentes na última coleta.

`NOVELIS_TARIFARIO_AUTO_SYNC=true` habilita o coletor durante a execução normal do backend. Os computadores consultam a programação compartilhada; um lease de 15 minutos permite somente uma coleta por vez. Atualização manual respeita intervalo mínimo de 60 segundos. Falhas aguardam 15 minutos. Um processo encerrado libera o lease quando possível; após interrupção abrupta ele expira.

O fim da vigência é **inclusivo**. A programação considera a próxima virada de período no fuso `America/Sao_Paulo`, com uma conferência diária adicional para detectar novos contratos. Históricos vencidos não provocam repetição imediata de coleta. Se nenhum backend estiver executando, a consulta vencida ocorre na próxima inicialização. O app pode ficar na bandeja, conforme a configuração já existente.

`tzdata` foi declarado explicitamente em `pyproject.toml` para fornecer a base de fusos no Windows, conforme a [documentação de zoneinfo do Python](https://docs.python.org/3/library/zoneinfo.html#data-sources). A dependência deverá entrar na wheelhouse pelo processo normal do próximo build autorizado; o instalador anterior não foi alterado.

Na **prévia de revisão**, `NOVELIS_BACKEND_READINESS=1` mantém os trabalhos automáticos desativados. A carga real desta etapa foi solicitada explicitamente pelo script técnico, e o botão de atualização manual funciona. A execução automática da próxima meia-noite ainda não foi observada em tempo real.

## Resultado real e testes

Coleta concluída em **14/11/2026 às 15:58**, horário de São Paulo:

| Situação | Quantidade |
| --- | ---: |
| Vigentes | 757 |
| Vencidas | 8.838 |
| Vigência inconsistente | 432 |
| Total | **10.027** |

Próxima conferência programada: **15/11/2026 às 00:00** (`2026-11-15T03:00:00Z`). Registros com fim anterior ao início ou data inválida são classificados para conferência; os valores e datas originais permanecem preservados.

- Backend completo: **443 aprovados, 4 ignorados**. Casos específicos cobrem datas inclusivas, decimal, tonelagem distinta de capacidade, municípios e IDs, autenticação, proteção de credenciais em redirecionamento e acesso às rotas locais.
- Frontend completo: **48 aprovados**. TypeScript sem erros.
- Ruff nos novos módulos Python: aprovado. Verificação dos arquivos desta funcionalidade sem credenciais no código-fonte.
- UI com **API local e catálogo PostgreSQL reais**, usando sessão técnica identificada e encerrada após o teste: consulta HTTP 200, busca de cidade, cálculo HTTP 200 com resultado decimal conferido, painel lateral, datas iguais às do portal, larguras 1920/1280/1024 sem transbordamento horizontal da página e nenhum erro JavaScript.
- Janela Tauri observada na nova tela, com a sessão já existente do usuário. Nenhum fluxo fiscal foi iniciado por estes testes.
- Permanece necessária a observação do ciclo automático em execução normal e a homologação simultânea em múltiplos computadores. Testes de calendário/claim não equivalem a essa homologação operacional.

Evidências locais em `runtime/dev-preview/`: `tariff-real-sync.json`, `tariff-collector-trace.log`, `tariff-ui-validation.json`, `tariff-ui-test.log`, `backend-tariffs-tests.log`, `frontend-tariffs-final-tests.log`, `tariff-typecheck.log`, `tarifas-real-1920.png`, `tarifas-real-1280.png`, `tarifas-real-1024.png` e `tarifa-real-lateral.png`. Os arquivos de execução não fazem parte da distribuição.

## Arquivos principais

- Backend: `services/tariffs/`, `infrastructure/tariffs_postgres.py`, `api/routers/tariffs.py`, integração em `main.py` e `api/router.py`.
- Frontend: `routes/tarifas.tsx`, `components/app/tariff-city-select.tsx`, `tariff-drawer.tsx`, contrato `services/tariffs.ts` e adaptadores HTTP/demonstração.
- Referência: `app/resources/municipios/`, com licença e manifesto de hashes; inclusão no pacote Python em `pyproject.toml`.
- Testes: `test_tariffs.py`, `test_tariff_portal.py`, `test_tariffs_api.py`, `tariff-drawer.test.tsx` e `lib/format.test.ts`.

A revisão seguinte integrou a conferência à fila e à preparação do chamado, com seleção apenas quando os critérios confirmam uma referência única. Veja [Conferência tarifária dos CT-es](conferencia-tarifaria-ctes.md) para regras, preservação dos valores originais e testes reais.
