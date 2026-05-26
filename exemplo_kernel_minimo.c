int HALT_INT = 25;

void main() {
    asm("JMP os_boot");
    asm("os_boot:");
    asm("INT HALT_INT");
}
