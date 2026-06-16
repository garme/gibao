# Modos de compilação

- `Full`: comportamento histórico. `main()` termina com `HALT`.
- `Kernel`: compila o kernel isolado, preservando handlers e rotinas do SO.
- `Overlay`: compila uma aplicação de usuário com `main()` normal; o epílogo chama `exit` por syscall.
- `Kernel+Overlay`: compila o kernel e overlays selecionados. A IDE gera automaticamente um `kernel/sys_overlays.inc` virtual em memória.

## Observação sobre `sys_overlays.inc`

O arquivo físico em `SO/kernel/sys_overlays.inc` é somente fallback vazio para compilação do kernel isolado.
No modo `Kernel+Overlay`, a IDE substitui esse arquivo por uma versão gerada automaticamente com os overlays selecionados.

## Rede e limites de segmento

No modo `Kernel+Overlay`, a IDE detecta o uso de `usr_net.c`, ativa automaticamente as syscalls 30/31 e inclui `kernel/sys_net.c` no kernel seletivo.

O log informa:

- perfil de rede detectado: cliente, servidor ou ambos;
- syscalls selecionadas;
- linhas ASM do kernel, overlays e arquivo final;
- palavras de instrução usadas de 4096;
- palavras de dados+BSS+pilha+imagens usadas de 4096.

A geração é abortada com uma mensagem explícita caso um segmento ultrapasse o limite arquitetural.
