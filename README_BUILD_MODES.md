# Modos de compilação

- `Full`: comportamento histórico. `main()` termina com `HALT`.
- `Kernel`: compila o kernel isolado, preservando handlers e rotinas do SO.
- `Overlay`: compila uma aplicação de usuário com `main()` normal; o epílogo chama `exit` por syscall.
- `Kernel+Overlay`: compila o kernel e overlays selecionados. A IDE gera automaticamente um `kernel/sys_overlays.inc` virtual em memória.

## Observação sobre `sys_overlays.inc`

O arquivo físico em `SO/kernel/sys_overlays.inc` é somente fallback vazio para compilação do kernel isolado.
No modo `Kernel+Overlay`, a IDE substitui esse arquivo por uma versão gerada automaticamente com os overlays selecionados.
