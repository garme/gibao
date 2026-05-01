# ~ from .compiler_ast import *
from compiler_ast import *
import os
import re

class CodeGenError(Exception):
    def __init__(self, message):
        super().__init__(f"Erro de Geração de Código: {message}")

class SymbolTable:
    def __init__(self):
        self.global_scope = {}
        self.scopes = {}
        self.current_scope = None

    def enter_function(self, name):
        self.current_scope = name
        self.scopes[name] = {}

    def leave_function(self):
        self.current_scope = None

    def declare(self, name):
        if self.current_scope:
            scoped_name = f'{self.current_scope}_{name}'
            self.scopes[self.current_scope][name] = scoped_name
            return scoped_name
        else:
            self.global_scope[name] = name
            return name

    def resolve(self, name):
        if self.current_scope and name in self.scopes[self.current_scope]:
            return self.scopes[self.current_scope][name]
        elif name in self.global_scope:
            return self.global_scope[name]
        else:
            raise CodeGenError(f"Variável não definida: '{name}'")


class CodeGen:
    def __init__(self):
        self.code = []
        self.data = set()
        self.constants = {}
        self.label_counter = 0
        self.break_labels = []
        self.continue_labels = []
        self.array_names = set()
        self.local_data = []
        self.local_bss = []
        self.symbol_table = SymbolTable()
        
        self.current_function = None
        
        # Rótulo para salto de retorno
        self.func_exit_label = None 

        # strings
        self.strings = {}
        self.string_count = 0
        self.all_string_data = []

        # structs
        self.structs = {}  
        
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.library_path = os.path.join(base_dir, "stdlib")
        
        # bibliotecas
        self.required_libraries = set()

        # Temporários conhecidos
        self.known_temps = []
        
        self.current_line = None

    def string_to_bytes(self, s_val):
        """Converte string literal em lista de inteiros (ASCII + 0)."""
        if s_val.startswith('"') and s_val.endswith('"'):
            s_val = s_val[1:-1]
        
        bytes_list = list(s_val.encode('utf-8'))
        bytes_list.append(0) # Null terminator
        return bytes_list

    def generate(self, program):
        try:
            self.emit('.code')
            
            # --- INJEÇÃO DO CALL GRAPH AQUI ---
            # Removemos a gordura da Árvore Sintática antes de gerar qualquer coisa!
            mortas = self.prune_dead_functions(program)
            print(f"Otimização AST: {mortas} funções não utilizadas foram removidas.")
            # ----------------------------------

            # ---------------------------------------------------------
            # 1. SETUP INICIAL
            # ---------------------------------------------------------
            items = getattr(program, 'items', None) or getattr(program, 'functions', None) or []
            for decl in items:
                if isinstance(decl, LibraryImport):
                    self.required_libraries.add(decl.name)

            functions = [f for f in items if isinstance(f, Function)]
            globals_raw = [f for f in items if not isinstance(f, Function)]

            # Coleta Structs
            for decl in globals_raw:
                if isinstance(decl, StructDecl):
                    offsets = {}
                    offset = 0
                    for fname, ftype, _ in decl.fields:
                        offsets[fname] = offset
                        field_size = self.sizeof(ftype)
                        offset += field_size
                    self.structs[decl.name] = {
                        "fields": offsets,
                        "size": offset
                    }

            globals_var = [g for g in globals_raw if isinstance(g, (VarDecl, ArrayDecl))]
            globals_assign = [g for g in globals_raw if isinstance(g, Assignment)]

            for decl in globals_var:
                if isinstance(decl, ArrayDecl):
                    self.array_names.add(decl.name)

            # Declara globais
            declared = set()
            for decl in globals_var:
                if isinstance(decl, VarDecl):
                    for entry in decl.names:
                        if isinstance(entry, tuple):
                            raw = entry[0]
                            name = raw.lstrip('*') if isinstance(raw, str) else str(raw)
                        elif isinstance(entry, str):
                            name = entry.lstrip('*')
                        else:
                            raise TypeError(f"Tipo inválido em VarDecl: {entry}")

                        if name not in declared:
                            self.symbol_table.declare(name)
                            declared.add(name)

                elif isinstance(decl, ArrayDecl):
                    name = decl.name
                    if name not in declared:
                        self.symbol_table.declare(name)
                        declared.add(name)

            # Gera atribuições globais
            for assign in globals_assign:
                self.generate_stmt(assign)

            # ---------------------------------------------------------
            # 2. GERAÇÃO DE FUNÇÕES
            # ---------------------------------------------------------
            mains = [f for f in functions if f.name == 'main']
            others = [f for f in functions if f.name != 'main']

            for func in mains + others:
                self.local_data = []
                self.local_bss = []
                self.generate_function(func)

            # ---------------------------------------------------------
            # 3. LIBS EXTERNAS
            # ---------------------------------------------------------
            for lib in sorted(self.required_libraries):
                lib_code = self.load_external_library(lib)
                if lib_code:
                    self.emit(f"\n; --- external library: {lib} ---")
                    for ln in lib_code:
                        self.emit(ln)
                    self.emit(f"\n; --- end library: {lib} ---\n")

            temp_pattern = re.compile(r'\b(tmp_[A-Za-z0-9_]+)\b')
            for line in self.code:
                for m in temp_pattern.finditer(line):
                    temp = m.group(1)
                    self.data.add(temp)

            # ---------------------------------------------------------
            # 4. GERAÇÃO DE .DATA E .BSS
            # ---------------------------------------------------------
            has_data = []
            has_bss = []
            declared = set()

            for decl in globals_var:
                # VARIÁVEIS GLOBAIS
                if isinstance(decl, VarDecl):
                    for entry in decl.names:
                        if isinstance(entry, tuple):
                            if len(entry) == 4: raw_name, kind, _, init = entry
                            elif len(entry) == 2: raw_name, init = entry
                            name = raw_name.lstrip('*')
                        elif isinstance(entry, str):
                            name = entry.lstrip('*')
                            init = None

                        if name in declared: continue
                        declared.add(name)

                        vartype = getattr(decl, 'vartype', None)
                        is_char = isinstance(vartype, CharType)

                        if init is not None:
                            value = init[0]
                            if isinstance(value, UnaryOp) and value.op in ('-', '+') and isinstance(value.expr, Const):
                                sign = -1 if value.op == '-' else 1
                                value = sign * (int(value.expr.value) if value.expr.literal_type == "int" else value.expr.value)
                            if isinstance(value, Const):
                                value = int(value.value) if value.literal_type == "int" else value.value
                            elif isinstance(value, AddressOf):
                                value = self.symbol_table.resolve(value.var.name)
                            elif isinstance(value, Var):
                                value = self.symbol_table.resolve(value.name)
                            elif isinstance(value, StringLiteral):
                                value = self.get_string_label(value.value)

                            if is_char:
                                db_repr = self.format_char_literal(value)
                                has_data.append((name, db_repr, "DB"))
                            else:
                                has_data.append((name, value, "DD"))
                        else:
                            if isinstance(vartype, StructType):
                                size = self.structs[vartype.name]["size"]
                                has_bss.append((name, size, "RESD"))
                            elif isinstance(vartype, CharType):
                                has_bss.append((name, 1, "RESB"))
                            else:
                                has_bss.append((name, 1, "RESD"))

                elif isinstance(decl, ArrayDecl):
                    name = decl.name
                    arrtype = getattr(decl, 'arrtype', None)
                    init = getattr(decl, 'init', None)

                    if name in declared: continue
                    declared.add(name)

                    elem_is_char = isinstance(getattr(arrtype, 'base', None), CharType)

                    if init is not None and len(init) > 0:
                        if len(init) == 1 and isinstance(init[0], StringLiteral):
                             bytes_vals = self.string_to_bytes(init[0].value)
                             has_data.append((name, bytes_vals, "INITB"))
                        else:
                            # --- FIX: Desembrulha Constantes e Operadores Unários ---
                            values = []
                            for v in init:
                                if hasattr(v, 'op') and v.op in ('-', '+') and hasattr(v, 'expr'):
                                    sign = -1 if v.op == '-' else 1
                                    val = int(v.expr.value) if getattr(v.expr, 'literal_type', '') == "int" else v.expr.value
                                    values.append(sign * val)
                                elif hasattr(v, 'value'):
                                    values.append(int(v.value) if getattr(v, 'literal_type', '') == "int" else v.value)
                                else:
                                    values.append(v)
                            
                            if elem_is_char:
                                has_data.append((name, values, "INITB"))
                            else:
                                has_data.append((name, values, "INITD"))
                    else:
                        total_size = arrtype.size
                        if isinstance(arrtype.base, StructType):
                            struct_size = self.structs[arrtype.base.name]["size"]
                            has_bss.append((name, total_size * struct_size, "RESD"))
                        elif isinstance(arrtype.base, CharType):
                            has_bss.append((name, total_size, "RESB"))
                        else:
                            has_bss.append((name, total_size, "RESD"))
                                
            for entry in getattr(self, 'all_local_data', []):
                if len(entry) == 3: has_data.append(entry)
                elif len(entry) == 2:
                    name, value = entry
                    has_data.append((name, value, "DD"))

            for entry in getattr(self, 'all_local_bss', []):
                if len(entry) == 3: has_bss.append(entry)
                elif len(entry) == 2:
                    name, size = entry
                    kind = "RESB" if size == 1 else "RESD"
                    has_bss.append((name, size, kind))

            used_vars = set(self.data)
            already_data = {e[0] for e in has_data}
            already_bss = {e[0] for e in has_bss}
            for var in sorted(used_vars):
                if isinstance(var, str) and var.startswith('const_'): continue
                if var not in already_data and var not in already_bss:
                    has_bss.append((var, 1, "RESD"))

            self.emit("\n.data")
            for label, val_bytes, kind in self.all_string_data:
                val_str = ",".join(str(b) for b in val_bytes)
                self.emit(f"{label}: INITB {val_str}")

            for entry in has_data:
                if len(entry) == 3: name, values, kind = entry
                else: name, values = entry; kind = "INITD" if isinstance(values, list) else "DD"

                if not isinstance(values, list):
                    self.emit(f"{name}: {kind} {values}")
                else:
                    val_str = ",".join(str(v) for v in values)
                    self.emit(f"{name}: {kind} {val_str}")

            for (valtype, original_val), (const_label, kind, raw) in self.constants.items():
                self.emit(f"{const_label}: {kind} {raw}")

            if hasattr(self, 'library_constants'):
                for lib_label, lib_value in self.library_constants.items():
                    self.emit(f"{lib_label}: DD {lib_value}")

            self.emit('PUSH_OP: DD 0')
            self.emit('POP_OP: DD 1')
            self.emit('HALT_INT: DD 25')

            if has_bss:
                self.emit("\n.bss")
                for entry in has_bss:
                    name, size, kind = entry[0], entry[1], (entry[2] if len(entry)>2 else "RESD")
                    self.emit(f"{name}: {kind} {size}")

            self.emit('.stack 100') 
            return '\n'.join(self.code)

        except Exception as e:
            if isinstance(e, CodeGenError): raise
            raise CodeGenError(str(e))

    def emit(self, instruction):
        # Ignora linhas vazias ou labels (ex: "L1:") para não sujar o mapa
        if self.current_line and not instruction.strip().endswith(':'):
            # Anexa o Source Map invisível no final da instrução
            self.code.append(f"{instruction:<25} ;@ln:{self.current_line}")
        else:
            self.code.append(instruction)

    def sanitize_const_name(self, val):
        if isinstance(val, str): val = val.strip("'").strip('"')
        safe = "".join(ch for ch in str(val) if ch.isalnum() or ch == '_')
        return safe or f"c{abs(hash(val))%10000}"

    def generate_stmt(self, stmt):
        if hasattr(stmt, 'lineno') and stmt.lineno:
            self.current_line = stmt.lineno
            
        if isinstance(stmt, Assignment):
            if getattr(stmt, "is_struct_assign", False):
                self.gen_struct_assignment(stmt)
                return

            if isinstance(stmt.target, Var):
                if isinstance(stmt.value, Var) and stmt.value.name in self.array_names:
                    self.emit(f'MOV {self.symbol_table.resolve(stmt.value.name)}')
                    self.emit(f'STA {self.symbol_table.resolve(stmt.target.name)}')
                else:
                    self.generate_expr(stmt.value)
                    self.emit(f'STA {self.symbol_table.resolve(stmt.target.name)}')
                self.data.add(self.symbol_table.resolve(stmt.target.name))

            elif isinstance(stmt.target, Deref):
                self.generate_expr(stmt.target.ptr)
                self.emit('STA tmp_lhs')
                self.data.add('tmp_lhs')
                self.generate_expr(stmt.value)
                self.emit('STA tmp_val')
                self.data.add('tmp_val')
                self.emit('LDA tmp_lhs')
                self.emit('STA tmp_ptr')
                self.data.add('tmp_ptr')
                self.emit('LDA tmp_val')
                self.emit('STI tmp_ptr')
            
            elif isinstance(stmt.target, ArrayAccess):
                self.gen_array_element_address(stmt.target)
                self.emit("STA tmp_lhs")
                self.data.add("tmp_lhs")
                self.generate_expr(stmt.value)
                self.emit("STA tmp_val")
                self.data.add("tmp_val")
                self.emit("LDA tmp_lhs")
                self.emit("STA tmp_ptr")
                self.data.add("tmp_ptr")
                self.emit("LDA tmp_val")
                self.emit("STI tmp_ptr")
                
            elif isinstance(stmt.target, (FieldAccess, ArrowAccess)):
                self.gen_lvalue(stmt.target)
                self.emit("STA tmp_lhs")
                self.data.add("tmp_lhs")
                self.generate_expr(stmt.value)
                self.emit("STA tmp_val")
                self.data.add("tmp_val")
                self.emit("LDA tmp_lhs")
                self.emit("STA tmp_ptr")
                self.data.add("tmp_ptr")
                self.emit("LDA tmp_val")
                self.emit("STI tmp_ptr")
            else:
                raise CodeGenError("Atribuição inválida")

        # ~ elif isinstance(stmt, Return):
            # ~ if stmt.value is None:
                # ~ zero = self.get_const_label(0)
                # ~ self.emit(f'LDA {zero}')
                # ~ self.emit('SOP PUSH_OP')
            # ~ else:
                # ~ if isinstance(stmt.value.vartype, StructType):
                    # ~ struct_type = stmt.value.vartype
                    # ~ size = self.structs[struct_type.name]["size"]
                    # ~ if isinstance(stmt.value, Call):
                        # ~ self.generate_expr(stmt.value)
                    # ~ else:
                        # ~ self.gen_lvalue(stmt.value) 
                    # ~ self.emit("STA tmp_ptr_src")
                    # ~ self.data.add("tmp_ptr_src")
                    # ~ for i in range(size):
                        # ~ self.emit("LDA tmp_ptr_src") 
                        # ~ if i > 0:
                            # ~ off = self.get_const_label(i)
                            # ~ self.emit(f"ADD {off}")
                        # ~ self.emit("STA tmp_ptr")
                        # ~ self.data.add("tmp_ptr")
                        # ~ self.emit("LDI tmp_ptr")
                        # ~ self.emit("SOP PUSH_OP")
                # ~ else:
                    # ~ self.generate_expr(stmt.value)
                    # ~ self.emit('SOP PUSH_OP')
            
            # ~ if self.func_exit_label:
                # ~ self.emit(f"JMP {self.func_exit_label}")

        elif isinstance(stmt, Return):
            if stmt.value is None:
                if not self.current_function.is_naked:
                    self.emit("SOP POP_OP")
                    self.emit("STA tmp_left")
                
                zero = self.get_const_label(0)
                self.emit(f'LDA {zero}')
                self.emit('SOP PUSH_OP')
                
                if not self.current_function.is_naked:
                    self.emit("LDA tmp_left")
                    self.emit("SOP PUSH_OP")
            else:
                if isinstance(getattr(stmt.value, 'vartype', None), StructType):
                    struct_type = stmt.value.vartype
                    size = self.structs[struct_type.name]["size"]
                    if isinstance(stmt.value, Call):
                        self.generate_expr(stmt.value)
                    else:
                        self.gen_lvalue(stmt.value) 
                    self.emit("STA tmp_ptr_src")
                    self.data.add("tmp_ptr_src")
                    
                    if not self.current_function.is_naked:
                        self.emit("SOP POP_OP")
                        self.emit("STA tmp_left")

                    for i in range(size):
                        self.emit("LDA tmp_ptr_src") 
                        if i > 0:
                            off = self.get_const_label(i)
                            self.emit(f"ADD {off}")
                        self.emit("STA tmp_ptr")
                        self.data.add("tmp_ptr")
                        self.emit("LDI tmp_ptr")
                        self.emit("SOP PUSH_OP")
                        
                    if not self.current_function.is_naked:
                        self.emit("LDA tmp_left")
                        self.emit("SOP PUSH_OP")
                else:
                    self.generate_expr(stmt.value)
                    self.emit('STA tmp_val') # Salva resultado do AC
                    
                    if not self.current_function.is_naked:
                        self.emit("SOP POP_OP")
                        self.emit("STA tmp_left") # Salva RetAddr
                        
                    self.emit('LDA tmp_val')
                    self.emit('SOP PUSH_OP') # Empilha o valor
                    
                    if not self.current_function.is_naked:
                        self.emit("LDA tmp_left")
                        self.emit("SOP PUSH_OP") # Devolve o RetAddr
            
            # Retorna imediatamente (já não usa JMP para a label global)
            self.emit("RET")

        elif isinstance(stmt, If):
            label_then = self.new_label("bloco_then")
            label_else = self.new_label("bloco_else") if stmt.else_body else None
            label_end = self.new_label("fim_if")

            if isinstance(stmt.condition, BinaryOp):
                self.gen_condition(stmt.condition, label_then, label_else or label_end)
            else:
                # --- FIX CRÍTICO: Força atualização de flags (SUB 0) ---
                self.generate_expr(stmt.condition)
                zero = self.get_const_label(0)
                self.emit(f'SUB {zero}') # AC = AC - 0 (Flags atualizadas)
                self.emit(f'JZ {label_else or label_end}')
                self.emit(f'JMP {label_then}')

            self.emit(f'{label_then}:')
            for inner in stmt.then_body:
                self.generate_stmt(inner)
            self.emit(f'JMP {label_end}')

            if stmt.else_body:
                self.emit(f'{label_else}:')
                for inner in stmt.else_body:
                    self.generate_stmt(inner)
            self.emit(f'{label_end}:')

        elif isinstance(stmt, While):
            label_start = self.new_label("while_start")
            label_end = self.new_label("while_end")
            self.continue_labels.append(label_start)
            self.break_labels.append(label_end)
            self.emit(f'{label_start}:')
            
            if isinstance(stmt.condition, BinaryOp):
                self.gen_condition(stmt.condition, f"{label_start}_true", label_end)
                self.emit(f'{label_start}_true:')
            else:
                # --- FIX CRÍTICO: Força atualização de flags ---
                self.generate_expr(stmt.condition)
                zero = self.get_const_label(0)
                self.emit(f'SUB {zero}')
                self.emit(f'JZ {label_end}')

            for inner in stmt.body:
                self.generate_stmt(inner)
            self.emit(f'JMP {label_start}')
            self.emit(f'{label_end}:')
            self.continue_labels.pop()
            self.break_labels.pop()
        
        elif isinstance(stmt, Switch):
            # Cria a label de saída que os comandos 'break' vão utilizar
            label_end = self.new_label("switch_end")
            self.break_labels.append(label_end)
            
            # 1. Avalia a expressão principal do switch e salva num temporário exclusivo
            self.generate_expr(stmt.expr)
            
            # Garantimos um temporário único para este switch (permite switch aninhado)
            tmp_switch = f"tmp_sw_{self.label_counter}"
            self.data.add(tmp_switch)
            self.emit(f'STA {tmp_switch}')
            
            # 2. FASE DE DESPACHO (As comparações)
            case_labels = []
            default_label = None
            
            for case in stmt.cases:
                lbl = self.new_label("case")
                case_labels.append((case, lbl))
                
                if case.value is None:
                    default_label = lbl
                else:
                    self.emit(f'LDA {tmp_switch}')
                    const_lbl = self.get_const_label(case.value.value)
                    self.emit(f'SUB {const_lbl}')  # Testa se tmp_switch == case.value
                    self.emit(f'JZ {lbl}')         # Se sim, salta pro bloco do case
                    
            # Se não bateu em nenhum case, vai para o default (se existir) ou para o fim
            if default_label:
                self.emit(f'JMP {default_label}')
            else:
                self.emit(f'JMP {label_end}')
                
            # 3. FASE DOS CORPOS (A geração do código em si)
            # O "fallthrough" (vazamento de fluxo) acontece naturalmente porque os blocos
            # são gerados um após o outro sem JMP no final, a menos que haja um 'break'!
            for case, lbl in case_labels:
                self.emit(f'{lbl}:')
                for s in case.body:
                    self.generate_stmt(s)
                    
            # 4. FIM DO SWITCH
            self.emit(f'{label_end}:')
            self.break_labels.pop()
        
        elif isinstance(stmt, For):
            self.generate_stmt(stmt.init)
            
            label_start = self.new_label("for_start")
            label_inc = self.new_label("for_inc")  # <--- NOVO: Rótulo para o incremento
            label_end = self.new_label("for_end")
            
            # --- FIX: Em um 'for', o continue salta para o incremento, não para o início! ---
            self.continue_labels.append(label_inc) 
            self.break_labels.append(label_end)
            
            self.emit(f'{label_start}:')

            if isinstance(stmt.condition, BinaryOp):
                 self.gen_condition(stmt.condition, f"{label_start}_true", label_end)
                 self.emit(f'{label_start}_true:')
            else:
                self.generate_expr(stmt.condition)
                zero = self.get_const_label(0)
                self.emit(f'SUB {zero}')
                self.emit(f'JZ {label_end}')

            for inner in stmt.body:
                self.generate_stmt(inner)
                
            # O continue salta exatamente para aqui!
            self.emit(f'{label_inc}:')
            self.generate_stmt(stmt.increment)
            self.emit(f'JMP {label_start}')
            
            self.emit(f'{label_end}:')
            self.continue_labels.pop()
            self.break_labels.pop()

        elif isinstance(stmt, (Call, PreInc, PreDec, PostInc, PostDec)):
            self.generate_expr(stmt)
        elif isinstance(stmt, Break):
            self.emit(f'JMP {self.break_labels[-1]}')
        elif isinstance(stmt, Continue):
            self.emit(f'JMP {self.continue_labels[-1]}')
        elif isinstance(stmt, Asm):
            lines = stmt.code.split('\n')
            for ln in lines:
                if ln.strip(): self.emit(ln)

    def gen_condition(self, cond, label_true, label_false):
        # 1. Curto-circuito para AND (&&)
        if isinstance(cond, BinaryOp) and cond.op == '&&':
            lbl_next = self.new_label("and_next")
            # Se a esquerda for falsa, pula tudo e vai pro FALSO.
            # Se for verdadeira, pula pro lbl_next e avalia a direita.
            self.gen_condition(cond.left, lbl_next, label_false)
            self.emit(f'{lbl_next}:')
            self.gen_condition(cond.right, label_true, label_false)
            return

        # 2. Curto-circuito para OR (||)
        if isinstance(cond, BinaryOp) and cond.op == '||':
            lbl_next = self.new_label("or_next")
            # Se a esquerda for verdadeira, pula tudo e vai pro VERDADEIRO.
            # Se for falsa, pula pro lbl_next e avalia a direita.
            self.gen_condition(cond.left, label_true, lbl_next)
            self.emit(f'{lbl_next}:')
            self.gen_condition(cond.right, label_true, label_false)
            return

        # 3. Comparações Relacionais Padrão (==, !=, <, >, <=, >=)
        if isinstance(cond, BinaryOp) and cond.op in ('==', '!=', '<', '>', '<=', '>='):
            op = cond.op
            self.generate_expr(cond.left)
            self.emit('STA tmp_left_cond')
            self.data.add('tmp_left_cond')

            right = cond.right
            if isinstance(right, Var):
                self.emit('LDA tmp_left_cond')
                self.emit(f'SUB {self.symbol_table.resolve(right.name)}')
                self.data.add(self.symbol_table.resolve(right.name))
            elif isinstance(right, Const):
                self.emit('LDA tmp_left_cond')
                label = self.get_const_label(right.value)
                self.emit(f'SUB {label}')
            else:
                self.generate_expr(right)
                self.emit('STA tmp_right_cond')
                self.data.add('tmp_right_cond')
                self.emit('LDA tmp_left_cond')  
                self.emit('SUB tmp_right_cond') 

            if op == '==':
                self.emit(f'JZ {label_true}')
                self.emit(f'JMP {label_false}')
            elif op == '!=':
                self.emit(f'JZ {label_false}')
                self.emit(f'JMP {label_true}')
            elif op == '<':
                self.emit(f'JN {label_true}')
                self.emit(f'JMP {label_false}')
            elif op == '>':
                self.emit(f'JZ {label_false}')
                self.emit(f'JN {label_false}')
                self.emit(f'JMP {label_true}')
            elif op == '<=':
                self.emit(f'JN {label_true}')
                self.emit(f'JZ {label_true}')
                self.emit(f'JMP {label_false}')
            elif op == '>=':
                self.emit(f'JZ {label_true}')
                self.emit(f'JN {label_false}')
                self.emit(f'JMP {label_true}')
            return

        # 4. Fallback: Expressões booleanas simples (Ex: if (a), if (ptr), if (!a))
        self.generate_expr(cond)
        zero = self.get_const_label(0)
        self.emit(f'SUB {zero}')
        self.emit(f'JZ {label_false}')
        self.emit(f'JMP {label_true}')
    
    def new_label(self, base):
        self.label_counter += 1
        return f'{base}_{self.label_counter}'

    def generate_expr(self, expr):
        if hasattr(expr, 'lineno') and expr.lineno:
            self.current_line = expr.lineno
            
        if isinstance(expr, Var):
            resolved = self.symbol_table.resolve(expr.name)
            if expr.name in self.array_names:
                self.emit(f'MOV {resolved}') 
            else:
                self.emit(f'LDA {resolved}')

        elif isinstance(expr, StringLiteral):
            label = self.get_string_label(expr.value)
            self.emit(f"MOV {label}") 

        elif isinstance(expr, Const):
            label = self.get_const_label(expr.value)
            self.emit(f'LDA {label}')

        elif isinstance(expr, TypeCast):
            self.generate_expr(expr.expr)

        elif isinstance(expr, BinaryOp):
            
            # Suporte a Operadores Relacionais como Expressões (ex: int x = a == b;) ---
            if expr.op in ('==', '!=', '<', '>', '<=', '>=', '&&', '||'):
                lbl_true = self.new_label("rel_true")
                lbl_false = self.new_label("rel_false")
                lbl_end = self.new_label("rel_end")
                
                # Reutiliza a lógica de saltos já pronta do compilador
                self.gen_condition(expr, lbl_true, lbl_false)
                
                # Bloco VERDADEIRO: Carrega 1 no AC e pula pro fim
                self.emit(f'{lbl_true}:')
                self.emit(f'LDA {self.get_const_label(1)}')
                self.emit(f'JMP {lbl_end}')
                
                # Bloco FALSO: Carrega 0 no AC
                self.emit(f'{lbl_false}:')
                self.emit(f'LDA {self.get_const_label(0)}')
                
                self.emit(f'{lbl_end}:')
                return  # Sai da função para não executar o resto da matemática binária
            
            self.generate_expr(expr.left)
            self.emit('STA tmp_left')
            self.data.add('tmp_left')
            self.generate_expr(expr.right)
            self.emit('STA tmp_right')
            self.data.add('tmp_right')
            self.emit('LDA tmp_left')

            if expr.op == '+':
                # --- ARITMÉTICA DE PONTEIROS (Loop Unrolling) ---
                if getattr(expr, 'vartype', None) and isinstance(expr.vartype, PointerType):
                    base_size = self.sizeof(expr.vartype.base)
                    if base_size > 1:
                        if isinstance(expr.right.vartype, IntType):
                            self.emit('LDA tmp_right')
                            self.emit('STA tmp_step')
                            self.data.add('tmp_step')
                            for _ in range(base_size - 1):
                                self.emit('ADD tmp_step')
                            self.emit('STA tmp_right')
                            
                            # Restaura o AC que foi sujado pelo loop!
                            self.emit('LDA tmp_left')  
                            
                        elif isinstance(expr.left.vartype, IntType):
                            self.emit('LDA tmp_left')
                            self.emit('STA tmp_step')
                            self.data.add('tmp_step')
                            for _ in range(base_size - 1):
                                self.emit('ADD tmp_step')
                            self.emit('STA tmp_left')
                            
                            # Recarrega o novo tmp_left no AC!
                            self.emit('LDA tmp_left')  
                # ------------------------------------------------
                
                # A instrução final para TODOS os casos de soma (1 única linha!)
                self.emit('ADD tmp_right')

            elif expr.op == '-':
                # --- ARITMÉTICA DE PONTEIROS (Loop Unrolling) ---
                if getattr(expr, 'vartype', None) and isinstance(expr.vartype, PointerType):
                    base_size = self.sizeof(expr.vartype.base)
                    if base_size > 1 and isinstance(expr.right.vartype, IntType):
                        self.emit('LDA tmp_right')
                        self.emit('STA tmp_step')
                        self.data.add('tmp_step')
                        for _ in range(base_size - 1):
                            self.emit('ADD tmp_step')
                        self.emit('STA tmp_right')
                        
                        # Restaura o AC que foi sujado pelo loop!
                        self.emit('LDA tmp_left')  
                # ------------------------------------------------
                
                # A instrução final para TODOS os casos de subtração (1 única linha!)
                self.emit('SUB tmp_right')

            elif expr.op == '*':
                # 1. OTIMIZAÇÃO INTELIGENTE: Constante (Shift & Add Unrolling)
                if isinstance(expr.right, Const) and expr.right.literal_type == "int":
                    val = int(expr.right.value)
                    
                    if val == 0:
                        self.emit(f"LDA {self.get_const_label(0)}")
                        return
                    if val == 1:
                        self.generate_expr(expr.left)
                        return
                        
                    # Prepara a base 'A' e o Acumulador 'Res' = 0
                    self.generate_expr(expr.left)
                    self.emit('STA tmp_a_mul')
                    self.data.add('tmp_a_mul')
                    
                    self.emit(f"LDA {self.get_const_label(0)}")
                    self.emit('STA tmp_res_mul')
                    self.data.add('tmp_res_mul')
                    
                    # Decompõe o multiplicador nos bits ativados (Potências de 2)
                    shifts_done = 0
                    for bit_pos in range(val.bit_length()):
                        if (val & (1 << bit_pos)) != 0:
                            # Faz os deslocamentos necessários para alcançar esse bit
                            while shifts_done < bit_pos:
                                self.emit('LDA tmp_a_mul')
                                self.emit(f"SHIFT {self.get_const_label(1)}") # 1 = Left Shift
                                self.emit('STA tmp_a_mul')
                                shifts_done += 1
                                
                            # Soma a parcela ao resultado final
                            self.emit('LDA tmp_res_mul')
                            self.emit('ADD tmp_a_mul')
                            self.emit('STA tmp_res_mul')
                            
                    self.emit('LDA tmp_res_mul') # Retorna o resultado final no AC
                    return
                
                # Otimização comutativa: Se a esquerda for constante e a direita variável, inverte!
                elif isinstance(expr.left, Const) and expr.left.literal_type == "int":
                     expr.left, expr.right = expr.right, expr.left
                     self.generate_expr(expr)
                     return

                # 2. FALLBACK: Var x Var (Loop de Somas Sucessivas Inline)
                self.generate_expr(expr.left)
                self.emit('STA tmp_left_mul')
                self.data.add('tmp_left_mul')
                self.generate_expr(expr.right)
                self.emit('STA tmp_right_mul')
                self.data.add('tmp_right_mul')
                
                # --- FIX: Correção de Sinal para evitar Loop Infinito ---
                lbl_check_sign = self.new_label("mul_sign")
                lbl_start = self.new_label("mul_loop")
                lbl_end = self.new_label("mul_end")
                
                # Verifica se o multiplicador é negativo
                self.emit('LDA tmp_right_mul')
                self.emit(f"SUB {self.get_const_label(0)}")
                self.emit(f"JN {lbl_check_sign}")
                self.emit(f"JMP {lbl_start}")
                
                # Inverte o sinal da Direita e da Esquerda
                self.emit(f"{lbl_check_sign}:")
                self.emit(f"LDA {self.get_const_label(0)}")
                self.emit('SUB tmp_right_mul')
                self.emit('STA tmp_right_mul')
                self.emit(f"LDA {self.get_const_label(0)}")
                self.emit('SUB tmp_left_mul')
                self.emit('STA tmp_left_mul')
                # --------------------------------------------------------
                
                self.emit(f"{lbl_start}:")
                self.emit('LDA tmp_right_mul')
                self.emit(f"SUB {self.get_const_label(0)}") # Flag Check
                self.emit(f"JZ {lbl_end}")
                
                self.emit(f"SUB {self.get_const_label(1)}") # Multiplicador--
                self.emit('STA tmp_right_mul')
                
                self.emit('LDA tmp_res_mul')
                self.emit('ADD tmp_left_mul')
                self.emit('STA tmp_res_mul')
                self.emit(f"JMP {lbl_start}")
                
                self.emit(f"{lbl_end}:")
                self.emit('LDA tmp_res_mul')
                
            elif expr.op == '/':
                # 1. OTIMIZAÇÃO: Divisão por Constante Potência de 2
                if isinstance(expr.right, Const) and expr.right.literal_type == "int":
                    val = int(expr.right.value)
                    
                    if val == 0:
                        raise CodeGenError("Divisão por zero detectada em tempo de compilação!")
                    if val == 1:
                        self.generate_expr(expr.left)
                        return
                        
                    # Se for potência exata de 2 (ex: 2, 4, 8, 16), aplica SHIFT RIGHT direto
                    if (val & (val - 1)) == 0:
                        self.generate_expr(expr.left)
                        shift_amount = val.bit_length() - 1
                        for _ in range(shift_amount):
                            self.emit(f"SHIFT {self.get_const_label(0)}") # 0 = Right Shift
                        return

                # 2. FALLBACK: Var / Var (Loop de Subtrações Sucessivas)
                self.generate_expr(expr.left)
                self.emit('STA tmp_dividend')
                self.data.add('tmp_dividend')
                self.generate_expr(expr.right)
                self.emit('STA tmp_divisor')
                self.data.add('tmp_divisor')

                # --- FIX: Correção de Sinal para Divisão ---
                lbl_check_b = self.new_label("div_check_b")
                lbl_do_div = self.new_label("div_do")
                lbl_apply_sign = self.new_label("div_apply_sign")
                lbl_end = self.new_label("div_end")

                # Inicializa flag de sinal (0 = positivo, 1 = negativo)
                self.emit(f"LDA {self.get_const_label(0)}")
                self.emit('STA tmp_div_sign')
                self.data.add('tmp_div_sign')

                # Checa sinal do Dividendo (A)
                self.emit('LDA tmp_dividend')
                self.emit(f"SUB {self.get_const_label(0)}")
                self.emit(f"JZ {lbl_check_b}") # Se 0, é positivo
                self.emit(f"JN {self.new_label('div_a_neg')}") # Se negativo
                self.emit(f"JMP {lbl_check_b}")

                self.emit(f"{self.label_counter - 1}:") # div_a_neg
                # Inverte A e liga flag de sinal
                self.emit(f"LDA {self.get_const_label(0)}")
                self.emit('SUB tmp_dividend')
                self.emit('STA tmp_dividend')
                self.emit(f"LDA {self.get_const_label(1)}")
                self.emit('STA tmp_div_sign')

                self.emit(f"{lbl_check_b}:")
                # Checa sinal do Divisor (B)
                self.emit('LDA tmp_divisor')
                self.emit(f"SUB {self.get_const_label(0)}")
                self.emit(f"JZ {lbl_do_div}")
                self.emit(f"JN {self.new_label('div_b_neg')}")
                self.emit(f"JMP {lbl_do_div}")

                self.emit(f"{self.label_counter - 1}:") # div_b_neg
                # Inverte B e inverte a flag de sinal (XOR simulado)
                self.emit(f"LDA {self.get_const_label(0)}")
                self.emit('SUB tmp_divisor')
                self.emit('STA tmp_divisor')
                self.emit(f"LDA {self.get_const_label(1)}")
                self.emit('SUB tmp_div_sign') # 1 - 0 = 1 (neg), 1 - 1 = 0 (pos)
                self.emit('STA tmp_div_sign')

                self.emit(f"{lbl_do_div}:")
                # -------------------------------------------
                
                # Executa divisão garantidamente com números positivos
                self.emit('LDA tmp_dividend')
                self.emit('STA tmp_rem')
                self.data.add('tmp_rem')
                
                self.emit(f"LDA {self.get_const_label(0)}")
                self.emit('STA tmp_res_div')
                self.data.add('tmp_res_div')
                
                lbl_start = self.new_label("div_loop")
                self.emit(f"{lbl_start}:")
                self.emit('LDA tmp_rem')
                self.emit('SUB tmp_divisor')
                self.emit(f"JN {lbl_apply_sign}") # Se Resto < Divisor, a divisão acabou
                
                self.emit('STA tmp_rem')
                self.emit('LDA tmp_res_div')
                self.emit(f"ADD {self.get_const_label(1)}")
                self.emit('STA tmp_res_div')
                self.emit(f"JMP {lbl_start}")
                
                self.emit(f"{lbl_apply_sign}:")
                # Aplica o sinal correto ao Quociente final
                self.emit('LDA tmp_div_sign')
                self.emit(f"SUB {self.get_const_label(0)}")
                self.emit(f"JZ {lbl_end}") # Se 0, já é positivo, terminou
                
                # Se 1, inverte o resultado
                self.emit(f"LDA {self.get_const_label(0)}")
                self.emit('SUB tmp_res_div')
                self.emit('STA tmp_res_div')
                
                self.emit(f"{lbl_end}:")
                self.emit('LDA tmp_res_div')
            
            # --- BITWISE AND (&) ---
            # A & B = ~(~(A & B)) = (A NAND B) NAND (A NAND B)
            elif expr.op == '&':
                self.emit('NAND tmp_right')
                self.emit('STA tmp_and')
                self.data.add('tmp_and')
                self.emit('NAND tmp_and') 
                
            # --- BITWISE OR (|) ---
            # A | B = ~(~A & ~B) = (~A) NAND (~B) = (A NAND A) NAND (B NAND B)
            elif expr.op == '|':
                self.emit('NAND tmp_left')
                self.emit('STA tmp_not_a')
                self.data.add('tmp_not_a')
                
                self.emit('LDA tmp_right')
                self.emit('NAND tmp_right')
                self.emit('STA tmp_not_b')
                self.data.add('tmp_not_b')
                
                self.emit('LDA tmp_not_a')
                self.emit('NAND tmp_not_b')

            # --- BITWISE SHIFT (<< e >>) ---
            # Realiza um loop decrementando B até zero, executando SHIFT a cada ciclo
            elif expr.op in ('<<', '>>'):
                lbl_start = self.new_label("shift_start")
                lbl_end = self.new_label("shift_end")
                
                self.emit(f'{lbl_start}:')
                self.emit('LDA tmp_right')      # Carrega o contador B
                zero = self.get_const_label(0)
                self.emit(f'SUB {zero}')        # Atualiza as flags
                self.emit(f'JZ {lbl_end}')      # Se B == 0, encerra
                
                # Decrementa o contador B (B = B - 1)
                one = self.get_const_label(1)
                self.emit(f'SUB {one}')
                self.emit('STA tmp_right')
                
                # Aplica o SHIFT no valor de A
                self.emit('LDA tmp_left')
                dir_lbl = self.get_const_label(1) if expr.op == '<<' else self.get_const_label(0)
                self.emit(f'SHIFT {dir_lbl}')   # Passa ponteiro 1 (Esquerda) ou 0 (Direita)
                self.emit('STA tmp_left')       # Salva A atualizado
                
                self.emit(f'JMP {lbl_start}')
                self.emit(f'{lbl_end}:')
                self.emit('LDA tmp_left')       # Retorna A atualizado no AC

            # --- BITWISE XOR (^) ---
            elif expr.op == '^':
                # T1 = A NAND B
                self.emit('LDA tmp_left')
                self.emit('NAND tmp_right')
                self.emit('STA tmp_t1')
                self.data.add('tmp_t1')
                
                # T2 = A NAND T1
                self.emit('LDA tmp_left')
                self.emit('NAND tmp_t1')
                self.emit('STA tmp_t2')
                self.data.add('tmp_t2')
                
                # T3 = B NAND T1
                self.emit('LDA tmp_right')
                self.emit('NAND tmp_t1')
                self.emit('STA tmp_t3')
                self.data.add('tmp_t3')
                
                # Res = T2 NAND T3
                self.emit('LDA tmp_t2')
                self.emit('NAND tmp_t3')
                
            else: raise CodeGenError(f"Operador '{expr.op}' não suportado")

        elif isinstance(expr, Call):
            is_direct = False
            callee_label = None
            if isinstance(expr.callee, Var):
                try:
                    self.symbol_table.resolve(expr.callee.name)
                    is_direct = False
                except CodeGenError:
                    is_direct = True
                    callee_label = expr.callee.name
                    self.required_libraries.add(callee_label)
            else:
                is_direct = False

            for arg in expr.args:
                if isinstance(arg.vartype, StructType):
                    if isinstance(arg, Call):
                         self.generate_expr(arg) 
                         self.emit("STA tmp_ptr_src")
                    else:
                        self.gen_lvalue(arg)
                        self.emit("STA tmp_ptr_src")
                    
                    self.data.add("tmp_ptr_src")
                    size = self.structs[arg.vartype.name]["size"]
                    for i in range(size):
                        self.emit("LDA tmp_ptr_src")
                        if i > 0: self.emit(f"ADD {self.get_const_label(i)}")
                        self.emit("STA tmp_ptr")
                        self.data.add("tmp_ptr")
                        self.emit("LDI tmp_ptr")
                        self.emit("SOP PUSH_OP")
                else:
                    self.generate_expr(arg)
                    self.emit('SOP PUSH_OP')

            if is_direct:
                self.emit(f'CALL {callee_label}')
            else:
                self.generate_expr(expr.callee)
                self.emit("STA tmp_ptr_fn")
                self.data.add("tmp_ptr_fn")
                ret_label = self.new_label("ret_indirect")
                self.emit(f"MOV {ret_label}")
                self.emit("SOP PUSH_OP")
                self.emit("LDA tmp_ptr_fn")
                self.emit("SOP PUSH_OP")
                self.emit("RET")
                self.emit(f"{ret_label}:")

            if isinstance(expr.vartype, StructType):
                size = self.structs[expr.vartype.name]["size"]
                temp_ret_name = self.symbol_table.declare(f"struct_ret_{self.label_counter}") 
                self.label_counter += 1
                self.local_bss.append((temp_ret_name, size, "RESD"))
                for i in reversed(range(size)):
                    self.emit("SOP POP_OP")
                    self.emit("STA tmp_val_pop")
                    self.data.add("tmp_val_pop")
                    self.emit(f"MOV {temp_ret_name}")
                    if i > 0: self.emit(f"ADD {self.get_const_label(i)}")
                    self.emit("STA tmp_ptr")
                    self.data.add("tmp_ptr")
                    self.emit("LDA tmp_val_pop")
                    self.emit("STI tmp_ptr")
                self.emit(f"MOV {temp_ret_name}")
            else:
                self.emit('SOP POP_OP')

        elif isinstance(expr, AddressOf):
            if isinstance(expr.var, Var):
                 try:
                     self.gen_lvalue(expr.var)
                 except CodeGenError:
                     self.emit(f"MOV {expr.var.name}") 
            else:
                self.gen_lvalue(expr.var)
            
        elif isinstance(expr, Deref):
            self.generate_expr(expr.ptr)
            self.emit('STA tmp_ptr')
            self.emit('LDI tmp_ptr')
            self.data.add('tmp_ptr')
            
        elif isinstance(expr, UnaryOp):
            if expr.op == '-':
                self.generate_expr(expr.expr)
                self.emit('STA tmp_val')
                self.data.add('tmp_val')
                zero = self.get_const_label(0)
                self.emit(f'LDA {zero}')
                self.emit('SUB tmp_val')
            elif expr.op == '+':
                # O unário '+' não altera o valor, basta gerar a expressão normalmente!
                self.generate_expr(expr.expr)
            elif expr.op == '~':
                self.generate_expr(expr.expr)
                self.emit('STA tmp_val')
                self.data.add('tmp_val')
                # ~A = A NAND A
                self.emit('NAND tmp_val')
            elif expr.op == '!':
                self.generate_expr(expr.expr) # Resultado fica no Acumulador (AC)
                
                zero = self.get_const_label(0)
                one = self.get_const_label(1)
                lbl_is_zero = self.new_label("not_is_zero")
                lbl_end = self.new_label("not_end")
                
                # Força a atualização da flag Z (Zero) na máquina virtual
                self.emit(f'SUB {zero}')
                self.emit(f'JZ {lbl_is_zero}')
                
                # --- CASO FALSO (A expressão NÃO era zero) ---
                # O resultado lógico de !N é 0
                self.emit(f'LDA {zero}')
                self.emit(f'JMP {lbl_end}')
                
                # --- CASO VERDADEIRO (A expressão era zero) ---
                self.emit(f'{lbl_is_zero}:')
                # O resultado lógico de !0 é 1
                self.emit(f'LDA {one}')
                
                self.emit(f'{lbl_end}:')
                # Ao final, o AC terá 0 ou 1
            
            
            else: raise CodeGenError(f"Operador unário '{expr.op}' não suportado")
        
        # ---------------------------------------------------------
        # INCREMENTO E DECREMENTO (++, --)
        # ---------------------------------------------------------
        elif isinstance(expr, (PreInc, PreDec, PostInc, PostDec)):
            # 1. Aritmética de Ponteiros: Calcula o tamanho do salto
            step_size = 1
            if hasattr(expr.target, 'vartype') and isinstance(expr.target.vartype, PointerType):
                try:
                    step_size = self.sizeof(expr.target.vartype.base)
                except CodeGenError:
                    step_size = 1 # Fallback de segurança
            
            step_label = self.get_const_label(step_size)

            # 2. Descobre o endereço da variável na memória
            self.gen_lvalue(expr.target)
            self.emit('STA tmp_ptr')
            self.data.add('tmp_ptr')
            
            # 3. Carrega o valor atual da variável no Acumulador
            self.emit('LDI tmp_ptr')

            # --- SUFIXO (Post): Salva o valor antigo antes de alterar ---
            if isinstance(expr, (PostInc, PostDec)):
                self.emit('STA tmp_old_val')
                self.data.add('tmp_old_val')

            # 4. Executa a Matemática (Soma ou Subtrai o step_size)
            if isinstance(expr, (PreInc, PostInc)):
                self.emit(f'ADD {step_label}')
            else:
                self.emit(f'SUB {step_label}')

            # 5. Salva o novo valor de volta na memória
            self.emit('STI tmp_ptr')

            # --- SUFIXO (Post): Restaura o valor antigo para a expressão exterior ---
            if isinstance(expr, (PostInc, PostDec)):
                self.emit('LDA tmp_old_val')
            
            # Nota: No caso de PREFIXO (Pre), o Acumulador naturalmente 
            # já retém o novo valor calculado no passo 4, então não precisamos fazer nada!
        
        elif isinstance(expr, ArrayAccess):
            self.gen_array_element_address(expr)
            self.emit("STA tmp_ptr")
            self.data.add("tmp_ptr")
            self.emit("LDI tmp_ptr")
        elif isinstance(expr, (FieldAccess, ArrowAccess)):
            self.gen_lvalue(expr)
            if not isinstance(expr.vartype, ArrayType):
                self.emit("STA tmp_ptr")
                self.emit("LDI tmp_ptr")

    def get_const_label(self, value):
        if isinstance(value, str):
            s = value.strip("'").strip('"')
            if s.isdigit(): value = int(s)
        key = (type(value), value)
        if key in self.constants: return self.constants[key][0]
        
        kind = "DD"
        raw = str(value)
        if not isinstance(value, int):
            s = str(value).strip("'").strip('"')
            if len(s) == 1 and not s.isdigit():
                kind = "DB"
                raw = str(ord(s[0]))  # <--- FIX: Agora envia o número ASCII
            elif s.isdigit():
                kind = "DD"
                raw = s
            else:
                 kind = "DB"
                 raw = str(ord(s[0])) if len(s) > 0 else "0" # <--- FIX
        
        safe = self.sanitize_const_name(value)
        label = f"prog_const_{safe}"
        self.constants[key] = (label, kind, raw)
        return label
        
    def get_string_label(self, value):
        if value in self.strings: return self.strings[value]
        label = f"prog_str_{self.string_count}"
        self.string_count += 1
        val_bytes = self.string_to_bytes(value)
        if not hasattr(self, "all_string_data"): self.all_string_data = []
        self.all_string_data.append((label, val_bytes, "INITB"))
        self.strings[value] = label
        return label

    def generate_function(self, func):
        self.current_function = func
        
        self.emit(f'{func.name}:')
        self.symbol_table.enter_function(func.name)
        self.func_exit_label = f"fim_func_{func.name}"

        if func.is_naked:
            for stmt in func.body:
                self.generate_stmt(stmt)
            self.symbol_table.leave_function()
            return 
        
        self.local_data = []
        self.local_bss = []
        
        tmp_ret = None
        if func.name != "main":
            # ~ tmp_ret = self.symbol_table.declare("retaddr")
            # ~ self.data.add(tmp_ret)
            # ~ self.emit("SOP POP_OP")
            # ~ self.emit(f"STA {tmp_ret}")
            
            # 1. Tira o RetAddr e guarda num temporário protegido pelo Kernel
            self.emit("SOP POP_OP")
            self.emit("STA tmp_left")
            self.data.add("tmp_left")
            
            # ~ for param in reversed(func.params):
                # ~ pname = param.name
                # ~ scoped = self.symbol_table.declare(pname)
                # ~ size = self.sizeof(param.vartype)
                # ~ kind = "RESB" if isinstance(param.vartype, CharType) else "RESD"
                # ~ self.local_bss.append((scoped, size, kind))
                
                # ~ if isinstance(param.vartype, StructType):
                    # ~ for i in reversed(range(size)):
                        # ~ self.emit("SOP POP_OP")
                        # ~ self.emit("STA tmp_val_pop")
                        # ~ self.data.add("tmp_val_pop")
                        # ~ self.emit(f"MOV {scoped}")
                        # ~ if i > 0: self.emit(f"ADD {self.get_const_label(i)}")
                        # ~ self.emit("STA tmp_ptr")
                        # ~ self.data.add("tmp_ptr")
                        # ~ self.emit("LDA tmp_val_pop")
                        # ~ self.emit("STI tmp_ptr")
                # ~ else:
                    # ~ self.emit("SOP POP_OP")
                    # ~ self.emit(f"STA {scoped}")
                    # ~ self.data.add(scoped)
            
            for param in reversed(func.params):
                pname = param.name
                scoped = self.symbol_table.declare(pname)
                size = self.sizeof(param.vartype)
                kind = "RESB" if isinstance(param.vartype, CharType) else "RESD"
                self.local_bss.append((scoped, size, kind))
                
                if isinstance(param.vartype, StructType):
                    for i in reversed(range(size)):
                        self.emit("SOP POP_OP")
                        self.emit("STA tmp_val_pop")
                        self.data.add("tmp_val_pop")
                        self.emit(f"MOV {scoped}")
                        if i > 0: self.emit(f"ADD {self.get_const_label(i)}")
                        self.emit("STA tmp_ptr")
                        self.data.add("tmp_ptr")
                        self.emit("LDA tmp_val_pop")
                        self.emit("STI tmp_ptr")
                else:
                    self.emit("SOP POP_OP")
                    self.emit(f"STA {scoped}")
                    self.data.add(scoped)

            # 2. MÁGICA: Devolve o Endereço de Retorno para o topo da pilha!
            self.emit("LDA tmp_left")
            self.emit("SOP PUSH_OP")

        # FASE 1: Alocação (BSS)
        declared = set()
        for stmt in func.body:
            if isinstance(stmt, VarDecl):
                for entry in stmt.names:
                    if isinstance(entry, tuple):
                        if len(entry) == 4: raw_name, _, _, init = entry
                        elif len(entry) == 2: raw_name, init = entry
                    else: raw_name, init = entry, None
                    
                    name = raw_name.lstrip('*')
                    if name in declared: continue
                    declared.add(name)
                    scoped = self.symbol_table.declare(name)
                    
                    try:
                        size = self.sizeof(stmt.vartype)
                    except:
                        size = 1
                    is_char_array = (hasattr(stmt.vartype, 'base') and isinstance(stmt.vartype.base, CharType))
                    kind = "RESB" if isinstance(stmt.vartype, CharType) or is_char_array else "RESD"
                    self.local_bss.append((scoped, size, kind))
                        
            elif isinstance(stmt, ArrayDecl):
                name = stmt.name
                self.array_names.add(name)
                if name in declared: continue
                declared.add(name)
                scoped = self.symbol_table.declare(name)
                
                # --- FIX: Verifica se a inicialização exige tempo de execução ---
                has_vars = False
                if stmt.init:
                    has_vars = any(not isinstance(v, (Const, StringLiteral, UnaryOp)) for v in stmt.init)
                
                if stmt.init and len(stmt.init) > 0:
                    is_char = isinstance(stmt.arrtype.base, CharType)
                    if len(stmt.init) == 1 and isinstance(stmt.init[0], StringLiteral):
                        bytes_vals = self.string_to_bytes(stmt.init[0].value)
                        self.local_data.append((scoped, bytes_vals, "INITB"))
                    else:
                        # --- FIX: Desembrulha Local ---
                        values = []
                        for v in stmt.init:
                            if hasattr(v, 'op') and v.op in ('-', '+') and hasattr(v, 'expr'):
                                sign = -1 if v.op == '-' else 1
                                val = int(v.expr.value) if getattr(v.expr, 'literal_type', '') == "int" else v.expr.value
                                values.append(sign * val)
                            elif hasattr(v, 'value'):
                                values.append(int(v.value) if getattr(v, 'literal_type', '') == "int" else v.value)
                            else:
                                values.append(v)
                        kind = "INITB" if is_char else "INITD"
                        self.local_data.append((scoped, values, kind))
                else:
                    # Se tiver variáveis (ou não tiver init), aloca vazio na FASE 1 (.bss)
                    size = stmt.arrtype.size
                    if isinstance(stmt.arrtype.base, StructType):
                         size *= self.structs[stmt.arrtype.base.name]["size"]
                         self.local_bss.append((scoped, size, "RESD"))
                    elif isinstance(stmt.arrtype.base, CharType):
                        self.local_bss.append((scoped, size, "RESB"))
                    else:
                        self.local_bss.append((scoped, size, "RESD"))
                        
        # FASE 2: Reset Dinâmico
        for stmt in func.body:
            if isinstance(stmt, VarDecl):
                for entry in stmt.names:
                    if isinstance(entry, tuple):
                        if len(entry) == 4: raw_name, _, _, init = entry
                        elif len(entry) == 2: raw_name, init = entry
                    else: raw_name, init = entry, None
                    
                    if init is not None:
                        val_node = init[0]
                        name = raw_name.lstrip('*')
                        self.generate_expr(val_node)
                        self.emit(f"STA {self.symbol_table.resolve(name)}")
            
            elif isinstance(stmt, ArrayDecl):
                # --- FIX: Se o array tem variáveis, inicializa-o em Tempo de Execução ---
                has_vars = False
                if stmt.init:
                    has_vars = any(not isinstance(v, (Const, StringLiteral, UnaryOp)) for v in stmt.init)
                    
                if stmt.init and has_vars:
                    scoped = self.symbol_table.resolve(stmt.name)
                    for i, elem in enumerate(stmt.init):
                        self.emit(f"MOV {scoped}")
                        if i > 0: self.emit(f"ADD {self.get_const_label(i)}")
                        self.emit("STA tmp_ptr")
                        self.data.add("tmp_ptr")
                        
                        self.generate_expr(elem)
                        self.emit("STI tmp_ptr")
            
            else:
                self.generate_stmt(stmt)

        self.symbol_table.leave_function()
        self.emit(f"{self.func_exit_label}:")
        
        # ~ if func.rettype is None and not self.has_explicit_return(func):
            # ~ zero = self.get_const_label(0)
            # ~ self.emit(f'LDA {zero}')
            # ~ self.emit('SOP PUSH_OP')
            
        # ~ if func.name == 'main':
            # ~ self.emit("INT HALT_INT")
        # ~ else:
            # ~ self.emit(f"LDA {tmp_ret}")
            # ~ self.emit("SOP PUSH_OP")
            # ~ self.emit("RET")
        
        if func.name == 'main':
            self.emit("INT HALT_INT")
        elif func.rettype is None and not self.has_explicit_return(func):
            # Funções void sem return explícito
            self.emit("SOP POP_OP")
            self.emit("STA tmp_left")
            
            zero = self.get_const_label(0)
            self.emit(f'LDA {zero}')
            self.emit('SOP PUSH_OP')
            
            self.emit("LDA tmp_left")
            self.emit("SOP PUSH_OP")
            self.emit("RET")
        elif not self.has_explicit_return(func):
            self.emit("RET")
        
            
        if not hasattr(self, "all_local_data"): self.all_local_data = []
        if not hasattr(self, "all_local_bss"): self.all_local_bss = []
        self.all_local_data.extend(self.local_data)
        self.all_local_bss.extend(self.local_bss)

    def load_external_library(self, func_name):
        filename = os.path.join(self.library_path, f"{func_name}.cariri")
        if not os.path.exists(filename): return None
        
        with open(filename, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f.readlines()]
        
        lib_prefix = f"lib_{func_name}_"
        renamed = []
        if not hasattr(self, 'library_constants'): self.library_constants = {}
        const_pattern = re.compile(r'\bconst_(\d+)\b')
        for ln in lines:
            for t in self.known_temps:
                if t in ln:
                    ln = ln.replace(t, lib_prefix + t)
                    self.data.add(lib_prefix + t)
            def repl_const(m):
                n = m.group(1)
                new_label = f"{lib_prefix}const_{n}"
                self.library_constants[new_label] = int(n)
                return new_label
            ln = const_pattern.sub(repl_const, ln)
            renamed.append(ln)
        return renamed

    def has_explicit_return(self, func):
        for stmt in func.body:
            if self.contains_return(stmt): return True
        return False

    def contains_return(self, stmt):
        from ast import Return, If, While, For
        if isinstance(stmt, Return): return True
        if isinstance(stmt, If):
            return (any(self.contains_return(s) for s in stmt.then_body) or
                    any(self.contains_return(s) for s in stmt.else_body or []))
        if isinstance(stmt, While): return any(self.contains_return(s) for s in stmt.body)
        if isinstance(stmt, For): return any(self.contains_return(s) for s in stmt.body)
        return False

    def format_char_literal(self, value):
        if isinstance(value, int):
            return str(value)
        s = str(value).strip("'").strip('"')
        if len(s) == 0: return "0"
        return str(ord(s[0]))

    def sizeof(self, t):
        if isinstance(t, IntType): return 1
        if isinstance(t, CharType): return 1
        if isinstance(t, PointerType): return 1
        if isinstance(t, ArrayType): return t.size * self.sizeof(t.base)
        if isinstance(t, StructType):
            if t.name not in self.structs: raise CodeGenError(f"struct '{t.name}' desconhecido")
            return self.structs[t.name]["size"]
        raise CodeGenError(f"sizeof não suportado para tipo {t}")

    def gen_lvalue(self, expr):
        if isinstance(expr, Var):
            self.emit(f"MOV {self.symbol_table.resolve(expr.name)}")
        elif isinstance(expr, ArrayAccess):
            self.gen_array_element_address(expr)
        elif isinstance(expr, FieldAccess):
            self.gen_lvalue(expr.base)
            struct_name = expr.base.vartype.name
            offset = self.structs[struct_name]["fields"][expr.field]
            if offset != 0: self.emit(f"ADD {self.get_const_label(offset)}")
        elif isinstance(expr, ArrowAccess):
            self.generate_expr(expr.base)
            struct_name = expr.base.vartype.base.name
            offset = self.structs[struct_name]["fields"][expr.field]
            if offset != 0: self.emit(f"ADD {self.get_const_label(offset)}")
        elif isinstance(expr, Deref):
            self.generate_expr(expr.ptr)
        else:
            raise CodeGenError("Expressão não é lvalue.")

    def gen_array_element_address(self, expr):
        arr_t = expr.array.vartype
        if arr_t is None: raise CodeGenError("Array sem tipo.")
        if isinstance(arr_t, ArrayType): base_type = arr_t.base
        elif isinstance(arr_t, PointerType): base_type = arr_t.base
        else: raise CodeGenError("Indexação inválida.")
        
        elem_size = self.sizeof(base_type)
        if isinstance(arr_t, ArrayType):
            self.gen_lvalue(expr.array)
            self.emit("STA tmp_arr_base")
        else:
            self.generate_expr(expr.array)
            self.emit("STA tmp_arr_base")
        self.data.add("tmp_arr_base")
        
        # --- OTIMIZAÇÃO: Resolução Estática de Índices ---
        if hasattr(expr.index, 'value') and str(expr.index.value).lstrip('-').isdigit():
            offset = int(expr.index.value) * elem_size
            self.emit("LDA tmp_arr_base")
            if offset > 0:
                self.emit(f"ADD {self.get_const_label(offset)}")
            return
        # -------------------------------------------------

        self.generate_expr(expr.index)
        
        if elem_size > 1:
            self.emit("STA tmp_a_mul")
            self.data.add("tmp_a_mul")
            self.emit(f"LDA {self.get_const_label(0)}")
            self.emit("STA tmp_res_mul")
            self.data.add("tmp_res_mul")
            
            shifts_done = 0
            for bit_pos in range(elem_size.bit_length()):
                if (elem_size & (1 << bit_pos)) != 0:
                    while shifts_done < bit_pos:
                        self.emit('LDA tmp_a_mul')
                        self.emit(f"SHIFT {self.get_const_label(1)}")
                        self.emit('STA tmp_a_mul')
                        shifts_done += 1
                    self.emit('LDA tmp_res_mul')
                    self.emit('ADD tmp_a_mul')
                    self.emit('STA tmp_res_mul')
            self.emit('LDA tmp_res_mul')
            
        self.emit("ADD tmp_arr_base")
        
    def gen_struct_assignment(self, stmt):
        struct_t = stmt.target.vartype
        struct_name = struct_t.name
        size = self.structs[struct_name]["size"]
        self.gen_lvalue(stmt.target)
        self.emit("STA tmp_dst")
        self.data.add("tmp_dst")
        
        if isinstance(stmt.value, Call): self.generate_expr(stmt.value)
        else: self.gen_lvalue(stmt.value)
        self.emit("STA tmp_src")
        self.data.add("tmp_src")
        
        for i in range(size):
            if i != 0:
                off = self.get_const_label(i)
                self.emit(f"LDA tmp_src")
                self.emit(f"ADD {off}")
                self.emit("STA tmp_ptr")
            else:
                self.emit("LDA tmp_src")
                self.emit("STA tmp_ptr")
            self.emit("LDI tmp_ptr")
            self.emit("STA tmp_val")
            self.data.add("tmp_val")
            
            if i != 0:
                self.emit(f"LDA tmp_dst")
                self.emit(f"ADD {off}")
                self.emit("STA tmp_ptr")
            else:
                self.emit("LDA tmp_dst")
                self.emit("STA tmp_ptr")
            self.emit("LDA tmp_val")
            self.emit("STI tmp_ptr")

    def prune_dead_functions(self, program):
        """
        Eliminação de Funções Mortas (Dead Function Elimination)
        com Poda Inteligente de Roteamento de Syscalls para o CompSysLab.
        """
        all_functions = {f.name: f for f in program.items if isinstance(f, Function)}

        # =================================================================
        # HACK DO COMPSYSLAB: PODA DE SYSCALLS (OS Kernel Space)
        # =================================================================
        
        # 1. Mapa de IDs das Syscalls para os nomes dos Wrappers no User Space
        syscall_wrappers = {
            1: 'exit', 2: 'wait', 3: 'kill', 4: 'sem_lock', 5: 'sem_unlock',
            6: 'spawn',
            7: 'sys_mutex_trylock', 8: 'mutex_unlock',
            9: 'yield', 10: 'print_char', 11: 'read_char', 12: 'sleep',
            13: 'alarm', 14: 'pause', 15: 'signal', 16: 'sigreturn', 17: 'get_signal',
            20: 'write_pipe', 21: 'read_pipe', 25: 'shmget',
            27: 'msg_send', 28: 'msg_recv'
        }

        used_wrappers = set()

        # 2. Rastreador para descobrir quais syscalls as Tasks realmente usam
        def scan_used_wrappers(node):
            if node is None or isinstance(node, (int, str, bool, float)): return
            if isinstance(node, list):
                for item in node: scan_used_wrappers(item)
                return

            if isinstance(node, Call) and isinstance(node.callee, Var):
                if node.callee.name in syscall_wrappers.values():
                    used_wrappers.add(node.callee.name)

            if isinstance(node, Asm):
                for w in syscall_wrappers.values():
                    if re.search(rf'\b{w}\b', node.code):
                        used_wrappers.add(w)

            if hasattr(node, '__dict__'):
                for key, val in vars(node).items():
                    if key not in ('lineno', 'colno', 'end_lineno', 'end_colno'):
                        scan_used_wrappers(val)

        # Varre todas as funções EXCETO a main (que é o SO)
        for f_name, f_node in all_functions.items():
            if f_name != 'main': 
                scan_used_wrappers(f_node.body)

        # --- DESVINCULAÇÃO COMPLETA DE HANDLERS DO KERNEL ---
        
        # IPC (Pipes, Memória Compartilhada e Mensagens)
        if 'write_pipe' not in used_wrappers and 'kernel_write_pipe' in all_functions:
            del all_functions['kernel_write_pipe']
        if 'read_pipe' not in used_wrappers and 'kernel_read_pipe' in all_functions:
            del all_functions['kernel_read_pipe']
        if 'shmget' not in used_wrappers and 'kernel_shmget' in all_functions:
            del all_functions['kernel_shmget']
        if 'msg_send' not in used_wrappers and 'kernel_msg_send' in all_functions:
            del all_functions['kernel_msg_send']
        if 'msg_recv' not in used_wrappers and 'kernel_msg_recv' in all_functions:
            del all_functions['kernel_msg_recv']

        # Processos e Sincronização
        if 'spawn' not in used_wrappers and 'kernel_spawn' in all_functions:
            del all_functions['kernel_spawn']
        if 'wait' not in used_wrappers and 'kernel_wait' in all_functions:
            del all_functions['kernel_wait']
        if 'sem_lock' not in used_wrappers and 'kernel_sem_lock' in all_functions:
            del all_functions['kernel_sem_lock']
        if 'sem_unlock' not in used_wrappers and 'kernel_sem_unlock' in all_functions:
            del all_functions['kernel_sem_unlock']
        if 'sys_mutex_trylock' not in used_wrappers and 'kernel_mutex_trylock' in all_functions:
            del all_functions['kernel_mutex_trylock']
        if 'mutex_unlock' not in used_wrappers and 'kernel_mutex_unlock' in all_functions:
            del all_functions['kernel_mutex_unlock']

        # Sinais e Tempo
        if 'signal' not in used_wrappers and 'kernel_signal' in all_functions:
            del all_functions['kernel_signal']
        if 'sigreturn' not in used_wrappers and 'kernel_sigreturn' in all_functions:
            del all_functions['kernel_sigreturn']
        if 'get_signal' not in used_wrappers and 'kernel_get_signal' in all_functions:
            del all_functions['kernel_get_signal']
        # ~ if 'kill' not in used_wrappers and 'kernel_kill' in all_functions:
            # ~ del all_functions['kernel_kill']
        if 'sleep' not in used_wrappers and 'kernel_sleep' in all_functions:
            del all_functions['kernel_sleep']
        if 'alarm' not in used_wrappers and 'kernel_alarm' in all_functions:
            del all_functions['kernel_alarm']
        if 'pause' not in used_wrappers and 'kernel_pause' in all_functions:
            del all_functions['kernel_pause']

        # I/O Básico
        if 'print_char' not in used_wrappers and 'kernel_print_char' in all_functions:
            del all_functions['kernel_print_char']
        if 'read_char' not in used_wrappers and 'kernel_read_char' in all_functions:
            del all_functions['kernel_read_char']

        # --- NOVO: Podador Recursivo da AST ---
        def contains_var(node, var_name):
            if node is None or isinstance(node, (int, str, bool, float)): return False
            if isinstance(node, list): return any(contains_var(n, var_name) for n in node)
            if isinstance(node, Var) and node.name == var_name: return True
            if hasattr(node, '__dict__'):
                return any(contains_var(v, var_name) for k, v in vars(node).items() if k not in ('lineno', 'colno', 'end_lineno', 'end_colno'))
            return False

        def prune_ast_blocks(body_list, used_wrappers):
            if not isinstance(body_list, list): return
            
            new_body = []
            for stmt in body_list:
                is_dead = False
                if isinstance(stmt, (If, While)):
                    cond = getattr(stmt, 'condition', None)
                    
                    # Poda Semântica de Recursos Desativados em TODO o SO
                    if 'signal' not in used_wrappers and 'kill' not in used_wrappers and contains_var(cond, 'pending_signal'):
                        is_dead = True
                    elif 'sleep' not in used_wrappers and contains_var(cond, 'STATE_SLEEPING'):
                        is_dead = True
                    elif 'alarm' not in used_wrappers and contains_var(cond, 'alarm_tick'):
                        is_dead = True
                            
                if not is_dead:
                    if hasattr(stmt, 'body'):
                        prune_ast_blocks(getattr(stmt, 'body'), used_wrappers)
                    if hasattr(stmt, 'then_body'):
                        prune_ast_blocks(getattr(stmt, 'then_body'), used_wrappers)
                    if hasattr(stmt, 'else_body'):
                        prune_ast_blocks(getattr(stmt, 'else_body'), used_wrappers)
                    
                    new_body.append(stmt)
            
            body_list[:] = new_body

        # Aplica a poda de blocos inativos em TODAS as funções do SO
        for f_name, f_node in all_functions.items():
            prune_ast_blocks(f_node.body, used_wrappers)


        # 3. PODA CIRÚRGICA AVANÇADA NA MAIN()
        if 'main' in all_functions:
            main_func = all_functions['main']
            new_main_body = []
            
            for stmt in main_func.body:
                is_dead_syscall = False
                
                # A) Poda o Roteamento das Syscalls (Ifs)
                if isinstance(stmt, If) and isinstance(stmt.condition, BinaryOp) and stmt.condition.op == '==':
                    left = stmt.condition.left
                    right = stmt.condition.right
                    
                    if getattr(left, 'name', '') == 'tmp_sys_id' and isinstance(right, Const):
                        try:
                            sys_id = int(right.value)
                            if sys_id in syscall_wrappers:
                                wrapper_name = syscall_wrappers[sys_id]
                                if wrapper_name not in used_wrappers:
                                    is_dead_syscall = True 
                        except: pass
                
                # B) Poda as Inicializações do Boot (Memória Compartilhada e Mailbox)
                if isinstance(stmt, Call) and isinstance(stmt.callee, Var):
                    callee_name = stmt.callee.name
                    if callee_name == 'init_ipc_shm' and 'shmget' not in used_wrappers:
                        is_dead_syscall = True
                    if callee_name == 'init_ipc_mailbox' and 'msg_send' not in used_wrappers and 'msg_recv' not in used_wrappers:
                        is_dead_syscall = True
                
                if not is_dead_syscall:
                    new_main_body.append(stmt)
            
            main_func.body = new_main_body

        # =================================================================
        # FIM DA PODA DE SYSCALLS. O CALL GRAPH NORMAL ASSUME O CONTROLE!
        # =================================================================

        reachable = set()
        worklist = ['main'] # A main é sempre a raiz de execução

        def find_refs(node):
            refs = set()
            if node is None or isinstance(node, (int, str, bool, float)):
                return refs
            if isinstance(node, list):
                for item in node: refs.update(find_refs(item))
                return refs

            if hasattr(node, '__dict__'):
                if isinstance(node, Asm):
                    words = re.findall(r'[A-Za-z_]\w*', node.code)
                    for word in words:
                        if word in all_functions:
                            refs.add(word)

                if isinstance(node, Call) and isinstance(node.callee, Var):
                     if node.callee.name in all_functions:
                          refs.add(node.callee.name)
                          
                if isinstance(node, Var) and node.name in all_functions:
                     refs.add(node.name)

                for key, val in vars(node).items():
                    if key not in ('lineno', 'colno', 'end_lineno', 'end_colno'):
                        refs.update(find_refs(val))
            return refs

        dependencies = {}
        for f_name, f_node in all_functions.items():
            dependencies[f_name] = find_refs(f_node.body)

        for item in program.items:
            if not isinstance(item, Function):
                worklist.extend(list(find_refs(item)))

        while worklist:
            curr = worklist.pop(0)
            if curr in all_functions and curr not in reachable:
                reachable.add(curr)
                worklist.extend(list(dependencies[curr]))

        original_count = len(all_functions)
        
        program.items = [
            item for item in program.items 
            if not isinstance(item, Function) or item.name in reachable
        ]
        
        dead_count = original_count - len(reachable)
        return dead_count
