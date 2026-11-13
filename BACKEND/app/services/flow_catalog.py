from app.domain.models import FlowDefinition


def list_flows(rodopar_enabled: bool = False) -> list[FlowDefinition]:
    return [
        FlowDefinition(
            key="pendentes",
            name="Iniciar automação",
            description="Verifica pendentes, gera PDF pelo banco/Crystal e executa XML Sefaz, comprovantes e Novelis.",
        ),
        FlowDefinition(
            key="consulta-pendentes",
            name="Consultar",
            description="Atualiza SQL dos últimos 5 dias e relatório Novelis sem executar baixas/chamados.",
        ),
        FlowDefinition(
            key="pdf-rodopar",
            name="PDF - Rodopar",
            description="Baixa PDFs do Rodopar em fluxo isolado, repetindo CTRCs da CONSULTA.",
            enabled=rodopar_enabled,
        ),
        FlowDefinition(
            key="xml-sefaz",
            name="XML - Sefaz",
            description="Baixa XMLs de CTE pela Sefaz usando o fluxo legado dedicado.",
        ),
        FlowDefinition(
            key="comprovante-local",
            name="Comprovante - Local",
            description="Busca comprovantes GNR/CMP na pasta local/rede e copia para a pasta do CTE.",
        ),
        FlowDefinition(
            key="chamado-novelis",
            name="Chamado - Novelis",
            description="Abre chamados Novelis usando o fluxo legado dedicado.",
        ),
    ]
