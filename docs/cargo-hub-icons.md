# Ícone nativo do Cargo Hub

A imagem-base usada pelo executável fica em
`FRONTEND-HUB/src-tauri/icons/app-icon-source.png`. A versão anterior do ICO
continha somente 16, 32 e 48 pixels e deixava margens transparentes largas.
Em 32 pixels, o desenho ocupava 21 pixels. A revisão ocupa 30 pixels.

O ajuste de enquadramento foi produzido com a ferramenta de imagem integrada
`image_gen`, com transparência. Prompt utilizado:

```text
Precise production icon reframing edit. The provided image is the existing Cargo Hub application icon and is the edit target. Keep the exact same navy rounded-square icon, white angular C-shaped symbol and teal right-pointing arrow, same geometry, proportions, colors and appearance. Change ONLY the framing: crop away the large external transparent margins so the navy rounded square occupies approximately 94% of the square output canvas, centered, leaving about 3% transparent padding on every side. Remove the stray thin white horizontal/vertical lines outside the rounded square. Preserve transparent rounded corners. No extra decoration, no shadow outside the square, no words, no new logo design, no symbol changes. This image will be encoded as 16,24,32,48,64,128,256px Windows ICO frames, so the entire icon must fill its canvas and remain legible at small sizes.
```

O empacotamento determinístico gera quadros PNG RGBA no ICO, nos tamanhos
16, 20, 24, 32, 40, 48, 64, 96, 128 e 256 pixels. O mesmo conjunto atende o
executável e o favicon. Os PNGs de 16, 32 e 180 pixels também são atualizados.

Para regenerar esses arquivos no Windows:

```powershell
& '.\scripts\build-desktop-icons.ps1'
```

O instalador e a bandeja usam o ICO compilado no aplicativo. Alterar o arquivo
exige recompilar e reiniciar a prévia nativa para carregar o novo ícone.
As logos do cabeçalho e o fundo da tela de entrada mantêm seus próprios arquivos.
