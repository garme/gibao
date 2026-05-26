int SYSCALL_INT = 26;
int OUT_INT = 21;

void print_char(int ascii) {
    asm("LDA print_char_ascii");
    asm("SOP PUSH_OP");
    asm("MOV 10");
    asm("SOP PUSH_OP");
    asm("INT SYSCALL_INT");
}

void main() {
    print_char('O');
    print_char('K');
}
