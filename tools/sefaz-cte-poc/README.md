# PoC oficial de CT-e

Cliente Node.js 22+ e TypeScript para consulta SOAP 1.2 e distribuição nacional de CT-e. Usa `fast-xml-parser` sob licença MIT e os módulos nativos de HTTPS e GZIP do Node.

## Preparação no Windows

```powershell
Set-Location 'E:\PROJETOS\AUTOMAÇÃO NOVELIS\tools\sefaz-cte-poc'
npm.cmd ci --ignore-scripts
npm.cmd test
$chave = '26261113254104001065570100000028791000028796'
node dist/cli.js validate --key $chave
```

## Certificado instalado no Windows

Selecione localmente um certificado autorizado, válido e com chave privada. O modo Windows utiliza `curl.exe` com Schannel e o repositório `CurrentUser\My`, sob a conta que executa o comando.

```powershell
$certificados = @(Get-ChildItem Cert:\CurrentUser\My |
  Where-Object { $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) })
$certificados | Select-Object Subject, NotAfter, Thumbprint
$env:CTE_WINDOWS_CERT_THUMBPRINT = Read-Host 'Thumbprint do certificado autorizado'
node dist/cli.js status --key $chave
node dist/cli.js dist --key $chave --cnpj '13254104001065' --uf 26 --max-batches 1
Remove-Item Env:\CTE_WINDOWS_CERT_THUMBPRINT
```

## Certificado A1 em arquivo

O caminho e a senha são recebidos pelo ambiente do processo. A senha deve ser digitada somente no computador autorizado. Este modo está implementado e aguarda teste real com um PFX autorizado.

```powershell
$env:CTE_A1_PFX = Read-Host 'Caminho local do PFX autorizado'
$senha = Read-Host 'Senha do A1' -AsSecureString
$ponteiro = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($senha)
try {
  $env:CTE_A1_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ponteiro)
  node dist/cli.js status --key $chave
  node dist/cli.js dist --key $chave --cnpj '13254104001065' --uf 26 --max-batches 1
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ponteiro)
  Remove-Item Env:\CTE_A1_PASSWORD -ErrorAction SilentlyContinue
  Remove-Item Env:\CTE_A1_PFX -ErrorAction SilentlyContinue
  $senha.Dispose()
}
```

## Operações e arquivos

- `validate --key ...` valida formato, modelo e DV.
- `status --key ...` consulta situação na SVSP. `--no-certificate` permite reproduzir o teste HTTPS anônimo.
- `dist --key ... --cnpj ... --uf ... --max-batches 1` continua o cursor nacional desse interessado.
- `nsu --key ... --cnpj ... --uf ... --nsu ...` recupera um NSU conhecido e faltante. Esse comando foi validado por teste de protocolo local.
- `--out C:\Dados\SEFAZ` muda a pasta persistente. O padrão é `runtime\sefaz-poc` na raiz do projeto, organizado por CNPJ e ambiente.
- Cada `NSU_*.xml` preserva o documento retornado. `CTE_<chave>.xml` é criado somente para `cteProc` com chave coincidente no documento e no protocolo, com autorização `100`.
- Os JSONs de resultado registram URL, horário UTC, HTTP, `cStat`, motivo, cursores e contagens. Respostas XML locais podem conter dados fiscais e exigem controle de acesso à pasta.

Os códigos de saída são `0` para operação concluída, `2` para erro ou rejeição e `3` para distribuição concluída sem o XML completo da chave procurada. `status` com saída `0` comprova a conclusão da consulta. Confira seu `cStat` para conhecer a situação fiscal.

## Consumo e retomada

Preserve `state.json` e use a mesma pasta para o mesmo CNPJ. O cliente grava cada documento antes de avançar o cursor, recupera respostas pendentes de processamento e usa `consumer.lock` para impedir execuções concorrentes nessa pasta. Uma trava remanescente exige conferir se o processo terminou antes de removê-la.

O cliente aguarda uma hora após esgotar o fluxo, receber `137` ou `656`. Coordene o cursor com outros sistemas da empresa. Pastas diferentes e produtos externos precisam compartilhar essa coordenação operacional. `consNSU` deve ser usado para uma lacuna identificada.

Os endpoints desta PoC estão fixados em produção. A consulta de situação atende emissão normal na SVSP, incluindo Pernambuco. Outros autorizadores, contingência e homologação exigem configurar e validar seus endpoints oficiais. O cliente de distribuição recebe CNPJ. A modalidade CPF permanece pendente.

O relatório de investigação e os resultados reais estão em [docs/sefaz-cte-teste-2026-11-13.md](../../docs/sefaz-cte-teste-2026-11-13.md).
