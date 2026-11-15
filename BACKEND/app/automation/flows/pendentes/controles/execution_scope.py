def scoped_config(config, request):
    scope = request.execution_scope
    if scope == "full":
        return config
    if scope == "chamados":
        return {**config, "skipPdf": True, "skipXml": True, "skipComprovantes": True, "skipNovelis": False}
    result = {**config, "skipNovelis": True, "refreshNovelisRelatorioAfterChamados": False}
    if scope == "pdf":
        result.update(skipXml=True, skipComprovantes=True, refreshNovelisRelatorio=False,
                      requireNovelisFilterBeforeExecution=False)
    elif scope == "xml":
        result.update(skipPdf=True, skipXml=False, skipComprovantes=True,
                      refreshNovelisRelatorio=False, requireNovelisFilterBeforeExecution=False)
    elif scope == "comprovantes":
        result.update(skipPdf=True, skipXml=True, skipComprovantes=False,
                      refreshNovelisRelatorio=False, requireNovelisFilterBeforeExecution=False)
    return result
