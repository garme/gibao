"""
build_modes.py - Pipeline unificado para a IDE do compilador C Cariri/GIBÃO.

Modos suportados:
  full    : comportamento histórico; main() termina com HALT
  kernel  : compila apenas kernel; não aplica DCE de SO para preservar handlers
  overlay : compila app de usuário; main() termina via syscall exit
  kernel_overlay : compila kernel + injeta overlays montados no .data
"""
from __future__ import annotations

import os
import sys
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from preprocess import Preprocessor
from lexer import tokenize
from parser import Parser
from semantic import Semantic
from codegen import CodeGen
from optimizer import optimize_with_log

try:
    from assembler_cariri_adv import AssemblerCariri
except Exception:  # mantém a IDE funcional mesmo sem assembler no PYTHONPATH
    AssemblerCariri = None

VALID_MODES = {"full", "kernel", "overlay"}

DEFAULT_DYNAMIC_COV_WINDOW_WORDS = 1536


# ---------------------------------------------------------------------------
# Otimização Kernel+Overlay: seleção automática de syscalls e módulos.
# ---------------------------------------------------------------------------
SYSCALL_NAMES = {
    1: "exit",
    2: "wait",
    3: "kill",
    4: "sem_lock",
    5: "sem_unlock",
    6: "spawn",
    7: "mutex_trylock",
    8: "mutex_unlock",
    9: "yield",
    10: "print_char",
    11: "read_char",
    12: "sleep",
    13: "alarm",
    14: "pause",
    15: "signal",
    16: "sigreturn",
    17: "get_signal",
    20: "write_pipe",
    21: "read_pipe",
    25: "shmget",
    27: "msg_send",
    28: "msg_recv",
    29: "thread_create",
    30: "net_out",
    31: "net_in",
    32: "thread_exit",
    33: "fs_out",
    34: "fs_in",
    35: "fs_exec",
}

# Cada syscall habilita seu módulo mínimo de kernel e sua linha de dispatch.
# Alguns módulos são sempre necessários por segurança de fault/exit/overlay.
BASE_KERNEL_MODULES = [
    "kernel/sys_mem.c",
    "kernel/sys_wakeup.c",
    "kernel/sys_proc_resources.c",
    "kernel/sys_proc_exit.c",
    "kernel/sys_proc_kill.c",
]
SYSCALL_MODULES = {
    1: [],
    2: ["kernel/sys_proc_wait.c"],
    3: [],
    4: ["kernel/sys_sem.c"],
    5: ["kernel/sys_sem.c"],
    6: ["kernel/sys_proc.c", "kernel/sys_proc_spawn.c"],
    7: ["kernel/sys_mutex.c"],
    8: ["kernel/sys_mutex.c"],
    9: [],
    10: ["kernel/sys_io.c"],
    11: ["kernel/sys_io.c"],
    12: ["kernel/sys_proc_sleep.c"],
    13: ["kernel/sys_proc_sleep.c"],
    14: ["kernel/sys_proc_sleep.c"],
    15: ["kernel/sys_signal.c"],
    16: ["kernel/sys_signal.c"],
    17: ["kernel/sys_signal.c"],
    20: ["kernel/sys_pipe.c"],
    21: ["kernel/sys_pipe.c"],
    25: ["kernel/sys_shm.c"],
    27: ["kernel/sys_msg.c"],
    28: ["kernel/sys_msg.c"],
    29: ["kernel/sys_proc.c", "kernel/sys_thread.c"],
    30: ["kernel/sys_net.c"],
    31: ["kernel/sys_net.c"],
    32: ["kernel/sys_thread_exit.c"],
    33: ["kernel/sys_fs.c"],
    34: ["kernel/sys_fs.c"],
    35: ["kernel/sys_fs.c"],
}

DISPATCH_SNIPPETS = {
    1: "if (tmp_sys_id == 1) { kernel_exit(); }",
    2: "if (tmp_sys_id == 2) { kernel_wait(tmp_sys_arg); }",
    3: "if (tmp_sys_id == 3) { kernel_kill(tmp_sys_arg, tmp_sys_arg2); }",
    4: "if (tmp_sys_id == 4) { kernel_sem_lock(); }",
    5: "if (tmp_sys_id == 5) { kernel_sem_unlock(); }",
    6: "if (tmp_sys_id == 6) { isr_tmp_ac = kernel_spawn(tmp_sys_arg, tmp_sys_arg2); curr_pcb->ac = isr_tmp_ac; }",
    7: "if (tmp_sys_id == 7) { isr_tmp_ac = kernel_mutex_trylock(); curr_pcb->ac = isr_tmp_ac; }",
    8: "if (tmp_sys_id == 8) { kernel_mutex_unlock(); }",
    9: "if (tmp_sys_id == 9) { kernel_need_resched = 1; }",
    10: "if (tmp_sys_id == 10) { kernel_print_char(tmp_sys_arg); }",
    11: "if (tmp_sys_id == 11) { isr_tmp_ac = kernel_read_char(); curr_pcb->ac = isr_tmp_ac; }",
    12: "if (tmp_sys_id == 12) { kernel_sleep(tmp_sys_arg); }",
    13: "if (tmp_sys_id == 13) { kernel_alarm(tmp_sys_arg); }",
    14: "if (tmp_sys_id == 14) { kernel_pause(); }",
    15: "if (tmp_sys_id == 15) { kernel_signal(tmp_sys_arg); }",
    16: "if (tmp_sys_id == 16) { kernel_sigreturn(); }",
    17: "if (tmp_sys_id == 17) { isr_tmp_ac = kernel_get_signal(); curr_pcb->ac = isr_tmp_ac; }",
    20: "if (tmp_sys_id == 20) { isr_tmp_ac = kernel_write_pipe(tmp_sys_arg); curr_pcb->ac = isr_tmp_ac; }",
    21: "if (tmp_sys_id == 21) { isr_tmp_ac = kernel_read_pipe(); curr_pcb->ac = isr_tmp_ac; }",
    25: "if (tmp_sys_id == 25) { isr_tmp_ac = kernel_shmget(tmp_sys_arg, tmp_sys_arg2); curr_pcb->ac = isr_tmp_ac; }",
    27: "if (tmp_sys_id == 27) { isr_tmp_ac = kernel_msg_send(tmp_sys_arg, tmp_sys_arg2); curr_pcb->ac = isr_tmp_ac; }",
    28: "if (tmp_sys_id == 28) { isr_tmp_ac = kernel_msg_recv(); curr_pcb->ac = isr_tmp_ac; }",
    29: "if (tmp_sys_id == 29) { isr_tmp_ac = kernel_thread_create(tmp_sys_arg, tmp_sys_arg2); curr_pcb->ac = isr_tmp_ac; }",
    30: "if (tmp_sys_id == 30) { isr_tmp_ac = kernel_net_out(tmp_sys_arg); curr_pcb->ac = isr_tmp_ac; }",
    31: "if (tmp_sys_id == 31) { isr_tmp_ac = kernel_net_in(tmp_sys_arg); curr_pcb->ac = isr_tmp_ac; }",
    32: "if (tmp_sys_id == 32) { isr_tmp_ac = kernel_thread_exit(); curr_pcb->ac = isr_tmp_ac; }",
    33: "if (tmp_sys_id == 33) { isr_tmp_ac = kernel_fs_out(tmp_sys_arg); curr_pcb->ac = isr_tmp_ac; }",
    34: "if (tmp_sys_id == 34) { isr_tmp_ac = kernel_fs_in(tmp_sys_arg); curr_pcb->ac = isr_tmp_ac; }",
    35: "if (tmp_sys_id == 35) { isr_tmp_ac = kernel_fs_exec(tmp_sys_arg); curr_pcb->ac = isr_tmp_ac; }",
}

def detect_syscalls_from_asm(asm: str) -> set[int]:
    """Detecta IDs de syscall no ASM de overlay procurando MOV <id> ... INT SYSCALL_INT."""
    ids: set[int] = set()
    pending: list[int] = []
    for raw in asm.splitlines():
        line = raw.split(';', 1)[0].strip()
        if not line or line.endswith(':'):
            continue
        m = re.match(r"^MOV\s+(-?\d+)\s*$", line, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if val in SYSCALL_NAMES:
                pending.append(val)
                pending = pending[-6:]
            continue
        if re.match(r"^INT\s+SYSCALL_INT\s*$", line, re.IGNORECASE):
            if pending:
                ids.add(pending[-1])
            pending.clear()
    return ids

def detect_syscalls_from_source(path: str) -> set[int]:
    """Fallback textual: útil quando o otimizador reordena ou o app usa wrappers pequenos."""
    try:
        txt = Path(path).read_text(encoding="utf-8")
    except Exception:
        return set()
    mapping = {
        "exit(": 1, "wait(": 2, "kill(": 3,
        "sem_lock(": 4, "sem_unlock(": 5,
        "spawn(": 6, "mutex_lock(": 7, "sys_mutex_trylock(": 7, "mutex_unlock(": 8,
        "yield(": 9, "print_char(": 10, "printstr(": 10, "printint(": 10,
        "read_char(": 11, "readint(": 11, "readstr(": 11,
        "sleep(": 12, "alarm(": 13, "pause(": 14,
        "signal(": 15, "sigreturn(": 16, "get_signal(": 17,
        "write_pipe(": 20, "read_pipe(": 21,
        "shmget(": 25, "msg_send(": 27, "msg_recv(": 28,
        "thread_create(": 29, "thread_exit(": 32,
        "net_sys_out(": 30, "net_sys_in(": 31,
        "fs_sys_out(": 33, "fs_sys_in(": 34, "fs_sys_exec(": 35, "fs_exec(": 35,
    }
    found = set()
    for token, sid in mapping.items():
        if token in txt:
            found.add(sid)
    # inclui indireções por include, sem tentar preprocessar novamente
    if "usr_printstr.c" in txt or "usr_printint.c" in txt or "usr_stdio.c" in txt:
        found.add(10)
    if "usr_exit.c" in txt or "usr_proc.c" in txt:
        found.add(1)
    if "usr_sleep.c" in txt or "usr_proc.c" in txt:
        found.add(12)
    if "usr_read_char.c" in txt or "usr_stdio.c" in txt:
        found.add(11)
    if ("usr_net.c" in txt or "usr_net_core.c" in txt or
            "usr_net_tcp.c" in txt or "usr_net_udp.c" in txt or
            "net_" in txt):
        found |= {30, 31}
    if ("usr_fs.c" in txt or "fs_" in txt):
        found |= {33, 34}
    return found

def detect_network_roles(paths: Sequence[str]) -> List[str]:
    """Classifica protocolos e papéis de rede para o relatório da IDE."""
    roles = set()
    tcp_client_tokens = (
        "net_connect_ipv4(", "net_connect_start(",
        "net_wait_connected(", "net_wait_connected_socket(",
    )
    tcp_server_tokens = (
        "net_bind_ipv4(", "net_bind_start(", "net_listen_socket(",
        "net_listen_start(", "net_accept(", "net_accept_start(",
        "net_wait_accept(",
    )
    udp_client_tokens = (
        "net_udp_sendto_ipv4(",
    )
    udp_server_tokens = (
        "net_udp_bind_ipv4(",
    )

    for path in paths:
        try:
            txt = Path(path).read_text(encoding="utf-8")
        except Exception:
            continue

        if any(token in txt for token in tcp_client_tokens):
            roles.add("TCP cliente")
        if any(token in txt for token in tcp_server_tokens):
            roles.add("TCP servidor")
        udp_is_server = any(token in txt for token in udp_server_tokens)
        udp_is_client = any(token in txt for token in udp_client_tokens)
        if udp_is_server:
            roles.add("UDP servidor")
        elif udp_is_client:
            roles.add("UDP cliente")

        if "usr_net_tcp.c" in txt and not any(r.startswith("TCP") for r in roles):
            roles.add("TCP baixo nível")
        if "usr_net_udp.c" in txt and not any(r.startswith("UDP") for r in roles):
            roles.add("UDP baixo nível")
        if "usr_net_core.c" in txt and not roles:
            roles.add("rede baixo nível")
        if "usr_net.c" in txt and not any(r.startswith("TCP") for r in roles):
            roles.add("TCP compatibilidade")

    order = [
        "TCP cliente", "TCP servidor", "TCP baixo nível", "TCP compatibilidade",
        "UDP cliente", "UDP servidor", "UDP baixo nível", "rede baixo nível",
    ]
    return [role for role in order if role in roles]


def detect_network_protocols(paths: Sequence[str]) -> List[str]:
    roles = detect_network_roles(paths)
    protocols = []
    if any(role.startswith("TCP") for role in roles):
        protocols.append("TCP")
    if any(role.startswith("UDP") for role in roles):
        protocols.append("UDP")
    if not protocols and roles:
        protocols.append("baixo nível")
    return protocols


def count_text_lines(text: str) -> int:
    """Número total de linhas textuais do ASM/arquivo gerado."""
    return len(str(text).splitlines())



def detect_fs_operations(paths: Sequence[str]) -> List[str]:
    """Classifica operações de FS usadas por overlays para o relatório da IDE."""
    ops = set()
    op_tokens = {
        "mount": ("fs_mount(",),
        "mkdir": ("fs_mkdir(",),
        "open_read": ("fs_open_read(",),
        "open_write": ("fs_open_write(",),
        "read": ("fs_read_byte(", "fs_read_all(", "fs_print_file("),
        "write": ("fs_write_byte(", "fs_write_text("),
        "list": ("fs_list(",),
        "exists": ("fs_exists(",),
        "delete": ("fs_delete(",),
        "close": ("fs_close(",),
    }
    for path in paths:
        try:
            txt = Path(path).read_text(encoding="utf-8")
        except Exception:
            continue
        if "usr_fs.c" in txt:
            ops.add("API FS")
        for name, tokens in op_tokens.items():
            if any(token in txt for token in tokens):
                ops.add(name)
    return sorted(ops)

def is_fs_enabled(syscalls: Iterable[int]) -> bool:
    """Retorna True quando o kernel seletivo precisa incluir o periférico de FS."""
    return bool({33, 34, 35} & set(syscalls))


def generate_sys_config_inc(syscalls: Iterable[int]) -> str:
    lines = [
        "#ifndef SYS_CONFIG_INC",
        "#define SYS_CONFIG_INC",
        "",
        "// Gerado automaticamente pela IDE no modo Kernel+Overlay.",
    ]
    for sid in sorted(set(syscalls)):
        name = SYSCALL_NAMES.get(sid, str(sid)).upper()
        lines.append(f"#define USE_SYSCALL_{name} 1")
    lines += ["", "#endif", ""]
    return "\n".join(lines)


def generate_sys_kernel_includes_inc(syscalls: Iterable[int]) -> str:
    enabled = set(syscalls)
    modules: list[str] = []
    for m in BASE_KERNEL_MODULES:
        if m not in modules:
            modules.append(m)
    for sid in sorted(enabled):
        for m in SYSCALL_MODULES.get(sid, []):
            if m not in modules:
                modules.append(m)
    # Spawn/threads já incluem sys_proc.c; nesse caso o overlay reutiliza
    # create_process_ex() para evitar duplicação de código.
    overlay_module = "kernel/sys_overlay_shared.c" if enabled.intersection({6, 29, 32}) else "kernel/sys_overlay.c"
    if overlay_module not in modules:
        modules.append(overlay_module)
    lines = [
        "#ifndef SYS_KERNEL_INCLUDES_INC",
        "#define SYS_KERNEL_INCLUDES_INC",
        "",
        "// Gerado automaticamente pela IDE: kernel mínimo para os overlays selecionados.",
    ]
    for m in modules:
        lines.append(f'#include "{m}"')
    lines += ["", "#endif", ""]
    return "\n".join(lines)

def generate_sys_dispatch_inc(syscalls: Iterable[int]) -> str:
    enabled = sorted(set(syscalls) | {1, 9})  # exit/yield sempre seguros para epílogo de overlay
    lines = [
        "#ifndef SYS_DISPATCH_INC",
        "#define SYS_DISPATCH_INC",
        "",
        "// Gerado automaticamente pela IDE: dispatcher seletivo.",
        "void kernel_dispatch_syscall() {",
    ]
    for sid in enabled:
        snippet = DISPATCH_SNIPPETS.get(sid)
        if snippet:
            lines.append("    " + snippet)
    lines += ["}", "", "#endif", ""]
    return "\n".join(lines)

def generate_sys_init_inc(syscalls: Iterable[int]) -> str:
    enabled = set(syscalls)
    lines = [
        "#ifndef SYS_INIT_INC",
        "#define SYS_INIT_INC",
        "",
        "// Gerado automaticamente pela IDE: inicialização mínima de serviços.",
        "void init_kernel_services() {",
    ]
    if 25 in enabled:
        lines.append("    init_ipc_shm();")
    if 27 in enabled or 28 in enabled:
        lines.append("    init_ipc_mailbox();")
    lines += ["}", "", "#endif", ""]
    return "\n".join(lines)



def generate_sys_tick_inc(syscalls: Iterable[int]) -> str:
    enabled = set(syscalls)
    needs_sleep_alarm = bool(enabled & {12, 13, 14, 15, 16, 17})
    lines = [
        "#ifndef SYS_TICK_INC",
        "#define SYS_TICK_INC",
        "",
        "// Gerado automaticamente pela IDE: atualização de clock seletiva.",
        "void kernel_tick_update() {",
        "    system_ticks = system_ticks + 1;",
    ]
    if needs_sleep_alarm:
        lines += [
            "    int i;",
            "    struct PCB_Struct *p;",
            "    i = 0;",
            "    p = &pcb[0];",
            "    while(i < MAX_PROCESSES) {",
            "        if (p->state != STATE_TERMINATED) {",
        ]
        if enabled & {12}:
            lines += [
                "            if (p->state == STATE_SLEEPING) {",
                "                if (system_ticks >= p->wakeup_tick) { p->state = STATE_READY; }",
                "            }",
            ]
        if enabled & {13, 14, 15, 16, 17}:
            lines += [
                "            if (p->alarm_tick > 0) {",
                "                if (system_ticks >= p->alarm_tick) {",
                "                    p->pending_signal = 14;",
                "                    p->alarm_tick = 0;",
                "                    if (p->state == STATE_PAUSED) { p->state = STATE_READY; }",
                "                }",
                "            }",
            ]
        lines += [
            "        }",
            "        p = p + 1;",
            "        i = i + 1;",
            "    }",
        ]
    lines += ["}", "", "#endif", ""]
    return "\n".join(lines)

def generate_sys_signal_inject_inc(syscalls: Iterable[int]) -> str:
    enabled = set(syscalls)
    if not (enabled & {15, 16, 17, 3, 13, 14}):
        return "\n".join([
            "#ifndef SYS_SIGNAL_INJECT_INC",
            "#define SYS_SIGNAL_INJECT_INC",
            "",
            "// Gerado automaticamente pela IDE: sinais desabilitados para este build.",
            "void kernel_signal_inject(struct PCB_Struct *curr, int target_sp) { }",
            "",
            "#endif",
            "",
        ])
    return "\n".join([
        "#ifndef SYS_SIGNAL_INJECT_INC",
        "#define SYS_SIGNAL_INJECT_INC",
        "",
        "// Gerado automaticamente pela IDE: sinais habilitados.",
        "void kernel_signal_inject(struct PCB_Struct *curr, int target_sp) {",
        "    int *sp_ptr;",
        "    if (curr->pending_signal > 0) {",
        "        if (curr->signal_handler != 0) {",
        "            if (curr->in_signal == 0) {",
        "                curr->sig_saved_sp = target_sp;",
        "                curr->sig_saved_ac = curr->ac;",
        "                sp_ptr = &ram[target_sp];",
        "                curr->sig_saved_step      = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_arr_base  = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_right     = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_left      = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_left_cond = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_val       = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_lhs       = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_idx       = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_ptr       = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->sig_saved_flags = *sp_ptr; sp_ptr = sp_ptr + 1;",
        "                curr->saved_pc = *sp_ptr;",
        "                *sp_ptr = curr->signal_handler;",
        "                curr->in_signal = 1;",
        "            }",
        "        }",
        "    }",
        "}",
        "",
        "#endif",
        "",
    ])

def make_kernel_selective_vfs(overlay_paths: Sequence[str], syscalls: Iterable[int]) -> Dict[str, str]:
    """VFS completo para Kernel+Overlay: overlays + includes/dispatcher/init seletivos."""
    content_overlays = generate_sys_overlays_inc(overlay_paths)
    config = generate_sys_config_inc(syscalls)
    inc = generate_sys_kernel_includes_inc(syscalls)
    dispatch = generate_sys_dispatch_inc(syscalls)
    init = generate_sys_init_inc(syscalls)
    tick = generate_sys_tick_inc(syscalls)
    siginj = generate_sys_signal_inject_inc(syscalls)
    return {
        "kernel/sys_config.inc": config,
        "./kernel/sys_config.inc": config,
        "sys_config.inc": config,
        "kernel/sys_overlays.inc": content_overlays,
        "./kernel/sys_overlays.inc": content_overlays,
        "sys_overlays.inc": content_overlays,
        "kernel/sys_kernel_includes.inc": inc,
        "./kernel/sys_kernel_includes.inc": inc,
        "sys_kernel_includes.inc": inc,
        "kernel/sys_dispatch.inc": dispatch,
        "./kernel/sys_dispatch.inc": dispatch,
        "sys_dispatch.inc": dispatch,
        "kernel/sys_init.inc": init,
        "./kernel/sys_init.inc": init,
        "sys_init.inc": init,
        "kernel/sys_tick.inc": tick,
        "./kernel/sys_tick.inc": tick,
        "sys_tick.inc": tick,
        "kernel/sys_signal_inject.inc": siginj,
        "./kernel/sys_signal_inject.inc": siginj,
        "sys_signal_inject.inc": siginj,
    }


def normalize_mode(mode: str) -> str:
    m = (mode or "full").strip().lower().replace("-", "_")
    if m in ("kernel_overlay", "kernel_overlays", "kernel+overlay", "kernel+overlays"):
        return "kernel_overlay"
    if m not in VALID_MODES:
        return "full"
    return m


def find_duplicate_asm_labels(asm: str) -> List[str]:
    """Retorna colisões perigosas de rótulos ASM.

    Definições repetidas de uma constante imutável com a mesma diretiva e o
    mesmo valor são toleradas, pois alguns módulos históricos repetem, por
    exemplo, ``HALT_INT: DD 25``. Colisões entre código, funções, BSS ou
    definições diferentes são rejeitadas.
    """
    definitions: Dict[str, List[str]] = {}
    for raw in str(asm).splitlines():
        line = raw.split(";", 1)[0].strip()
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", line)
        if match:
            label = match.group(1)
            body = re.sub(r"\s+", " ", match.group(2).strip()).upper()
            definitions.setdefault(label, []).append(body)

    dangerous: List[str] = []
    immutable = re.compile(r"^(DD|DB|INITD|INITB)\b")
    for label, bodies in definitions.items():
        if len(bodies) <= 1:
            continue
        same_immutable_constant = (
            len(set(bodies)) == 1 and
            bool(bodies[0]) and
            immutable.match(bodies[0]) is not None
        )
        if not same_immutable_constant:
            dangerous.append(label)
    return sorted(dangerous)


def validate_unique_asm_labels(asm: str, context: str = "ASM") -> None:
    duplicates = find_duplicate_asm_labels(asm)
    if duplicates:
        preview = ", ".join(duplicates[:12])
        if len(duplicates) > 12:
            preview += f", ... (+{len(duplicates) - 12})"
        raise ValueError(
            f"{context}: rótulos ASM duplicados: {preview}. "
            "Renomeie variáveis locais que colidam com nomes de funções."
        )


def strip_source_map(asm: str) -> Tuple[str, Dict[int, List[int]], Dict[int, int]]:
    clean_asm_lines: List[str] = []
    c_to_asm: Dict[int, List[int]] = {}
    asm_to_c: Dict[int, int] = {}

    for i, line in enumerate(asm.split("\n")):
        match = re.search(r";@ln:\s*(\d+)", line)
        if match:
            c_line = int(match.group(1))
            clean_line = line.replace(match.group(0), "").rstrip()
            c_to_asm.setdefault(c_line, []).append(i + 1)
            asm_to_c[i + 1] = c_line
            clean_asm_lines.append(clean_line)
        else:
            clean_asm_lines.append(line)
    return "\n".join(clean_asm_lines), c_to_asm, asm_to_c


# ~ def _set_include_dirs(filename: Optional[str]) -> Optional[str]:
    # ~ # Calcula os caminhos antes de alterar o diretório corrente.
    # ~ ide_dir = os.path.dirname(os.path.abspath(__file__))
    # ~ stdlib_dir = os.path.join(ide_dir, "stdlib")
    # ~ compile_dir = (
        # ~ os.path.dirname(os.path.abspath(filename))
        # ~ if filename
        # ~ else os.getcwd()
    # ~ )

    # ~ if compile_dir:
        # ~ os.chdir(compile_dir)

        # ~ if hasattr(Preprocessor, "LOCAL_INCLUDE_DIRS"):
            # ~ Preprocessor.LOCAL_INCLUDE_DIRS = [
                # ~ compile_dir,
                # ~ stdlib_dir,
                # ~ "./",
            # ~ ]

    # ~ return compile_dir

def _set_include_dirs(filename: Optional[str]) -> Optional[str]:
    # No executável, procura recursos ao lado da IDE.
    # Nos fontes, procura ao lado de build_modes.py.
    if getattr(sys, "frozen", False):
        ide_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        ide_dir = os.path.dirname(os.path.abspath(__file__))

    stdlib_dir = os.path.join(ide_dir, "stdlib")
    compile_dir = (
        os.path.dirname(os.path.abspath(filename))
        if filename
        else os.getcwd()
    )

    os.chdir(compile_dir)

    Preprocessor.LOCAL_INCLUDE_DIRS = [
        compile_dir,
        stdlib_dir,
    ]

    return compile_dir

def compile_c_to_asm(
    raw_code: str,
    filename: Optional[str] = None,
    mode: str = "full",
    optimize: bool = True,
    required_entry: Optional[str] = "main",
    file_system: Optional[Dict[str, str]] = None,
) -> Dict[str, object]:
    """Compila C para ASM Cariri usando o mesmo pipeline da IDE."""
    mode = normalize_mode(mode)
    if mode == "kernel_overlay":
        mode = "kernel"

    old_cwd = os.getcwd()
    try:
        _set_include_dirs(filename)

        pre = Preprocessor(file_system=file_system or {})
        code = pre.preprocess(raw_code)

        tokens = list(tokenize(code))
        parser = Parser(tokens)
        ast = parser.parse_program()

        semantic = Semantic(ast, required_entry=required_entry)
        semantic.analyze()

        gen = CodeGen(target=mode)
        asm = gen.generate(ast)

        opt_log: List[str] = []
        final_asm_raw = asm
        if optimize:
            opt_asm, opt_log = optimize_with_log(asm.splitlines(True))
            final_asm_raw = "".join(opt_asm)

        final_asm, c_to_asm, asm_to_c = strip_source_map(final_asm_raw)
        validate_unique_asm_labels(final_asm, context=f"Compilação {mode}")

        return {
            "mode": mode,
            "preprocessor": pre,
            "preprocessed_code": code,
            "tokens": tokens,
            "ast": ast,
            "semantic": semantic,
            "codegen": gen,
            "asm_raw": asm,
            "final_asm_raw": final_asm_raw,
            "final_asm": final_asm,
            "optimizer_log": opt_log,
            "c_to_asm_map": c_to_asm,
            "asm_to_c_map": asm_to_c,
        }
    finally:
        os.chdir(old_cwd)


def compile_file_to_asm(
    path: str,
    mode: str = "full",
    optimize: bool = True,
    file_system: Optional[Dict[str, str]] = None,
) -> Dict[str, object]:
    p = Path(path)
    return compile_c_to_asm(
        p.read_text(encoding="utf-8"),
        filename=str(p),
        mode=mode,
        optimize=optimize,
        file_system=file_system,
    )


def assemble_asm_words(asm: str) -> List[int]:
    """Monta ASM Cariri e retorna a imagem física completa como palavras de 16 bits."""
    if AssemblerCariri is None:
        raise RuntimeError("assembler_cariri_adv.py não está disponível. Não é possível gerar overlay INITD.")
    assembler = AssemblerCariri()
    result = assembler.assemble_code(asm)
    if not result or result[0] != "Ok":
        raise RuntimeError(f"Erro ao montar overlay: {result}")
    words_hex = result[1]
    return [int(str(w), 16) & 0xFFFF for w in words_hex]


SEGMENT_WORD_LIMIT = 4096

def _stack_size_from_asm(asm: str) -> int:
    """Extrai o tamanho lógico da pilha declarado por .stack."""
    for raw in asm.splitlines():
        line = raw.split(';', 1)[0].strip().lower()
        if line.startswith('.stack'):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1], 0)
                except ValueError:
                    return 0
    return 0

def analyze_asm_segments(asm: str) -> Dict[str, int]:
    """Mede uso real dos segmentos arquiteturais de 4 Ki palavras.

    code_words conta apenas instruções na seção .code. data_words inclui
    .data + .bss na imagem montada. data_total_words soma também a pilha
    lógica do kernel, que ocupa o mesmo segmento físico de dados/pilha.
    """
    words = assemble_asm_words(asm)
    code_words = _count_code_words(asm)
    data_words = max(0, len(words) - SEGMENT_WORD_LIMIT)
    stack_words = _stack_size_from_asm(asm)
    data_total_words = data_words + stack_words
    return {
        "limit": SEGMENT_WORD_LIMIT,
        "code_words": code_words,
        "code_free": SEGMENT_WORD_LIMIT - code_words,
        "data_words": data_words,
        "stack_words": stack_words,
        "data_total_words": data_total_words,
        "data_free": SEGMENT_WORD_LIMIT - data_total_words,
        "physical_words": len(words),
        "code_ok": int(code_words <= SEGMENT_WORD_LIMIT),
        "data_ok": int(data_total_words <= SEGMENT_WORD_LIMIT),
    }

def validate_segment_limits(usage: Dict[str, int], context: str) -> None:
    errors = []
    if not usage.get("code_ok"):
        errors.append(
            f"segmento de instruções: {usage['code_words']}/{usage['limit']} palavras"
        )
    if not usage.get("data_ok"):
        errors.append(
            f"segmento de dados+pilha: {usage['data_total_words']}/{usage['limit']} palavras"
        )
    if errors:
        raise RuntimeError(
            f"{context} excede o limite arquitetural de 4 Ki palavras: " + "; ".join(errors)
        )

def _count_code_words(asm: str) -> int:
    """Conta instruções reais na seção .code do ASM emitido pelo CodeGen."""
    in_code = False
    count = 0
    for raw in asm.splitlines():
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        if low == '.code':
            in_code = True
            continue
        if low in ('.data', '.bss') or low.startswith('.stack'):
            if in_code:
                break
        if not in_code:
            continue
        # Label isolado não gera palavra; instrução ou label+instrução gera uma palavra.
        if line.endswith(':'):
            continue
        count += 1
    return count


def assemble_overlay_image(asm: str) -> Dict[str, object]:
    """
    Monta overlay em formato compacto: code_words e data_words separados.
    O assembler histórico gera imagem física com padding até DS=0x1000; aqui removemos
    esse padding e colocamos metadados para o loader do kernel.
    """
    full_words = assemble_asm_words(asm)
    code_size = _count_code_words(asm)
    ds_base = 4096
    data_words = full_words[ds_base:] if len(full_words) > ds_base else []
    code_words = full_words[:code_size]
    return {
        "code_words": code_words,
        "data_words": data_words,
        "code_size": len(code_words),
        "data_size": len(data_words),
        "entry_pc": 0,
        "ds_delta": 4096,
        "full_size": len(full_words),
    }


def words_to_initd(label: str, words: Sequence[int], chunk_size: int = 12) -> str:
    """Converte uma lista de palavras já formatada em diretivas INITD."""
    all_words = [int(w) & 0xFFFF for w in words]
    lines: List[str] = []
    for i in range(0, len(all_words), chunk_size):
        chunk = all_words[i:i + chunk_size]
        prefix = f"{label}: INITD " if i == 0 else "INITD "
        vals = ", ".join(f"0x{w:04x}" for w in chunk)
        lines.append(prefix + vals)
    return "\n".join(lines)



def overlay_label_for_path(path: str, overlay_index: int) -> str:
    """Retorna o rótulo de imagem usado pela IDE para um overlay."""
    p = Path(path)
    safe = re.sub(r"\W+", "_", p.stem).strip("_") or f"overlay_{overlay_index}"
    return f"overlay_{overlay_index}_{safe}_image"


def generate_sys_overlays_inc(overlay_paths: Sequence[str], default_priority: int = 4) -> str:
    """
    Gera, em memória, o conteúdo de kernel/sys_overlays.inc para o modo Kernel+Overlay.

    A IDE injeta este include virtual no Preprocessor. O arquivo físico continua sendo um
    fallback vazio para permitir compilação Kernel sem overlays.
    """
    lines: List[str] = [
        "#ifndef SYS_OVERLAYS_INC",
        "#define SYS_OVERLAYS_INC",
        "",
        "// Gerado automaticamente pela IDE no modo Kernel+Overlay.",
        "// Não edite este conteúdo manualmente; selecione os overlays na IDE.",
        "",
    ]
    if not overlay_paths:
        lines += [
            "void boot_overlays() {",
            "    // Nenhum overlay selecionado.",
            "}",
            "",
            "#endif",
            "",
        ]
        return "\n".join(lines)

    for i, path in enumerate(overlay_paths):
        lines.append(f"int overlay_boot_addr_{i};")
    lines += ["", "void boot_overlays() {"]
    for i, path in enumerate(overlay_paths):
        label = overlay_label_for_path(path, i)
        pretty = Path(path).name
        lines.append(f"    // {pretty}")
        lines.append(f"    asm(\"MOV {label}\");")
        lines.append(f"    asm(\"STA overlay_boot_addr_{i}\");")
        lines.append(f"    kernel_spawn_overlay(overlay_boot_addr_{i}, {default_priority});")
    lines += ["}", "", "#endif", ""]
    return "\n".join(lines)


def make_overlay_vfs(overlay_paths: Sequence[str]) -> Dict[str, str]:
    """Compatibilidade: VFS que substitui apenas kernel/sys_overlays.inc."""
    content = generate_sys_overlays_inc(overlay_paths)
    return {
        "kernel/sys_overlays.inc": content,
        "./kernel/sys_overlays.inc": content,
        "sys_overlays.inc": content,
    }

def compile_overlay_file_to_initd(path: str, overlay_index: int) -> Dict[str, object]:
    """Compila arquivo C de usuário como overlay, monta e retorna bloco INITD compacto."""
    p = Path(path)
    result = compile_file_to_asm(str(p), mode="overlay", optimize=True)
    image = assemble_overlay_image(str(result["final_asm"]))
    overlay_usage = analyze_asm_segments(str(result["final_asm"]))
    validate_segment_limits(overlay_usage, f"Overlay {p.name}")
    label = overlay_label_for_path(str(p), overlay_index)

    # Formato compacto v2:
    # [magic, version, entry_pc, ds_delta, code_size, data_size, code..., data...]
    words = [
        0xCAFE, 2, image["entry_pc"], image["ds_delta"],
        image["code_size"], image["data_size"],
    ] + list(image["code_words"]) + list(image["data_words"])

    return {
        "path": str(p),
        "label": label,
        "words": words,
        "image": image,
        "initd": words_to_initd(label, words),
        "compile": result,
        "segment_usage": overlay_usage,
    }



def overlay_asm_to_cov_words(asm: str) -> Dict[str, object]:
    """
    Converte ASM de overlay para imagem .COV compacta v2.

    Formato:
      [0] magic      = 0xCAFE
      [1] version    = 2
      [2] entry_pc
      [3] ds_delta
      [4] code_size
      [5] data_size
      [6...] code_words + data_words
    """
    image = assemble_overlay_image(asm)
    words = [
        0xCAFE, 2, image["entry_pc"], image["ds_delta"],
        image["code_size"], image["data_size"],
    ] + list(image["code_words"]) + list(image["data_words"])

    return {
        "words": words,
        "image": image,
        "total_words": len(words),
        "code_size": image["code_size"],
        "data_size": image["data_size"],
    }


def write_cov_file(path: str, words: Sequence[int]) -> str:
    """Grava uma lista de palavras de 16 bits em arquivo .COV little-endian."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    data = bytearray()
    for w in words:
        value = int(w) & 0xFFFF
        data.append(value & 0xFF)
        data.append((value >> 8) & 0xFF)

    p.write_bytes(bytes(data))
    return str(p)


def compile_c_to_cov_words(
    raw_code: str,
    filename: Optional[str] = None,
    optimize: bool = True,
    file_system: Optional[Dict[str, str]] = None,
    window_words: int = DEFAULT_DYNAMIC_COV_WINDOW_WORDS,
) -> Dict[str, object]:
    """Compila C em modo overlay e retorna a imagem .COV compacta v2."""
    result = compile_c_to_asm(
        raw_code,
        filename=filename,
        mode="overlay",
        optimize=optimize,
        required_entry="main",
        file_system=file_system,
    )

    usage = analyze_asm_segments(str(result["final_asm"]))
    validate_segment_limits(usage, f"Overlay .COV {Path(filename).name if filename else ''}".strip())

    cov = overlay_asm_to_cov_words(str(result["final_asm"]))
    cov["compile"] = result
    cov["segment_usage"] = usage
    cov["window_words"] = int(window_words)
    cov["fits_window"] = int(cov["total_words"] <= int(window_words))
    cov["window_free"] = int(window_words) - int(cov["total_words"])
    return cov


def compile_file_to_cov_words(
    path: str,
    optimize: bool = True,
    file_system: Optional[Dict[str, str]] = None,
    window_words: int = DEFAULT_DYNAMIC_COV_WINDOW_WORDS,
) -> Dict[str, object]:
    """Compila um arquivo C para imagem .COV compacta v2."""
    p = Path(path)
    return compile_c_to_cov_words(
        p.read_text(encoding="utf-8"),
        filename=str(p),
        optimize=optimize,
        file_system=file_system,
        window_words=window_words,
    )


def compile_file_to_cov_file(
    source_path: str,
    output_path: str,
    optimize: bool = True,
    file_system: Optional[Dict[str, str]] = None,
    window_words: int = DEFAULT_DYNAMIC_COV_WINDOW_WORDS,
) -> Dict[str, object]:
    """Compila um arquivo C para .COV e grava o binário."""
    cov = compile_file_to_cov_words(
        source_path,
        optimize=optimize,
        file_system=file_system,
        window_words=window_words,
    )
    write_cov_file(output_path, cov["words"])
    cov["output_path"] = str(output_path)
    return cov


def inject_overlay_blocks(kernel_asm: str, overlay_blocks: Sequence[Dict[str, object]]) -> str:
    """Injeta tabela e imagens de overlay na seção .data do kernel."""
    if not overlay_blocks:
        return kernel_asm

    labels = [str(b["label"]) for b in overlay_blocks]
    table_lines = [
        "",
        "; ============================================================",
        "; OVERLAYS INJETADOS PELA IDE",
        "; Formato compacto v2: [0xCAFE, 2, entry_pc, ds_delta, code_size, data_size, code..., data...]",
        "; ============================================================",
        f"overlay_count: DD {len(labels)}",
        "overlay_table: INITD " + ", ".join(labels),
        "",
    ]
    for block in overlay_blocks:
        table_lines.append(f"; --- {block['path']} ---")
        table_lines.append(str(block["initd"]))
        table_lines.append("")
    overlay_text = "\n".join(table_lines)

    lines = kernel_asm.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().lower() == ".data":
            return "\n".join(lines[:idx + 1] + [overlay_text] + lines[idx + 1:]) + "\n"

    # Se não houver .data, cria uma seção antes de .bss ou .stack.
    for idx, line in enumerate(lines):
        if line.strip().lower() in (".bss",) or line.strip().lower().startswith(".stack"):
            return "\n".join(lines[:idx] + [".data", overlay_text] + lines[idx:]) + "\n"

    return kernel_asm.rstrip() + "\n\n.data\n" + overlay_text + "\n"


def build_kernel_with_overlays(kernel_path: str, overlay_paths: Sequence[str]) -> Dict[str, object]:
    """Compila kernel + overlays com kernel seletivo.

    Fluxo otimizado:
      1. compila e monta os overlays;
      2. detecta syscalls usadas;
      3. gera includes/dispatcher/init virtuais mínimos;
      4. compila o kernel com esses includes em memória;
      5. injeta as imagens no .data do ASM final.
    """
    overlay_paths = list(overlay_paths)
    blocks = [compile_overlay_file_to_initd(path, i) for i, path in enumerate(overlay_paths)]

    syscall_ids = set()
    for block in blocks:
        syscall_ids |= detect_syscalls_from_asm(str(block["compile"]["final_asm"]))
        syscall_ids |= detect_syscalls_from_source(str(block["path"]))
    # Epílogo de overlay usa exit/yield mesmo que o app não chame explicitamente.
    if overlay_paths:
        syscall_ids |= {1, 9}

    kernel_vfs = make_kernel_selective_vfs(overlay_paths, syscall_ids)
    kernel = compile_file_to_asm(kernel_path, mode="kernel", optimize=True, file_system=kernel_vfs)
    final_asm = inject_overlay_blocks(str(kernel["final_asm"]), blocks)
    kernel_usage = {
        "limit": SEGMENT_WORD_LIMIT,
        "code_words": _count_code_words(str(kernel["final_asm"])),
        "code_free": SEGMENT_WORD_LIMIT - _count_code_words(str(kernel["final_asm"])),
    }
    final_usage = analyze_asm_segments(final_asm)
    validate_segment_limits(final_usage, "Kernel+Overlay")
    return {
        "kernel": kernel,
        "overlays": blocks,
        "syscalls": sorted(syscall_ids),
        "syscall_names": [SYSCALL_NAMES.get(i, str(i)) for i in sorted(syscall_ids)],
        "generated_sys_config_inc": kernel_vfs["kernel/sys_config.inc"],
        "generated_sys_overlays_inc": kernel_vfs["kernel/sys_overlays.inc"],
        "generated_sys_kernel_includes_inc": kernel_vfs["kernel/sys_kernel_includes.inc"],
        "generated_sys_dispatch_inc": kernel_vfs["kernel/sys_dispatch.inc"],
        "generated_sys_init_inc": kernel_vfs["kernel/sys_init.inc"],
        "generated_sys_tick_inc": kernel_vfs["kernel/sys_tick.inc"],
        "generated_sys_signal_inject_inc": kernel_vfs["kernel/sys_signal_inject.inc"],
        "kernel_segment_usage": kernel_usage,
        "segment_usage": final_usage,
        "network_roles": detect_network_roles(overlay_paths),
        "network_protocols": detect_network_protocols(overlay_paths),
        "network_enabled": bool({30, 31} & set(syscall_ids)),
        "fs_operations": detect_fs_operations(overlay_paths),
        "fs_enabled": is_fs_enabled(syscall_ids),
        "storage_enabled": is_fs_enabled(syscall_ids),
        "line_usage": {
            "kernel_asm_lines": count_text_lines(str(kernel["final_asm"])),
            "final_asm_lines": count_text_lines(final_asm),
            "overlay_asm_lines": sum(
                count_text_lines(str(block["compile"]["final_asm"])) for block in blocks
            ),
        },
        "final_asm": final_asm,
    }
