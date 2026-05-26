# optimizer.py — versão segura do otimizador (com LOG)
import re
from typing import List, Tuple, Callable, Set

# ------------------------
# Tokenizador auxiliar
# ------------------------
_token_re = re.compile(r'(\s+|\w+[:]?|[,]|\"[^\"]*\"|\'.*?\'|\S)')

def tokenize(line: str):
    return _token_re.findall(line)

def untokenize(tokens: List[str]) -> str:
    # Agora que o tokenize captura espaços (\s+), basta juntar tudo!
    return ''.join(tokens)

def log_append(log: List[str], msg: str):
    log.append(msg)

# ------------------------
# Utilitários sobre linhas
# ------------------------
_label_re = re.compile(r'^[A-Za-z_]\w*:$')
_name_re = re.compile(r'^[A-Za-z_]\w*$')

def is_label_line(line: str) -> bool:
    return bool(_label_re.match(line.strip()))

def find_prev_nonempty(lines: List[str], idx: int) -> int:
    """Retorna o índice da linha não-vazia anterior a idx, ou -1 se não houver."""
    i = idx - 1
    while i >= 0:
        if lines[i].strip() != "":
            return i
        i -= 1
    return -1

# ------------------------
# .data parsing / cleanup
# ------------------------
def parse_data_section(lines: List[str]):
    """
    Extrai tabela de constantes da seção .data.
    Formato reconhecido: label: DD N
    Retorna dict: {label: N}
    """
    consts = {}
    data_mode = False
    pat = re.compile(r'^([A-Za-z_]\w*)\s*:\s*DD\s+(-?\d+)\s*$')

    for ln in lines:
        s = ln.strip()
        if s == ".data":
            data_mode = True
            continue
        if s == ".bss":
            break
        if data_mode:
            m = pat.match(s)
            if m:
                name = m.group(1)
                value = int(m.group(2))
                consts[name] = value
    return consts

def remove_unused_constants(lines: List[str], const_names: set, log: List[str], protected=set()):
    """
    Remove entradas da seção .data correspondentes a constantes que NÃO
    aparecem em lugar algum do código final (fora da própria seção .data).
    """
    # localizar limites da seção .data
    data_start = None
    data_end = None
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if s == ".data":
            data_start = idx
            for j in range(idx+1, len(lines)):
                if lines[j].strip() == ".bss":
                    data_end = j
                    break
            break

    if data_start is None:
        return lines

    # escanear todo o arquivo EXCETO linhas entre data_start..data_end (a própria .data)
    referenced = set()
    for idx, ln in enumerate(lines):
        if data_start is not None and data_end is not None and data_start <= idx <= data_end:
            continue
        toks = tokenize(ln)
        for t in toks:
            if _name_re.match(t) and t in const_names:
                referenced.add(t)

    to_remove = set(const_names) - referenced - set(protected)
    if not to_remove:
        return lines

    out = []
    pat = re.compile(r'^([A-Za-z_]\w*)\s*:\s*DD\s+(-?\d+)\s*$')
    in_data = False
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if s == ".data":
            in_data = True
            out.append(ln)
            continue
        if in_data and s == ".bss":
            in_data = False
            out.append(ln)
            continue
        if in_data:
            m = pat.match(s)
            if m and m.group(1) in to_remove:
                log_append(log, f"[ConstFold] Removida constante não usada: {m.group(1)}")
                continue
            out.append(ln)
        else:
            out.append(ln)
    return out

# ----------------------------------------------------
# PASS 1 — Remover LDA X; STA X (NO-OP)
# ----------------------------------------------------
def pass_remove_load_store_noop(lines: List[str], log: List[str]):
    out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip('\n')
        if i + 1 < n:
            a = line.strip()
            b = lines[i+1].strip()
            ma = re.match(r'^(LDA|MOV)\s+([A-Za-z_]\w*)$', a)
            mb = re.match(r'^STA\s+([A-Za-z_]\w*)$', b)
            if ma and mb:
                src = ma.group(2)
                dst = mb.group(1)
                if src == dst:
                    log_append(log, f"[Peephole] Removido NO-OP: '{a}' seguido de '{b}' (linha {i+1})")
                    i += 2
                    continue
        out.append(line)
        i += 1
    return [ln + '\n' for ln in out]

# ----------------------------------------------------
# PASS 2 — Remover LDA morto (dead load) — com proteções
# ----------------------------------------------------
def pass_remove_dead_loads(lines: List[str], log: List[str], window=4):
    """
    Remove LDA <x> quando é carregado e, antes de ser usado, é sobrescrito ou descartado.
    Proteções:
      - se LDA é seguido por SOP pop seguido imediatamente por SOP push, NÃO REMOVER (padrão de retorno)
      - se SOP pop faz parte do prólogo (logo após label), NÃO considerar como overwrite descartável
    """
    out = []
    i = 0
    n = len(lines)

    while i < n:
        raw_line = lines[i]
        line = raw_line.rstrip('\n')
        m = re.match(r'^LDA\s+([A-Za-z_]\w*)$', line.strip())

        if m:
            used = False
            overwritten = False
            var = m.group(1)

            for j in range(i+1, min(n, i+1+window)):
                ls = lines[j].strip()

                # USO do AC — instruções que realmente usam o valor carregado
                if (
                    re.match(r'^(ADD|SUB|NAND|SHIFT|STA|STI|JZ|JN)\b', ls)
                    or ls.startswith("SOP push")
                    or ls.startswith("INT")
                    or re.match(r'^MOV\s*-\$', ls)
                ):
                    used = True
                    break

                # OVERWRITE / descarte potencial do AC
                # Qualquer LDA, e qualquer MOV que NÃO seja do tipo MOV -$ (ex: MOV 10 sobrescreve)
                if re.match(r'^LDA\b', ls) or (ls.startswith("MOV") and not re.match(r'^MOV\s*-\$', ls)):
                    overwritten = True
                    break

                # SOP pop: cuidado — pode ser overwrite, mas se for seguido por SOP push,
                # trata-se de padrão de retorno/epílogo -> NÃO remover LDA
                if ls.startswith("SOP pop"):
                    # se SOP pop está logo após label (prólogo), NÃO tratar como overwrite
                    prev_idx = find_prev_nonempty(lines, j)
                    if prev_idx >= 0 and is_label_line(lines[prev_idx]):
                        # log e marque como não-overwrite
                        log_append(log, f"[Safety] SOP pop em prólogo detectado (linha {j+1}), não considerar como overwrite")
                        # don't set overwritten, but continue scanning: the following instructions may use AC
                        continue

                    # verificar se existe SOP push imediatamente depois
                    if j+1 < n and lines[j+1].strip().startswith("SOP push"):
                        # padrão pop/push — potencial tratamento de retorno: não considerar overwritten
                        log_append(log, f"[Safety] Sequência SOP pop + SOP push detectada (linhas {j+1}-{j+2}), mantendo LDA")
                        used = True  # treat as used so LDA isn't removed
                        break
                    else:
                        # sop pop sem push -> likely overwrite
                        overwritten = True
                        break

            # Se nunca foi usado e foi sobrescrito/descartado → dead load
            if not used and overwritten:
                log_append(log, f"[Peephole] Removido LDA morto: '{line}' (linha {i+1})")
                i += 1
                continue

        out.append(raw_line)
        i += 1

    return [ln if ln.endswith('\n') else ln + '\n' for ln in out]

# ----------------------------------------------------
# PASS 3 — Colapsar rótulos consecutivos
# ----------------------------------------------------
def pass_collapse_consecutive_labels(lines: List[str], log: List[str]):
    out = []
    last_label = None
    label_map = {}

    for ln in lines:
        stripped = ln.strip()
        if _label_re.match(stripped):
            label = stripped[:-1]
            if last_label is None:
                last_label = label
                out.append(ln)
            else:
                label_map[label] = last_label
                log_append(log, f"[Labels] '{label}' fundido em '{last_label}'")
        else:
            last_label = None
            out.append(ln)

    if label_map:
        new = []
        for ln in out:
            toks = tokenize(ln)
            changed = False
            for i, t in enumerate(toks):
                if t in label_map:
                    toks[i] = label_map[t]
                    changed = True
                if t.endswith(':') and t[:-1] in label_map:
                    toks[i] = label_map[t[:-1]] + ':'
                    changed = True
            new_line = untokenize(toks)
            if changed:
                log_append(log, f"[Labels] Atualizadas referências de label em '{ln.strip()}'")
            new.append(new_line + '\n')
        return new
    return out

# ----------------------------------------------------
# PASS 4 — Remover JMP para próximo rótulo imediato
# ----------------------------------------------------
def pass_remove_jmp_to_next_label(lines: List[str], log: List[str]):
    out = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i].strip()
        if ln.startswith('JMP') and i + 1 < n:
            parts = ln.split()
            if len(parts) >= 2:
                dest = parts[1]
                next_line = lines[i+1].strip()
                if next_line == dest + ':':
                    log_append(log, f"[Jumps] Removido JMP para próximo label: {ln}")
                    i += 1
                    continue
        out.append(lines[i])
        i += 1
    return out

# ----------------------------------------------------
# PASS 5 — Remover JMP seguido de JMP
# ----------------------------------------------------
def pass_remove_jmp_followed_by_jmp(lines: List[str], log: List[str]):
    out = []
    i = 0
    n = len(lines)
    while i < n:
        cur = lines[i].strip()
        if cur.startswith("JMP") and i + 1 < n:
            nxt = lines[i+1].strip()
            if nxt.startswith("JMP"):
                log_append(log, f"[Jumps] Removido JMP redundante: '{nxt}' pois '{cur}' já salta")
                out.append(lines[i])
                i += 2
                continue
        out.append(lines[i])
        i += 1
    return out

# ----------------------------------------------------
# PASS 6 — Substituir LDA const por MOV const (rodar uma vez)
# ----------------------------------------------------
def pass_replace_constant_loads(lines: List[str], log: List[str], const_table: dict, protected:Set[str]=set()):
    out = []
    used_consts = set()
    pattern = re.compile(r'^LDA\s+([A-Za-z_]\w*)$')
    for ln in lines:
        stripped = ln.strip()
        m = pattern.match(stripped)
        if m:
            name = m.group(1)
            # PROTEÇÃO: Só substitui se estiver na const_table permitida
            if name in const_table and name not in protected:
                value = const_table[name]
                used_consts.add(name)
                new_line = f"MOV {value}\n"
                log_append(log, f"[ConstFold] LDA {name} → MOV {value}")
                out.append(new_line)
                continue
        out.append(ln)
    return out, used_consts

# ----------------------------------------------------
# PASS 7 — Remover LDA var após STA var
# ----------------------------------------------------
def pass_remove_redundant_load_after_store(lines: List[str], log: List[str]):
    out = []
    i = 0
    n = len(lines)
    while i < n:
        a = lines[i].strip()
        if i + 1 < n:
            b = lines[i+1].strip()
            m1 = re.match(r'^STA\s+([A-Za-z_]\w*)$', a)
            m2 = re.match(r'^LDA\s+([A-Za-z_]\w*)$', b)
            if m1 and m2:
                var1 = m1.group(1)
                var2 = m2.group(1)
                if var1 == var2:
                    log_append(log, f"[Peephole] Removido LDA redundante após STA: '{b}' (linha {i+2})")
                    out.append(lines[i])
                    i += 2
                    continue
        out.append(lines[i])
        i += 1
    return out

# ----------------------------------------------------
# PASS 8 — Remover SOP pop anterior a LDA ou MOV — com segurança
# ----------------------------------------------------
def pass_remove_sop_pop_before_load(lines: List[str], log: List[str]):
    """
    Remove 'SOP pop' quando seguido imediatamente de 'LDA x' ou 'MOV k',
    pois o valor carregado pela segunda instrução sobrescreve o AC.

    EXCEÇÃO IMPORTANTE:
    - NÃO remover quando o 'SOP pop' vier logo após um CALL.
      CALL sempre deixa algo na pilha que precisa ser descartado.
    """
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()

        if line == "SOP pop" and i + 1 < n:
            next_line = lines[i+1].strip()

            # --------------------------------------------------------
            # 1. Verificar se o SOP pop está logo após um CALL
            # --------------------------------------------------------
            # Procurar linha anterior não vazia
            prev = i - 1
            while prev >= 0 and lines[prev].strip() == "":
                prev -= 1

            if prev >= 0:
                prev_line = lines[prev].strip()
                if prev_line.startswith("CALL "):
                    # Não remover — CALL exige pop
                    out.append(lines[i])
                    i += 1
                    continue

            # --------------------------------------------------------
            # 2. Detectar padrões removíveis
            # --------------------------------------------------------

            # padrão: LDA <var>
            if re.match(r'^LDA\s+[A-Za-z_]\w*$', next_line):
                log_append(log, f"[Peephole] Removido 'SOP pop' redundante antes de '{next_line}' (linha {i+1})")
                i += 1
                continue

            # padrão: MOV <const>
            if re.match(r'^MOV\s+-?\d+$', next_line):
                log_append(log, f"[Peephole] Removido 'SOP pop' redundante antes de '{next_line}' (linha {i+1})")
                i += 1
                continue

        # padrão não detectado → manter linha normalmente
        out.append(lines[i])
        i += 1

    return out
    
# Em optimizer.py, adicione estes novos passes após o 'pass_remove_dead_loads':

# ----------------------------------------------------
# PASS 9 — Otimizar Incremento Simples 
# ----------------------------------------------------
def pass_optimize_increments(lines: List[str], log: List[str]):
    """
    Comprime i = i + 1 que o compilador gera como um gigante bloco
    LDA i / STA tmp_left / LDA prog_const_1 / STA tmp_right ...
    """
    out = []
    i = 0
    n = len(lines)
    while i < n:
        if i + 4 < n:
            # Detecta o início de um padrão i = i + 1 ou s = s + 1
            l1 = lines[i].strip()
            l2 = lines[i+1].strip()
            l3 = lines[i+2].strip()
            l4 = lines[i+3].strip()
            l5 = lines[i+4].strip()
            
            m1 = re.match(r'^LDA\s+([A-Za-z_]\w*)$', l1)
            
            if m1 and l2 == "STA tmp_left" and (l3 == "LDA prog_const_1" or l3 == "MOV 1") and l4 == "STA tmp_right" and l5 == "LDA tmp_left":
                var_name = m1.group(1)
                
                op_line = lines[i+5].strip()
                
                # Aceita tanto soma (ADD) quanto subtração (SUB)
                if i + 6 < n and op_line in ("ADD tmp_right", "SUB tmp_right") and lines[i+6].strip() == f"STA {var_name}":
                    
                    op_inst = "ADD" if op_line == "ADD tmp_right" else "SUB"
                    log_append(log, f"[Compress] Otimizado i = i +/- 1 para a variável '{var_name}'")
                    
                    out.append(f"LDA {var_name}\n")
                    out.append(f"{op_inst} prog_const_1\n")
                    out.append(f"STA {var_name}\n")
                    i += 7
                    continue

        out.append(lines[i])
        i += 1
    return out


# ----------------------------------------------------
# PASS X — Remover STA tmp; LDA tmp redundante
# ----------------------------------------------------
def pass_remove_store_load_same_tmp(lines: List[str], log: List[str]):
    """Remove LDA imediatamente após STA no mesmo temporário/variável.

    Após `STA x`, o AC continua contendo o mesmo valor armazenado em x.
    Portanto, `LDA x` logo em seguida é redundante quando não há instrução
    intermediária que altere AC, flags ou memória.
    """
    out = []
    i = 0
    n = len(lines)
    while i < n:
        if i + 1 < n:
            a = lines[i].strip()
            b = lines[i+1].strip()
            ma = re.match(r'^STA\s+([A-Za-z_]\w*)$', a)
            mb = re.match(r'^LDA\s+([A-Za-z_]\w*)$', b)
            if ma and mb and ma.group(1) == mb.group(1):
                log_append(log, f"[Peephole] Removido reload redundante: '{b}' após '{a}' (linha {i+2})")
                out.append(lines[i])
                i += 2
                continue
        out.append(lines[i])
        i += 1
    return out

# ----------------------------------------------------
# LISTA DE PASSES (ORDEM recomendada)
# ----------------------------------------------------
PASSES: List[Callable] = [
    # ~ pass_collapse_consecutive_labels,
    # ~ pass_remove_jmp_followed_by_jmp,
    pass_remove_jmp_to_next_label,
    pass_remove_load_store_noop,
    pass_remove_redundant_load_after_store,
    pass_remove_store_load_same_tmp,
    # ~ pass_remove_sop_pop_before_load,  #Comentada porque perde SP <- SP + 1
    pass_remove_dead_loads,
    pass_optimize_increments      # <-- NOVO
]

# ----------------------------------------------------
# FUNÇÃO PRINCIPAL
# ----------------------------------------------------
def optimize_with_log(code: List[str], max_iters=6):
    """
    code: lista de linhas (com '\n') ou string (será splitlines(True))
    retorna: (optimized_lines, log_list)
    """
    log: List[str] = []
    if isinstance(code, str):
        current = code.splitlines(True)
    else:
        current = code[:]

    # 1) extrair constantes da seção .data
    # NOTA: O parse extrai TUDO que tem DD (constantes E variáveis inicializadas)
    all_data_defs = parse_data_section(current)
    
    # --- FILTRO DE SEGURANÇA ---
    # Só vamos tratar como "Constante" (para fins de substituição e remoção)
    # símbolos que são explicitamente gerados como constantes pelo compilador/libs.
    # Ex: prog_const_0, const_1, lib_io_const_5.
    # Variáveis de usuário (main_x, global_var) são mutáveis e não devem ser tocadas.
    
    safe_consts = {}
    for name, value in all_data_defs.items():
        if "const_" in name:
            safe_consts[name] = value
    
    const_names = set(safe_consts.keys())

    # símbolos protegidos
    protected = {"push", "pop", "HALT_INT"}

    # 2) substituir LDA<const> -> MOV<value> (uma vez, explicitamente)
    # Apenas para safe_consts!
    current, used_consts = pass_replace_constant_loads(current, log, safe_consts, protected)

    # 3) aplicar passes peephole iterativamente
    for it in range(max_iters):
        prev = current
        for p in PASSES:
            current = p(current, log)
        if current == prev:
            break

    # 4) remover constantes não usadas da seção .data (checagem final)
    # Só tenta remover o que estava em const_names (as safe_consts). 
    # Variáveis de usuário (main_x) não estão em const_names, logo não serão removidas.
    current = remove_unused_constants(current, const_names, log, protected)
    
    # =========================================================
    # --- FIX: SANITIZAÇÃO EXTREMA PARA O SIMULADOR ---
    # Remove comentários e linhas vazias para evitar crashes no int(16)
    # =========================================================
    final_out = []
    for ln in current:
        if ';' in ln:
            ln = ln.split(';')[0]
            
        ln = ln.strip()
        if ln:
            final_out.append(ln + '\n')

    return final_out, log

# ----------------------------------------------------
# Auto-teste quando executado diretamente (útil para debug)
# ----------------------------------------------------
if __name__ == "__main__":
    sample = [
        "main:\n",
        "MOV 2\n",
        "SOP push\n",
        "MOV 3\n",
        "SOP push\n",
        "CALL soma\n",
        "SOP pop\n",
        "SOP push\n",
        "MOV 11\n",
        "SOP push\n",
        "CALL mul\n",
        "SOP pop\n",
        "SOP push\n",
        "CALL printint\n",
        "SOP pop\n",
        "MOV 10\n",
        "SOP push\n",
        "INT HALT_INT\n",
        "soma:\n",
        "SOP pop\n",
        "STA soma_retaddr\n",
        "SOP pop\n",
        "STA soma_b\n",
        "SOP pop\n",
        "STA soma_a\n",
        "LDA soma_a\n",
        "STA tmp_left\n",
        "LDA soma_b\n",
        "STA tmp_right\n",
        "LDA tmp_left\n",
        "ADD tmp_right\n",
        "SOP push\n",
        "LDA soma_retaddr\n",
        "SOP push\n",
        "RET\n",
    ]
    opt, log = optimize_with_log(sample)
    print("---- OPT ----")
    print("".join(opt))
    print("---- LOG ----")
    print("\n".join(log))
