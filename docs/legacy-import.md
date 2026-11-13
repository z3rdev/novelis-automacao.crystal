# Importacao Do Legado

Origem:

```text
C:\Users\joao.barbosa\Documents\AUTOMATION - AUDITORIA CTE - OCORRENCIA
```

Itens reaproveitados no primeiro corte:

- mapa dos 28 passos do pre-passo;
- coordenadas e viewport;
- referencias de templates visuais;
- imagens de template em `BACKEND/app/data/templates/pre-passo`.
- contrato completo do `.env.example` legado, sanitizado;
- `.env` real copiado localmente para `BACKEND/.env` e ignorado pelo Git;
- superficie dos fluxos `pre-passo`, `tarifario`, `gnre` e `novelis`.

## Fluxos Python criados

- Fluxos operacionais visiveis na tela:
  - `PDF - Rodopar`
  - `XML - Sefaz`
  - `Comprovante - Local`
  - `Chamado - Novelis`
- `PrePassoLegacyFlow`: login DataPar, espera manual, replay por coordenada, fill de filial/documento e persistencia de sessao.
- `TarifarioFlow`: leitura da CONSULTA, filtro por documento/linha, `ton-temp.json`, pesquisa no tarifario e saida JSON.
- `GnreFlow`: busca GNRE por NMGRE/data/documento, captura evidencia e grava caminho no resultado do tarifario.
- `RodoparPdfFlow`: fluxo isolado para baixar PDFs do Rodopar, com repeticao por CTRC.
- `NovelisFlow`: autentica portal, verifica lista existente, monta titulo/mensagem e prepara abertura de chamado.
- `PendentesFlow`: coordenador em estagios inspirado no `pendentes-fluxo.js`.
- `LegacyCoordinator`: executa fluxos isolados, o fluxo `integrado` ou o coordenador `pendentes`.

Itens nao importados:

- credenciais capturadas;
- `node_modules`;
- `ms-playwright`;
- `captures` de execução;
- banco JSON grande gerado em producao.
