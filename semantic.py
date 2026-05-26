# ~ from .lexer import tokenize
# ~ from .compiler_ast import *
from lexer import tokenize
from compiler_ast import *

class SemanticError(Exception):
    def __init__(self, message, lineno=None):
        if lineno is None:
            super().__init__(f"Erro Semântico na linha ?: {message}")
        else:
            super().__init__(f"Erro Semântico na linha {lineno}: {message}")


def get_lineno(node):
    return getattr(node, "lineno", "?")


class Semantic:
    # ---------------------------------------------
    # Tabela de bibliotecas Cariri e suas funções
    # ---------------------------------------------
    BUILTIN_LIBS = {
        "abs":      { "abs": 1 },
        "mul":      { "mul": 2 },
        "div":      { "div": 2 },
        "max":      { "max": 2 },
        "min":      { "min": 2 },
        "mod":      { "mod": 2 },
        "pow":      { "pow": 2 }
    }

    def __init__(self, ast, required_entry="main"):
        self.ast = ast
        self.required_entry = required_entry
        self.global_scope = {}
        self.functions = {}
        self.current_scope = None
        self.loop_depth = 0
        
        self.structs = {}

        self.log = []
        
        self.local_symbols = {}
        
        # --- NOVO: Estruturas para Linter de Avisos (Warnings) ---
        self.warnings = []
        self.global_usage = {}
        self.local_usage = None
        # ---------------------------------------------------------
        
        self.push("Iniciando análise semântica...\n")

    # ---------- Log ----------
    def push(self, msg):
        self.log.append(msg)

    def get_log(self):
        return "\n".join(self.log)

    # ---------- Utilitários ----------
    def type_name(self, t):
        if t is None:
            return "void"
        # Melhoria na representação de ponteiros void*
        if isinstance(t, PointerType) and t.base is None:
            return "void*"
        return repr(t)

    def types_equal(self, a, b):
        if a is None or b is None:
            return a is None and b is None
        if isinstance(a, IntType) and isinstance(b, IntType):
            return True
        if isinstance(a, CharType) and isinstance(b, CharType):
            return True
        if isinstance(a, PointerType) and isinstance(b, PointerType):
            return self.types_equal(a.base, b.base)
        if isinstance(a, ArrayType) and isinstance(b, ArrayType):
            return self.types_equal(a.base, b.base) and a.size == b.size
        if isinstance(a, StructType) and isinstance(b, StructType):
            return a.name == b.name
        return False

    def is_compatible(self, expected, actual, actual_node=None):
        if expected is None:
            return False
        if self.types_equal(expected, actual):
            return True
        
        # Antes estava bloqueando structs. Agora permitimos se for o mesmo tipo.
        if isinstance(expected, StructType) and isinstance(actual, StructType):
             return expected.name == actual.name
        
        if isinstance(expected, IntType) and isinstance(actual, CharType):
            return True
        
        if isinstance(expected, CharType) and isinstance(actual, IntType):
            if isinstance(actual_node, Const):
                try:
                    v = int(actual_node.value)
                    return 0 <= v <= 255
                except:
                    return False
            return False

        # --- LÓGICA DE PONTEIROS E VOID* ---
        if isinstance(expected, PointerType):
            # NULL (0) é compatível com qualquer ponteiro (Força a conversão para int)
            if isinstance(actual, IntType) and actual_node and isinstance(actual_node, Const):
                try:
                    if int(actual_node.value) == 0:
                        return True
                except:
                    pass

            # void* aceita qualquer ponteiro e vice-versa
            is_expected_void = (expected.base is None)
            
            if isinstance(actual, PointerType):
                is_actual_void = (actual.base is None)
                if is_expected_void or is_actual_void:
                    return True # void* é universal (compatível com tudo)
                return self.types_equal(expected.base, actual.base)
            
            if isinstance(actual, ArrayType):
                # Array decai para ponteiro
                if is_expected_void:
                    return True # Array para void* é permitido
                return self.types_equal(expected.base, actual.base)
            return False

        if isinstance(expected, ArrayType) and isinstance(actual, ArrayType):
            return self.types_equal(expected.base, actual.base) and expected.size == actual.size
        return False

    def is_declared(self, name):
        if self.current_scope is not None and name in self.current_scope:
            return True
        return name in self.global_scope

    # ======================================================
    # PROGRAMA
    # ======================================================
    def analyze(self):
        self.visit_program(self.ast)
        self.push("\nAnálise semântica finalizada com sucesso.")

    def visit_program(self, program):
        self.global_scope = {}
        self.global_usage = {} # Limpa os usos globais
        self.warnings = []
        
        # Define o escopo atual como global para que visit_stmt funcione
        self.current_scope = self.global_scope 
        
        self.push("📌 Coletando declarações globais e importações...")

        # bibliotecas
        for item in program.items:
            if isinstance(item, LibraryImport):
                lib = item.name
                if lib in self.BUILTIN_LIBS:
                    for fname, nargs in self.BUILTIN_LIBS[lib].items():
                        self.functions[fname] = f"[builtin:{lib}]"
                        self.push(f"  ✔ Biblioteca '{lib}' importada — função '{fname}' registrada ({nargs} args)")
                else:
                    raise SemanticError(f"Biblioteca '{lib}' não reconhecida.", get_lineno(item))

        # structs
        for item in program.items:
            if isinstance(item, StructDecl):
                if item.name in self.structs:
                    raise SemanticError(f"struct '{item.name}' redefinido.", get_lineno(item))

                offset = 0
                fields = {}
                offsets = {}

                for fname, ftype, flineno in item.fields:
                    if fname in fields:
                        raise SemanticError(f"Campo '{fname}' duplicado em struct '{item.name}'.", flineno)
                    fields[fname] = ftype
                    offsets[fname] = offset
                    offset += self.sizeof(ftype)

                self.structs[item.name] = {
                    "fields": fields,
                    "offsets": offsets,
                    "size": offset
                }

        # Declarações Globais (Variáveis e Arrays) e Cabeçalhos de Funções
        for decl in program.items:
            if isinstance(decl, (VarDecl, ArrayDecl)):
                # Agora chamamos visit_stmt, que fará a validação de constantes!
                self.visit_stmt(decl)
            
            elif isinstance(decl, Function):
                if decl.name in self.functions:
                    raise SemanticError(f"Função '{decl.name}' já foi declarada.", get_lineno(decl))
                self.functions[decl.name] = decl

        if self.required_entry and self.required_entry not in self.functions:
            raise SemanticError(f"Todo programa deve conter a função '{self.required_entry}'.", get_lineno(program))

        # Corpos das Funções
        for decl in program.items:
            if isinstance(decl, Function):
                self.visit_function(decl)
        
        # --- GERAÇÃO DE AVISOS (Variáveis Globais) ---
        for var_name, info in self.global_usage.items():
            if info['count'] == 0:
                self.warnings.append(f"Aviso na linha {info['lineno']}: Variável global '{var_name}' declarada mas nunca utilizada.")

        # Limpa o escopo ao final
        self.current_scope = None

    # ======================================================
    # FUNÇÕES
    # ======================================================
    def visit_function(self, func):

        if len(func.params) != len(set(p.name for p in func.params)):
            raise SemanticError(f"Parâmetros duplicados na função '{func.name}'.", get_lineno(func))

        self.current_function_rettype = func.rettype
        self.current_scope = {p.name: p.vartype for p in func.params}
        
        # --- REGISTRA PARÂMETROS PARA AVISOS ---
        self.local_usage = {p.name: {'count': 0, 'lineno': getattr(p, "lineno", "?")} for p in func.params}
        
        self.loop_depth = 0
        self.return_found = False

        for stmt in func.body:
            self.visit_stmt(stmt)

        if func.rettype is not None and not self.return_found and func.name != "main" and not func.is_naked:
            raise SemanticError(f"Função '{func.name}' não possui 'return'.", get_lineno(func))

        # --- GERAÇÃO DE AVISOS (Variáveis Locais e Parâmetros) ---
        for var_name, info in self.local_usage.items():
            if info['count'] == 0:
                self.warnings.append(f"Aviso na linha {info['lineno']}: Parâmetro ou variável local '{var_name}' declarado(a) mas nunca utilizado(a).")

        self.local_symbols[func.name] = set(self.current_scope.keys())
        
        self.local_usage = None
        self.current_scope = None

    # ======================================================
    # DECLARAÇÕES E COMANDOS
    # ======================================================
    def visit_stmt(self, stmt):
        
        # ------------------ VarDecl ------------------
        if isinstance(stmt, VarDecl):
            if stmt.vartype is None:
                raise SemanticError("Variáveis não podem ser declaradas como tipo 'void'. Use ponteiros 'void*'.", get_lineno(stmt))
            
            for entry in stmt.names:
                name, init = entry if isinstance(entry, tuple) else (entry, None)
                
                # Verifica redefinição
                if name in self.current_scope:
                    raise SemanticError(f"Variável '{name}' redefinida.", get_lineno(stmt))

                self.current_scope[name] = stmt.vartype
                
                # --- REGISTRA PARA AVISOS ---
                if self.current_scope is self.global_scope:
                    self.global_usage[name] = {'count': 0, 'lineno': get_lineno(stmt)}
                else:
                    self.local_usage[name] = {'count': 0, 'lineno': get_lineno(stmt)}

                if init is not None:
                    # --- CORREÇÃO: Validação usando 'is self.global_scope' ---
                    if self.current_scope is self.global_scope:  # Escopo Global detectado corretamente
                        def is_valid_global_init(node):
                            if isinstance(node, (Const, StringLiteral)): 
                                return True
                            if isinstance(node, AddressOf): 
                                return True
                            if isinstance(node, list):
                                return True
                            if isinstance(node, UnaryOp) and node.op in ('-', '+') and isinstance(node.expr, Const):
                                return True
                            return False

                        # Se for lista (array), verifica todos os elementos
                        if isinstance(init, list):
                            for item in init:
                                if not is_valid_global_init(item):
                                    raise SemanticError(
                                        f"Inicialização global de array '{name}' deve conter apenas constantes.", 
                                        get_lineno(stmt)
                                    )
                        # Se for escalar
                        elif not is_valid_global_init(init):
                            raise SemanticError(
                                f"Variável global '{name}' deve ser inicializada com constante (encontrado variável ou expressão).", 
                                get_lineno(stmt)
                            )
                    # ---------------------------------------------------------

                    # Verificação de Tipos (Compatibilidade)
                    if isinstance(init, list):
                        for elem in init:
                            if isinstance(elem, Const):
                                const_type = elem.typeof()
                                if not self.is_compatible(stmt.vartype, const_type, elem):
                                    raise SemanticError(
                                        f"Inicializador incompatível para '{name}'.",
                                        get_lineno(elem)
                                    )
                                elem.vartype = const_type
                            else:
                                self.visit_expr(elem)
                    else:
                        val_t = self.visit_expr(init)
                        if not self.is_compatible(stmt.vartype, val_t, init):
                            raise SemanticError(
                                f"Inicialização incompatível para '{name}'.",
                                get_lineno(init)
                            )

        # ------------------ ArrayDecl ------------------
        elif isinstance(stmt, ArrayDecl):
            if stmt.arrtype.base is None:
                raise SemanticError("Arrays não podem ser do tipo 'void'.", get_lineno(stmt))
                
            if stmt.name in self.current_scope:
                raise SemanticError(f"Array '{stmt.name}' redefinido.", get_lineno(stmt))

            self.current_scope[stmt.name] = stmt.arrtype
            
            # --- REGISTRA ARRAY PARA AVISOS ---
            if self.current_scope is self.global_scope:
                self.global_usage[stmt.name] = {'count': 0, 'lineno': get_lineno(stmt)}
            else:
                self.local_usage[stmt.name] = {'count': 0, 'lineno': get_lineno(stmt)}

            if stmt.init:
                # Regra de Globais para Arrays
                if self.current_scope is self.global_scope:
                    for elem in stmt.init:
                        is_valid = isinstance(elem, (Const, StringLiteral)) or (isinstance(elem, UnaryOp) and elem.op in ('-', '+') and isinstance(elem.expr, Const))
                        if not is_valid:
                             raise SemanticError(f"Inicialização de array global '{stmt.name}' deve conter apenas constantes.", get_lineno(stmt))

                if len(stmt.init) > stmt.arrtype.size:
                    raise SemanticError(
                        f"Inicializador maior que tamanho do array '{stmt.name}'.",
                        get_lineno(stmt)
                    )
                for elem in stmt.init:
                    if isinstance(elem, Const):
                        const_type = elem.typeof()
                        
                        if not self.is_compatible(stmt.arrtype.base, const_type, elem):
                            raise SemanticError(
                                f"Inicializador incompatível para '{stmt.name}'.",
                                get_lineno(elem)
                            )
                        elem.vartype = const_type
                    else:
                        val_t = self.visit_expr(elem)
                        val_t_decayed = self.decay(val_t)
                        
                        # --- FIX: Validação de Tipos para variáveis e arrays locais ---
                        # Exceção nativa do C: Permitir inicializar array de char com StringLiteral ("texto")
                        if isinstance(stmt.arrtype.base, CharType) and isinstance(elem, StringLiteral):
                            pass 
                        # Para os demais casos, checa rigorosamente a tipagem!
                        elif not self.is_compatible(stmt.arrtype.base, val_t_decayed, elem):
                            raise SemanticError(
                                f"Elemento incompatível na inicialização do array '{stmt.name}': esperado {self.type_name(stmt.arrtype.base)}, obtido {self.type_name(val_t)}.",
                                get_lineno(elem)
                            )

        # ------------------ Assignment (LÓGICA UNIFICADA) ------------------
        elif isinstance(stmt, Assignment):

            # 1. Resolver o Tipo do Lado Esquerdo (Target)
            if isinstance(stmt.target, Var):
                self.ensure_vartype(stmt.target)
                target_t = stmt.target.vartype

            elif isinstance(stmt.target, Deref):
                ptr_t = self.visit_expr(stmt.target.ptr)
                if not isinstance(ptr_t, PointerType):
                    raise SemanticError("Deref aplicado a não ponteiro.", get_lineno(stmt))
                # NOVO: Proibir desreferência direta de void* em atribuição
                if ptr_t.base is None:
                    raise SemanticError("Não é possível desreferenciar um ponteiro 'void*'. Use cast.", get_lineno(stmt))
                target_t = ptr_t.base

            elif isinstance(stmt.target, ArrayAccess):
                
                # --- FIX: Chama o ensure_vartype para registrar o uso do array no Linter! ---
                if isinstance(stmt.target.array, Var):
                    self.ensure_vartype(stmt.target.array)
                    arr_t = stmt.target.array.vartype
                else:
                    arr_t = self.visit_expr(stmt.target.array)
                    stmt.target.array.vartype = arr_t
                # ----------------------------------------------------------------------------

                if not isinstance(arr_t, (ArrayType, PointerType)):
                    raise SemanticError("Indexação aplicada a tipo inválido.",
                                        get_lineno(stmt))
                
                # NOVO: Proibir indexação de void*
                if isinstance(arr_t, PointerType) and arr_t.base is None:
                    raise SemanticError("Não é possível indexar um ponteiro 'void*'.", get_lineno(stmt))

                # índice
                self.visit_expr(stmt.target.index)

                target_t = arr_t.base
                stmt.target.vartype = target_t # Importante para CodeGen
            elif isinstance(stmt.target, FieldAccess):
                target_t = self.visit_expr(stmt.target)

            elif isinstance(stmt.target, ArrowAccess):
                target_t = self.visit_expr(stmt.target)

            else:
                raise SemanticError("Lado esquerdo inválido na atribuição.",
                                    get_lineno(stmt))

            # 2. Resolver o Tipo do Lado Direito (Value)
            val_t = self.visit_expr(stmt.value)
            #self.ensure_vartype(stmt.value)

            # Decay array para ponteiro, exceto em struct ou AddressOf
            if not isinstance(stmt.value, AddressOf) and not isinstance(val_t, StructType):
                val_t = self.decay(val_t)
            
            if isinstance(target_t, ArrayType):
                raise SemanticError(
                    "Em C, não é possível atribuir ou reatribuir um array diretamente. Use um laço de repetição ou manipulação de ponteiros.",
                    get_lineno(stmt)
                )
                
            # 3. Verificação de Structs e Compatibilidade
            stmt.is_struct_assign = False # Default

            if isinstance(target_t, StructType) or isinstance(val_t, StructType):
                # Ambos devem ser struct
                if not isinstance(target_t, StructType) or not isinstance(val_t, StructType):
                    raise SemanticError(
                        "Atribuição inválida envolvendo struct.",
                        get_lineno(stmt)
                    )

                # Nomes devem coincidir
                if target_t.name != val_t.name:
                    raise SemanticError(
                        f"Atribuição entre structs incompatíveis: '{target_t.name}' ← '{val_t.name}'.",
                        get_lineno(stmt)
                    )

                # Marca flag para o CodeGen saber que é cópia de bloco de memória
                stmt.is_struct_assign = True
                return

            # Verificação Padrão
            if not self.is_compatible(target_t, val_t, stmt.value):
                raise SemanticError(
                    f"Tipo incompatível na atribuição: esperado {self.type_name(target_t)}, obtido {self.type_name(val_t)}",
                    get_lineno(stmt.value)
                )

        # ------------------ Return ------------------
        elif isinstance(stmt, Return):
            if stmt.value is None:
                if self.current_function_rettype is not None:
                    raise SemanticError("Return sem valor em função não-void.", get_lineno(stmt))
            else:
                val_t = self.visit_expr(stmt.value)
                self.ensure_vartype(stmt.value)
                val_t = self.decay(val_t)
                rettype = self.current_function_rettype
                if rettype is None:
                    raise SemanticError("Função void não pode retornar valor.",
                                        get_lineno(stmt))
                if not self.is_compatible(rettype, val_t, stmt.value):
                    raise SemanticError(
                        f"Tipo de retorno incompatível: esperado {self.type_name(rettype)}, obtido {self.type_name(val_t)}",
                        get_lineno(stmt.value)
                    )
            self.return_found = True

        # ------------------ If ------------------
        elif isinstance(stmt, If):
            self.visit_expr(stmt.condition)
            for s in stmt.then_body:
                self.visit_stmt(s)
            if stmt.else_body:
                for s in stmt.else_body:
                    self.visit_stmt(s)

        # ------------------ While ------------------
        elif isinstance(stmt, While):
            self.loop_depth += 1
            self.visit_expr(stmt.condition)
            for s in stmt.body:
                self.visit_stmt(s)
            self.loop_depth -= 1
        
        # ------------------ Switch ------------------
        elif isinstance(stmt, Switch):
            if not hasattr(self, 'switch_depth'): 
                self.switch_depth = 0
                
            # A expressão testada deve ser int ou char
            expr_t = self.visit_expr(stmt.expr)
            if not isinstance(expr_t, (IntType, CharType)):
                raise SemanticError("A expressão do switch deve ser do tipo int ou char.", get_lineno(stmt))
                
            self.switch_depth += 1
            has_default = False
            case_values = set()
            
            for case in stmt.cases:
                if case.value is None: # É o 'default'
                    if has_default:
                        raise SemanticError("Múltiplos blocos 'default' em um único switch.", get_lineno(case))
                    has_default = True
                else:
                    # Avalia a expressão do case
                    self.visit_expr(case.value)
                    
                    if not isinstance(case.value, Const):
                        raise SemanticError("O valor do 'case' deve ser uma constante.", get_lineno(case.value))
                    
                    val = case.value.value
                    if val in case_values:
                        raise SemanticError(f"Valor de 'case' duplicado: {val}", get_lineno(case.value))
                    case_values.add(val)
                
                # Visita os comandos do bloco do case
                for s in case.body:
                    self.visit_stmt(s)
                    
            self.switch_depth -= 1

        # ------------------ For ------------------
        elif isinstance(stmt, For):
            self.loop_depth += 1
            self.visit_stmt(stmt.init)
            self.visit_expr(stmt.condition)
            self.visit_stmt(stmt.increment)
            for s in stmt.body:
                self.visit_stmt(s)
            self.loop_depth -= 1

        # ------------------ Call ------------------
        elif isinstance(stmt, (Call, PreInc, PreDec, PostInc, PostDec)):
            self.visit_expr(stmt)

        # ------------------ break ------------------
        elif isinstance(stmt, Break):
            sw_depth = getattr(self, 'switch_depth', 0)
            if self.loop_depth == 0 and sw_depth == 0:
                raise SemanticError("'break' fora de loop ou switch.", get_lineno(stmt))

        # ------------------ continue ------------------
        elif isinstance(stmt, Continue):
            if self.loop_depth == 0:
                raise SemanticError("'continue' fora de loop.", get_lineno(stmt))


        # ------------------ ASM ------------------
        if isinstance(stmt, Asm):
            pass

    # ======================================================
    # EXPRESSÕES
    # ======================================================
    def visit_expr(self, expr):

        ln = get_lineno(expr)

        # VAR
        if isinstance(expr, Var):
            self.ensure_vartype(expr)
            return expr.vartype


        # STRING LITERAL
        elif isinstance(expr, StringLiteral):
            expr.vartype = expr.typeof()
            return expr.vartype


        # CONST
        elif isinstance(expr, Const):
            expr.vartype = expr.typeof()
            return expr.vartype

        # CAST
        elif isinstance(expr, TypeCast):
            # Visita a expressão interna para garantir que ela é válida
            val_t = self.visit_expr(expr.expr)
            
            # O tipo da expressão de cast é o próprio tipo alvo
            expr.vartype = expr.target_type
            return expr.vartype


        # BINARY
        elif isinstance(expr, BinaryOp):
            self.push(f"      ➤ Operação binária '{expr.op}'")
            lt = self.visit_expr(expr.left)
            rt = self.visit_expr(expr.right)
            lt = self.decay(lt)
            rt = self.decay(rt)
            
            # ------------------------------------------
            # -2) OPERADORES LÓGICOS (&& e ||) 
            # ------------------------------------------
            if expr.op in ('&&', '||'):
                # Verifica se ambos os lados são int, char ou ponteiro
                valid_types = (IntType, CharType, PointerType)
                if not isinstance(lt, valid_types) or not isinstance(rt, valid_types):
                    raise SemanticError(
                        f"Operador '{expr.op}' exige operandos numéricos ou ponteiros.",
                        get_lineno(expr)
                    )
                self.push(f"        ✔ Operação lógica '{expr.op}' → int")
                expr.vartype = IntType()
                return expr.vartype
            # ------------------------------------------
            # -1) Comparação de Ponteiros (ptr == 0, ptr != 0)
            # ------------------------------------------
            if expr.op in ('==', '!='):
                is_lp = isinstance(lt, PointerType)
                is_rp = isinstance(rt, PointerType)
                
                # Se um lado é ponteiro e o outro é o literal 0
                if (is_lp and isinstance(rt, IntType) and isinstance(expr.right, Const) and int(expr.right.value) == 0) or \
                   (is_rp and isinstance(lt, IntType) and isinstance(expr.left, Const) and int(expr.left.value) == 0):
                    expr.vartype = IntType()
                    return expr.vartype
                
                # Se ambos são ponteiros (comparação de endereços)
                if is_lp and is_rp:
                    expr.vartype = IntType()
                    return expr.vartype
            
            # ------------------------------------------
            # 0) Operadores Lógicos e Matemáticos Nativos
            # ------------------------------------------
            if expr.op in ('&', '|', '^', '<<', '>>', '*', '/'):
                if not isinstance(lt, (IntType, CharType)) or not isinstance(rt, (IntType, CharType)):
                    raise SemanticError(f"Operador '{expr.op}' exige operandos inteiros (linha {expr.lineno})")
                self.push(f"        ✔ Operação '{expr.op}' → int")
                expr.vartype = IntType()
                return expr.vartype

            # ------------------------------------------
            # 1) Aritmética de ponteiros: ptr ± int
            # ------------------------------------------
            if isinstance(lt, PointerType) and isinstance(rt, IntType):
                if expr.op in ('+','-'):
                    # NOVO: PROIBIR aritmética com void*
                    if lt.base is None:
                        raise SemanticError(f"Aritmética não permitida em ponteiro void* (linha {ln}). Use cast se necessário.", ln)
                        
                    self.push("        ✔ Ponteiro ± inteiro → ponteiro")
                    expr.vartype = PointerType(lt.base)
                    return expr.vartype
                else:
                    raise SemanticError(f"Operação '{expr.op}' não permitida entre pointer e int (linha {expr.lineno})")

            if isinstance(rt, PointerType) and isinstance(lt, IntType):
                if expr.op == '+':  # int + pointer permitido
                    # NOVO: PROIBIR aritmética com void*
                    if rt.base is None:
                        raise SemanticError(f"Aritmética não permitida em ponteiro void* (linha {ln}).", ln)
                        
                    self.push("        ✔ Inteiro + ponteiro → ponteiro")
                    expr.vartype = PointerType(rt.base)
                    return expr.vartype
                else:
                    raise SemanticError(
                        f"Operação '{expr.op}' inválida: inteiro só pode somar com ponteiro (linha {expr.lineno})"
                    )

            # ------------------------------------------
            # 2) pointer - pointer (não suportado)
            # ------------------------------------------
            if isinstance(lt, PointerType) and isinstance(rt, PointerType):
                raise SemanticError(f"Subtração entre ponteiros não suportada (linha {expr.lineno})")

            # ------------------------------------------
            # 3) Regras já existentes
            # ------------------------------------------
            if isinstance(lt, IntType) or isinstance(rt, IntType):
                expr.vartype = IntType()
                return expr.vartype

            if isinstance(lt, CharType) and isinstance(rt, CharType):
                expr.vartype = CharType()
                return expr.vartype

            expr.vartype = lt
            return expr.vartype


        # UNARY
        elif isinstance(expr, UnaryOp):
            t = self.visit_expr(expr.expr)
            
            # Validação do Bitwise NOT
            if expr.op == '~':
                if not isinstance(t, (IntType, CharType)):
                    raise SemanticError(f"Operador '~' exige operando inteiro (linha {expr.lineno})")
                expr.vartype = IntType()
                return expr.vartype
            
            # Validação do Logical NOT (!)
            elif expr.op == '!':
                # Pode ser aplicado a int, char e ponteiros (decai para verificação de NULL)
                if not isinstance(t, (IntType, CharType, PointerType)):
                    raise SemanticError(f"Operador '!' exige operando numérico ou ponteiro (linha {expr.lineno})")
                
                # O resultado do '!' é sempre Int (0 ou 1)
                expr.vartype = IntType()
                return expr.vartype
            
            expr.vartype = t
            return expr.vartype
        
        # INCREMENTO E DECREMENTO (Prefixo e Sufixo)
        elif isinstance(expr, (PreInc, PreDec, PostInc, PostDec)):
            # 1. Visita o alvo para descobrir seu tipo e garantir que ele existe
            target_t = self.visit_expr(expr.target)
            
            # 2. Validação de L-value: Garante que o alvo é modificável na memória
            if not isinstance(expr.target, (Var, ArrayAccess, Deref, FieldAccess, ArrowAccess)):
                raise SemanticError(
                    "O operando do incremento/decremento deve ser um L-value (variável, array ou ponteiro modificável).",
                    get_lineno(expr)
                )

            # 3. Validação de Tipo: Garante que é int, char ou ponteiro
            if not (isinstance(target_t, IntType) or isinstance(target_t, CharType) or isinstance(target_t, PointerType)):
                raise SemanticError(
                    f"Operador de incremento/decremento não suportado para o tipo '{self.type_name(target_t)}'.",
                    get_lineno(expr)
                )

            # O tipo resultante da expressão de incremento é igual ao tipo da variável alvo
            expr.vartype = target_t
            return target_t


        # ADDRESS OF (&)
        if isinstance(expr, AddressOf):
            # --- FIX: Validação rigorosa de L-value ---
            if not isinstance(expr.var, (Var, ArrayAccess, Deref, FieldAccess, ArrowAccess)):
                raise SemanticError(
                    "O operador '&' (AddressOf) exige um L-value (variável, array ou campo de struct). Não é possível obter o endereço de uma constante ou expressão.", 
                    ln
                )
                
            if isinstance(expr.var, Var):
                name = expr.var.name
                # Se for uma função declarada
                if name in self.functions:
                    expr.vartype = PointerType(IntType()) 
                    return expr.vartype

            base_t = self.visit_expr(expr.var)
            if base_t is None:
                raise SemanticError("Operador '&' aplicado a expressão inválida.", ln)
            expr.vartype = PointerType(base_t)
            return expr.vartype

        # DEREF
        elif isinstance(expr, Deref):
            ptr_t = self.visit_expr(expr.ptr)
            expr.vartype = ptr_t.base
            if not isinstance(ptr_t, PointerType):
                raise SemanticError("Deref aplicado a não ponteiro.", ln)
            
            # NOVO: PROIBIR desreferência de void*
            if ptr_t.base is None:
                raise SemanticError("Não é possível desreferenciar ponteiro void* (tamanho desconhecido).", ln)
                
            return ptr_t.base

        # CALL
        elif isinstance(expr, Call):
            ln = get_lineno(expr)
            
            # Variáveis de controle para validação
            is_direct_call = False
            expected_types = None
            expected_n = None
            rettype = IntType() # Default retorno (int) se não soubermos

            # 1. Identificação do Alvo (Direto vs Indireto)
            if isinstance(expr.callee, Var):
                name = expr.callee.name
                
                # A: O nome refere-se a uma variável local/global? (Ponteiro de função)
                if self.is_declared(name):
                    is_direct_call = False
                    callee_t = self.visit_expr(expr.callee)

                # B: O nome refere-se a uma função definida? (Chamada Direta)
                elif name in self.functions:
                    is_direct_call = True
                    func_entry = self.functions[name]

                    # B1: Função de Usuário (Function Node)
                    if isinstance(func_entry, Function):
                        expected_types = [p.vartype for p in func_entry.params]
                        expected_n = len(func_entry.params)
                        rettype = func_entry.rettype

                    # B2: Builtin (Dicionário/String)
                    else: 
                        # Busca metadados nas libs embutidas
                        found_builtin = False
                        for lib, funcs in self.BUILTIN_LIBS.items():
                            if name in funcs:
                                expected_n = funcs[name]
                                found_builtin = True
                                break
                        if not found_builtin:
                             raise SemanticError(f"Erro interno: Builtin '{name}' não encontrado nas libs.", ln)
                
                else:
                    raise SemanticError(f"Função ou variável '{name}' não declarada.", ln)
            
            # C: O alvo é uma expressão complexa (ex: (*ptr)()) -> Indireta
            else:
                is_direct_call = False
                callee_t = self.visit_expr(expr.callee)

            # 2. Validação
            if not is_direct_call:
                # --- Validação de Chamada Indireta ---
                callee_t = self.decay(callee_t)
                
                if not (isinstance(callee_t, PointerType) or isinstance(callee_t, IntType)):
                     raise SemanticError(
                         f"Tentativa de chamar expressão do tipo '{self.type_name(callee_t)}'. Apenas ponteiros ou inteiros são invocáveis.", 
                         ln
                     )
                
                for arg in expr.args:
                    self.visit_expr(arg)
                
                expr.vartype = IntType()
                return expr.vartype

            else:
                # --- Validação de Chamada Direta ---
                if expected_n is not None and len(expr.args) != expected_n:
                    raise SemanticError(
                        f"Função '{name}' espera {expected_n} argumentos, mas recebeu {len(expr.args)}.",
                        ln
                    )

                for i, arg in enumerate(expr.args):
                    val_t = self.visit_expr(arg)
                    if expected_types is not None:
                        expected = expected_types[i]
                        val_t_decayed = self.decay(val_t)
                        if not self.is_compatible(expected, val_t_decayed, arg):
                             raise SemanticError(
                                 f"Argumento {i+1} incompatível em chamada de '{name}': "
                                 f"esperado {self.type_name(expected)}, obtido {self.type_name(val_t)}.",
                                 get_lineno(arg)
                             )

                expr.vartype = rettype
                return rettype
                
        # ARRAY ACCESS
        elif isinstance(expr, ArrayAccess):

            ln = get_lineno(expr)

            # GARANTE que Var tenha tipo
            if isinstance(expr.array, Var):
                self.ensure_vartype(expr.array)
                array_t = expr.array.vartype
            else:
                array_t = self.visit_expr(expr.array)

            decayed = self.decay(array_t)

            if not isinstance(decayed, (ArrayType, PointerType)):
                raise SemanticError("Indexação aplicada a tipo inválido.", ln)
            
            # NOVO: PROIBIR indexação de void*
            if isinstance(decayed, PointerType) and decayed.base is None:
                raise SemanticError("Não é possível indexar ponteiro void*.", ln)

            # índice
            index_t = self.visit_expr(expr.index)
            if not isinstance(index_t, IntType):
                raise SemanticError("Índice de array deve ser int.", ln)

            expr.vartype = decayed.base
            return expr.vartype


        # STRUCT DOT ACCESS
        elif isinstance(expr, FieldAccess):
            base_t = self.visit_expr(expr.base)
            expr.base.vartype = base_t

            # 🔥 CASO ESPECIAL: (&struct).field  → erro de precedência
            if isinstance(base_t, PointerType) and isinstance(base_t.base, StructType):
                raise SemanticError(
                    "Uso inválido de '.'. Em C, '&t.c' significa '&(t.c)'. "
                    "Provável erro de precedência no parser.",
                    ln
                )

            if not isinstance(base_t, StructType):
                raise SemanticError("Acesso '.' aplicado a não-struct.", ln)

            struct = self.structs.get(base_t.name)
            if struct is None:
                raise SemanticError(f"struct '{base_t.name}' não declarado.", ln)

            if expr.field not in struct["fields"]:
                raise SemanticError(
                    f"Campo '{expr.field}' não existe em struct '{base_t.name}'.", ln
                )

            field_t = struct["fields"][expr.field]
            expr.vartype = field_t
            return field_t


        # STRUCT ARROW ACCESS
        elif isinstance(expr, ArrowAccess):
            base_t = self.visit_expr(expr.base)
            expr.base.vartype = base_t

            # 🔥 CASO DE ERRO DE PRECEDÊNCIA / PARSER
            if isinstance(base_t, StructType):
                raise SemanticError(
                    "Uso inválido de '->'. O operador '->' requer um ponteiro para struct.",
                    ln
                )

            if not isinstance(base_t, PointerType):
                raise SemanticError(
                    "Operador '->' aplicado a não-ponteiro.",
                    ln
                )

            if not isinstance(base_t.base, StructType):
                raise SemanticError(
                    "Operador '->' aplicado a ponteiro que não aponta para struct.",
                    ln
                )

            struct = self.structs.get(base_t.base.name)
            if struct is None:
                raise SemanticError(
                    f"struct '{base_t.base.name}' não declarado.",
                    ln
                )

            if expr.field not in struct["fields"]:
                raise SemanticError(
                    f"Campo '{expr.field}' não existe em struct '{base_t.base.name}'.",
                    ln
                )

            field_t = struct["fields"][expr.field]
            expr.vartype = field_t
            return field_t

        # SIZEOF
        elif isinstance(expr, SizeOf):
            target_type = None

            if isinstance(expr.target, Type):
                target_type = expr.target
            else:
                target_type = self.visit_expr(expr.target)
            
            try:
                size_val = self.sizeof(target_type)
            except SemanticError as e:
                raise SemanticError(str(e), ln)

            expr.__class__ = Const
            expr.value = size_val
            expr.literal_type = "int"
            expr.vartype = IntType()
            
            self.push(f"      ✔ sizeof resolvido: {self.type_name(target_type)} -> {size_val} palavra(s) de 16-bits")
            return expr.vartype

        return None


    def sizeof(self, t):
        if isinstance(t, IntType):
            return 1
        if isinstance(t, CharType):
            return 1
        if isinstance(t, PointerType):
            return 1
        if isinstance(t, ArrayType):
            return t.size * self.sizeof(t.base)
        if isinstance(t, StructType):
            if t.name not in self.structs:
                raise SemanticError(f"struct '{t.name}' não declarado")
            return self.structs[t.name]["size"]
        if t is None:
            raise SemanticError("sizeof(void) não permitido.")
        raise SemanticError(f"sizeof não suportado para tipo {t}")


    def ensure_vartype(self, expr):
        if not isinstance(expr, Var):
            return

        # --- CONTAGEM DE USO PARA AVISOS ---
        if self.local_usage is not None and expr.name in self.local_usage:
            self.local_usage[expr.name]['count'] += 1
        elif expr.name in self.global_usage:
            self.global_usage[expr.name]['count'] += 1
        # -----------------------------------

        if expr.vartype is None:
            t = self.current_scope.get(expr.name, self.global_scope.get(expr.name))
            if t is None:
                # --- FIX: Se for uma função, converte para ponteiro de função ---
                if expr.name in self.functions:
                    expr.vartype = PointerType(IntType())
                    return
                # -----------------------------------------------------------------
                raise SemanticError(
                    f"Variável '{expr.name}' sem tipo resolvido (erro interno do semântico).",
                    get_lineno(expr)
                )
            expr.vartype = t

    def decay(self, t):
        if isinstance(t, ArrayType):
            return PointerType(t.base)
        return t
