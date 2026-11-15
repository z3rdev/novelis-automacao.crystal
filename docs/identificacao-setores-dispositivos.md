# Identificação do setor pelo computador

O nome informado pelo Windows classifica **setor, filial e tipo de estação**. O login destaca o setor e apresenta o nome do computador em texto menor. Filial e tipo de estação ficam na lista de computadores/sessões e no painel lateral do desenvolvedor. A busca aceita o nome do setor/filial sem exigir acentos; há filtros específicos de setor e filial.

Exemplo real deste computador: `NB-TI-VIN-07` → **Tecnologia da informação · Viana · Notebook**.

## Regras

A fonte única é `BACKEND/app/resources/device-naming.json`, versão 1. O Python lê o recurso empacotado; a interface importa o mesmo JSON para identificar o dispositivo nativo mesmo enquanto a conexão local está indisponível. O JSON não contém credenciais.

| Códigos do setor | Setor |
| --- | --- |
| GDF, GRF | Gestão de frota |
| TI | Tecnologia da informação |
| COM | Comercial |
| COMP | Compras, conforme correção do operador |
| MAN, MANUTENCAO | Manutenção |
| ABAST, ABASTECIMENTO | Abastecimento |
| FVN | Filial Viana |
| CORD | Coordenação |
| ACC | Acerto de contas |
| OCR, OCORRENCIA | Ocorrência |
| OPE, OPR, OPERACAO | Operação |
| RH | Recursos humanos |
| MKT, MARKETING | Marketing |
| QUA, QUALIDADE, QUALIDDADE | Qualidade |
| EXP, EXPEDICAO | Expedição |
| DHO | Desenvolvimento humano e organizacional |
| FIN, FINANCEIRO | Financeiro |
| JUR, JURIDICO | Jurídico |
| MON, MONITORAMENTO | Monitoramento |
| SESMT | Segurança do trabalho |
| NUC | Núcleo de auditoria |
| ALM, ALMOXARIFADO | Almoxarifado |

| Códigos da filial | Filial |
| --- | --- |
| VIN | Viana |
| PINDA | Pindamonhangaba |
| PIRACICABA, PIR | Piracicaba |
| RJ | Rio de Janeiro |
| PERNAMBUCO | Pernambuco |
| PGR | Ponta Grossa |

O primeiro segmento `NB` identifica Notebook; `WKS`, Workstation. A classificação descreve a convenção do nome, não uma inspeção física do hardware.

- Ignora maiúsculas/minúsculas, acentos, sufixo de domínio e separadores hífen, sublinhado ou espaço.
- Aceita números no final do segmento: `ABAST01/02`, `PINDA02/03`, `RJ02` e `PERNAMBUCO01/02` seguem a mesma regra do código sem número.
- Só aceita segmentos inteiros; `COM` não corresponde a `COMP`, `COMPUTADOR` nem a parte de outro nome.
- Dois aliases do mesmo setor, como GDF e GRF, são a mesma classificação. Dois setores distintos no mesmo nome exigem conferência; o sistema não escolhe um arbitrariamente.
- Campos sem regra aparecem como **Não identificado**. Conflitos aparecem como **Conferir identificação**.
- `PIN`, `RIO`, `GDFROTA`, `MDR`, `ABA` e outros códigos presentes nas capturas não receberam significados por aproximação. A resposta à pergunta de confirmação definiu COMP como Compras; PIN e RIO continuam pendentes de confirmação.

## Histórico e futuras permissões

Os nomes já são preservados no SQLite de sessões e dispositivos. O backend deriva a classificação desses nomes ao consultar os registros, incluindo clientes antigos sem metadados. Isso evita migrar ou sobrescrever o histórico. Renomear um computador segue a regra existente de identificação de máquina e não mescla registros automaticamente.

API de identidade, sessão e monitor inclui `classification` com `rules_version`, `source`, `sector`, `station_type`, `branch` e `conflicts`. Cada classificação possui código estável e rótulo de apresentação. Esses códigos podem servir de referência à futura política por setor. **Esta entrega não habilita nem bloqueia automações por setor e não trata o nome da máquina como autorização.**

## Validação e entrega

- **75 testes de backend aprovados**: regras, nomes reais das capturas, conflitos, persistência de sessão, inventário legado, heartbeat e controles de acesso existentes.
- **54 testes da interface aprovados**: o mesmo conjunto de nomes é conferido em Python e TypeScript; filtros, busca, painel lateral, login e reconexão foram exercitados.
- TypeScript e verificações de estilo dos arquivos alterados aprovados.
- Identificação real deste PC conferida diretamente pelo backend: TI / VIN / NB.
- Verificação visual com dados controlados, no tema escuro e larguras 1440, 1024 e 768 px, sem transbordamento horizontal da página e sem erros JavaScript. Nenhum fluxo fiscal foi iniciado.

Evidências locais em `runtime/dev-preview/`: `device-classification-backend-tests.log`, `device-classification-ui.json`, `device-classification-login.png`, `device-classification-monitor.png` e `device-classification-details.png`.

As mudanças estão no código e na prévia web de desenvolvimento. Não foi reconstruída a janela Tauri, gerado instalador, publicado release ou alterada a instalação existente nesta etapa.
