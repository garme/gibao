# ~ from .lexer import tokenize
# ~ from .compiler_ast import *
from lexer import tokenize
from compiler_ast import *

class SyntacticError(Exception):
    def __init__(self, message):
        super().__init__(f"Erro Sintático: {message}")

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.typedef_names = {}

    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ('EOF', '', -1)

    def match(self, expected_type):
        token = self.current()
        if token[0] == expected_type:
            self.pos += 1
            return token
        else:
            self.syntax_error(f"Esperado '{expected_type}', mas veio '{token[0]}'")


    # ============================================================
    # PROGRAMA
    # ============================================================
    def parse_program(self):
        imports = []
        declarations = []

        while self.current()[0] != 'EOF':
            tok_type = self.current()[0]
            tok_val  = self.current()[1]

            # ---------------------------
            # struct declaration
            # ---------------------------
            if (tok_type == 'STRUCT' and
                self.pos + 2 < len(self.tokens) and
                self.tokens[self.pos + 1][0] == 'ID' and
                self.tokens[self.pos + 2][0] == 'LBRACE'):
                declarations.append(self.parse_struct_decl())
                continue

            # ---------------------------
            # INCLUDE
            # ---------------------------
            if tok_type == 'INCLUDE':
                tok = self.match('INCLUDE')
                self.match('LANGLE')
                libtok = self.match('ID')
                self.match('RANGLE')
                imports.append(LibraryImport(libtok[1], lineno=tok[2]))
                continue

            # ---------------------------
            # CASO ESPECIAL: TYPEDEF
            # ---------------------------
            # Se começar com typedef, despachamos direto para parse_declaration
            if tok_type == 'TYPEDEF':
                # parse_declaration sabe lidar com typedef e retornará lista vazia
                decls = self.parse_declaration()
                if isinstance(decls, list):
                    declarations.extend(decls)
                continue
            
            # ---------------------------
            # CASO ESPECIAL: NAKED
            # ---------------------------
            is_naked = False
            if tok_type == 'NAKED':
                self.match('NAKED')
                is_naked = True
                # Atualiza tok_type para o próximo token (que deve ser o tipo: void, int...)
                tok_type = self.current()[0]

            # ---------------------------
            # Declaração de variável ou função
            # ---------------------------
            # Verifica se é um tipo primitivo OU se é um ID que foi definido via typedef
            is_primitive = tok_type in ('INT', 'CHAR', 'VOID', 'STRUCT')
            is_user_type = (tok_type == 'ID' and tok_val in self.typedef_names)

            if is_primitive or is_user_type:
                save = self.pos

                try:
                    t = self.parse_type()
                except SyntacticError:
                    self.pos = save
                    self.syntax_error("Tipo inválido na declaração/função")

                if self.current()[0] != 'ID':
                    self.pos = save
                    self.syntax_error("Esperado identificador após tipo")

                # Espia o próximo token para saber se é função '(' ou variável
                nexttok_type = self.tokens[self.pos+1][0] if self.pos+1 < len(self.tokens) else 'EOF'

                # ~ self.pos = save

                if nexttok_type == 'LPAREN':
                    self.pos = save
                    declarations.append(self.parse_function(is_naked=is_naked))
                else:
                    if is_naked:
                        self.syntax_error("'naked' só é permitido em declarações de função.")
                    
                    self.pos = save
                    decls = self.parse_declaration()
                    if isinstance(decls, list):
                        declarations.extend(decls)
                    else:
                        declarations.append(decls)
            else:
                self.syntax_error(f"Esperado tipo no início da declaração ou função. Encontrado: {tok_type}")

        # retorno final do programa
        prog_line = self.tokens[0][2] if self.tokens else 1
        return Program(imports + declarations, lineno=prog_line)

    # ============================================================
    # TIPOS
    # ============================================================

    def parse_type(self):
        tok = self.current()

        # 1. Tipos Primitivos
        if tok[0] == 'INT':
            self.match('INT')
            base = IntType()
        elif tok[0] == 'CHAR':
            self.match('CHAR')
            base = CharType()
        elif tok[0] == 'VOID':
            self.match('VOID')
            base = None
        elif tok[0] == 'STRUCT':
            self.match('STRUCT')
            name = self.match('ID')
            base = StructType(name[1])
            
        # 2. Verifica se é um ID que já é um Typedef
        elif tok[0] == 'ID' and tok[1] in self.typedef_names:
            name = self.match('ID')[1]
            # Recupera o tipo base associado a esse nome
            base = self.typedef_names[name]
            
        else:
            self.syntax_error(f"Tipo inválido: {tok[0]}")

        # 3. Processa ponteiros (funciona para primitivos e typedefs)
        # Ex: typedef int* ptr; ptr* p2; (p2 vira int**)
        while self.current()[0] == 'TIMES':
            self.match('TIMES')
            base = PointerType(base)

        return base


    # ============================================================
    # FUNÇÃO
    # ============================================================

    def parse_function(self, is_naked=False):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        rettype = self.parse_type()
        nametok = self.match('ID')

        self.match('LPAREN')
        params = []

        if self.current()[0] != 'RPAREN':
            while True:
                ptype = self.parse_type()
                pid = self.match('ID')
                params.append(Param(pid[1], ptype, lineno=pid[2]))

                if self.current()[0] != 'COMMA':
                    break
                self.match('COMMA')

        self.match('RPAREN')

        self.match('LBRACE')
        body = self.parse_statements()
        self.match('RBRACE')

        func_node = Function(rettype, nametok[1], params, body, is_naked=is_naked, lineno=nametok[2])
        return self.set_bounds(func_node, start_idx, self.pos - 1)


    # ============================================================
    # DECLARAÇÕES
    # ============================================================
    def parse_declaration(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        # 1. Verifica se é um typedef
        is_typedef = False
        if self.current()[0] == 'TYPEDEF':
            self.match('TYPEDEF')
            is_typedef = True

        vartype = self.parse_type()
        names = []

        while True:
            idtok = self.match('ID')
            name = idtok[1]
            line = idtok[2]

            is_array = False
            array_size = None
            
            # array?
            if self.current()[0] == 'LBRACKET':
                self.match('LBRACKET')
                sizetok = self.match('NUM')
                array_size = int(sizetok[1])
                self.match('RBRACKET')
                is_array = True

            # inicialização?
            init = None
            if self.current()[0] == 'ASSIGN':
                # IMPACTO: Typedef não pode ter valor inicial
                if is_typedef:
                    self.syntax_error("'typedef' não pode ser inicializado com valor.")

                self.match('ASSIGN')

                # inicialização composta {...}
                if self.current()[0] == 'LBRACE':
                    self.match('LBRACE')
                    init_list = []

                    while True:
                        expr = self.parse_expression()
                        
                        # --- FIX: Validação semântica removida! O Parser confia na AST ---
                        init_list.append(expr)

                        if self.current()[0] != 'COMMA':
                            break
                        self.match('COMMA')

                    self.match('RBRACE')
                    init = init_list

                else:
                    expr = self.parse_expression()
                    # --- FIX: Validação semântica removida! O Parser confia na AST ---
                    init = [expr]

            # DECISÃO: É typedef ou variável?
            if is_typedef:
                # Cria o tipo composto (ex: array de int)
                final_type = vartype
                if is_array:
                    final_type = ArrayType(vartype, array_size)
                
                # Registra na tabela de tipos do PARSER (não gera AST)
                self.typedef_names[name] = final_type
            else:
                # Guarda na lista para criar nós da AST depois
                names.append((name, is_array, array_size, init, line))

            if self.current()[0] != 'COMMA':
                break
            self.match('COMMA')

        self.match('SEMI')

        # Se for typedef, retorna lista vazia (nada a fazer no backend)
        if is_typedef:
            return []

        # gera AST (Lógica original intacta)
        decls = []
        for name, is_array, size, init, line in names:
            if is_array:
                arrtype = ArrayType(vartype, size)
                node = ArrayDecl(name, arrtype, init, lineno=line)
            else:
                node = VarDecl(vartype, [(name, init)], lineno=line)
            decls.append(self.set_bounds(node, start_idx, self.pos - 1))

        return decls
        
    # ============================================================
    # ATRIBUIÇÃO
    # ============================================================

    def parse_assignment(self, inline=False):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.current()
        line = tok[2]

        # LHS
        if tok[0] == 'TIMES':
            self.match('TIMES')
            ptr = self.parse_term()
            target = Deref(ptr, lineno=line)

        elif tok[0] == 'ID':
            idtok = self.match('ID')
            name = idtok[1]
            line = idtok[2]

            if self.current()[0] == 'LBRACKET':
                self.match('LBRACKET')
                idx = self.parse_expression()
                self.match('RBRACKET')
                target = ArrayAccess(Var(name, lineno=line), idx, lineno=line)
            else:
                target = Var(name, lineno=line)

        else:
            self.syntax_error("Esperado TIMES ou ID no lado esquerdo da atribuição")

        # operador =, +=, -=
        op = self.current()[0]
        opline = self.current()[2]

        if op == 'ASSIGN':
            self.match('ASSIGN')
            value = self.parse_expression()
        elif op in ('PLUS_ASSIGN', 'MINUS_ASSIGN'):
            self.match(op)
            symbol = '+' if op == 'PLUS_ASSIGN' else '-'
            right = self.parse_expression()
            value = BinaryOp(symbol, target, right, lineno=opline)
        else:
            self.syntax_error(f"Esperado ASSIGN, += ou -=")

        if not inline:
            self.match('SEMI')

        assign_node = Assignment(target, value, lineno=line)
        return self.set_bounds(assign_node, start_idx, self.pos - 1)


    # ============================================================
    # RETURN
    # ============================================================

    def parse_return(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.match('RETURN')
        line = tok[2]

        if self.current()[0] == 'SEMI':
            self.match('SEMI')
            return self.set_bounds(Return(None, lineno=line), start_idx, self.pos - 1)

        expr = self.parse_expression()
        self.match('SEMI')
        return self.set_bounds(Return(expr, lineno=line), start_idx, self.pos - 1)

    # ============================================================
    # EXPRESSÕES E TERMOS (Refatorado)
    # ============================================================
    def parse_expression(self):
        # O ponto de entrada para todas as expressões agora é o OR Lógico
        return self.parse_logical_or()

    # 1. OR Lógico (Já implementado)
    def parse_logical_or(self):
        left = self.parse_logical_and()
        while self.current()[0] == 'LOR':
            tok = self.current()
            self.match('LOR')
            right = self.parse_logical_and()
            node = BinaryOp('||', left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 2. AND Lógico (Já implementado, mas ATUALIZADO para chamar Bitwise OR)
    def parse_logical_and(self):
        left = self.parse_bitwise_or()
        while self.current()[0] == 'LAND':
            tok = self.current()
            self.match('LAND')
            right = self.parse_bitwise_or()
            node = BinaryOp('&&', left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 3. Bitwise OR (|)
    def parse_bitwise_or(self):
        left = self.parse_bitwise_xor()
        while self.current()[0] == 'PIPE':
            tok = self.current()
            self.match('PIPE')
            right = self.parse_bitwise_xor()
            node = BinaryOp('|', left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 4. Bitwise XOR (^)
    def parse_bitwise_xor(self):
        left = self.parse_bitwise_and()
        while self.current()[0] == 'CARET':
            tok = self.current()
            self.match('CARET')
            right = self.parse_bitwise_and()
            node = BinaryOp('^', left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 5. Bitwise AND (&)
    def parse_bitwise_and(self):
        left = self.parse_equality()
        while self.current()[0] == 'AMP':
            tok = self.current()
            self.match('AMP')
            right = self.parse_equality()
            node = BinaryOp('&', left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 6. Igualdade (==, !=)
    def parse_equality(self):
        left = self.parse_relational()
        while self.current()[0] in ('EQ', 'NE'):
            tok = self.current()
            self.match(tok[0])
            op = '==' if tok[0] == 'EQ' else '!='
            right = self.parse_relational()
            node = BinaryOp(op, left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 7. Relacional (<, >, <=, >=)
    def parse_relational(self):
        left = self.parse_shift()
        while self.current()[0] in ('LT', 'GT', 'LE', 'GE'):
            tok = self.current()
            self.match(tok[0])
            op_map = {'LT': '<', 'GT': '>', 'LE': '<=', 'GE': '>='}
            right = self.parse_shift()
            node = BinaryOp(op_map[tok[0]], left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 8. Shift (<<, >>)
    def parse_shift(self):
        left = self.parse_additive()
        while self.current()[0] in ('LSHIFT', 'RSHIFT'):
            tok = self.current()
            self.match(tok[0])
            op = '<<' if tok[0] == 'LSHIFT' else '>>'
            right = self.parse_additive()
            node = BinaryOp(op, left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 9. Adição e Subtração (+, -)
    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.current()[0] in ('PLUS', 'MINUS'):
            tok = self.current()
            self.match(tok[0])
            op = '+' if tok[0] == 'PLUS' else '-'
            right = self.parse_multiplicative()
            node = BinaryOp(op, left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
        return left

    # 10. Multiplicação e Divisão (*, /)
    def parse_multiplicative(self):
        left = self.parse_term()
        
        while self.current()[0] in ('TIMES', 'DIV'):
            tok = self.current()
            self.match(tok[0])
            op = '*' if tok[0] == 'TIMES' else '/'
            
            right = self.parse_term()
            node = BinaryOp(op, left, right, lineno=tok[2])
            left = self._apply_binop_bounds(node, left, right, tok)
            
        return left

    # Nível 2: Operadores Unários (&, *, -, sizeof, CAST)
    def parse_term(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.current()
        ttype, tval, line = tok[:3]
        
        # ++
        if ttype == 'INC':
            self.match('INC')
            return self.set_bounds(PreInc(self.parse_term(), lineno=line), start_idx, self.pos - 1)
        
        # --
        elif ttype == 'DEC':
            self.match('DEC')
            return self.set_bounds(PreDec(self.parse_term(), lineno=line), start_idx, self.pos - 1)

        # & (AddressOf)
        elif ttype == 'AMP':
            self.match('AMP')
            operand = self.parse_term() 
            return self.set_bounds(AddressOf(operand, lineno=line), start_idx, self.pos - 1)

        # * (Deref)
        elif ttype == 'TIMES':
            self.match('TIMES')
            operand = self.parse_term()
            return self.set_bounds(Deref(operand, lineno=line), start_idx, self.pos - 1)

        # - (Unário)
        elif ttype == 'MINUS':
            self.match('MINUS')
            operand = self.parse_term()
            return self.set_bounds(UnaryOp('-', operand, lineno=line), start_idx, self.pos - 1)
        
        # + (Unário)
        elif ttype == 'PLUS':
            self.match('PLUS')
            operand = self.parse_term()
            return self.set_bounds(UnaryOp('+', operand, lineno=line), start_idx, self.pos - 1)
        
        # ~ (Bitwise NOT)
        elif ttype == 'TILDE':
            self.match('TILDE')
            operand = self.parse_term()
            return self.set_bounds(UnaryOp('~', operand, lineno=line), start_idx, self.pos - 1)
        
        # ! (Logic Not)
        elif ttype == 'LNOT':
            self.match('LNOT')
            return self.set_bounds(UnaryOp('!', self.parse_term(), lineno=line), start_idx, self.pos - 1)
            
        # --- NOVO: IMPLEMENTAÇÃO DO TYPE CAST (type) ---
        elif ttype == 'LPAREN':
            # Precisamos "espiar" o próximo token para saber se é Cast ou Agrupamento
            is_cast = False
            if self.pos + 1 < len(self.tokens):
                next_tok = self.tokens[self.pos + 1]
                nt_type, nt_val, _ = next_tok[:3]
                
                # 1. É um tipo primitivo? (int, char, void, struct)
                if nt_type in ('INT', 'CHAR', 'VOID', 'STRUCT'):
                    is_cast = True
                # 2. É um typedef conhecido? (ex: (FuncPtr) x)
                elif nt_type == 'ID' and nt_val in self.typedef_names:
                    is_cast = True
            
            if is_cast:
                self.match('LPAREN')
                # Chama o seu parse_type() original para ler o tipo
                target_type = self.parse_type() 
                self.match('RPAREN')
                
                # O operando do cast é o próximo termo (ex: o 'ptr' em '(int) ptr')
                operand = self.parse_term() 
                node = TypeCast(target_type, operand, lineno=line)
                return self.set_bounds(node, start_idx, self.pos - 1)
            
            # Se não for cast, cai na lógica padrão de parênteses (expressão)
            return self.parse_postfix()

        # sizeof
        elif ttype == 'SIZEOF':
            self.match('SIZEOF')
            target = None
            
            # Lógica de Lookahead para distinguir sizeof(Type) de sizeof(Expr)
            is_type = False
            
            if self.current()[0] == 'LPAREN':
                if self.pos + 1 < len(self.tokens):
                    next_tok = self.tokens[self.pos + 1]
                    nt_type, nt_val, _ = next_tok[:3]
                    
                    if nt_type in ('INT', 'CHAR', 'VOID', 'STRUCT'):
                        is_type = True
                    elif nt_type == 'ID' and nt_val in self.typedef_names:
                        is_type = True

            if is_type:
                # sizeof( TIPO )
                self.match('LPAREN')
                target = self.parse_type()
                self.match('RPAREN')
            else:
                # sizeof EXPRESSÃO
                target = self.parse_term()
            
            node = SizeOf(target, lineno=line)
            return self.set_bounds(node, start_idx, self.pos - 1)

        return self.parse_postfix()
        
        
    # Nível 1: Primários + Sufixos (., ->, [])
    def parse_postfix(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.current()
        ttype, tval, line = tok[:3]
        node = None

        # --- PRIMÁRIOS (Átomos) ---
        if ttype == 'LPAREN':
            self.match('LPAREN')
            node = self.parse_expression() 
            self.match('RPAREN')

        elif ttype == 'NUM':
            self.match('NUM')
            node = Const(tval, literal_type="int", lineno=line)

        elif ttype == 'CHAR_LITERAL':
            self.match('CHAR_LITERAL')
            node = Const(tval, literal_type="char", lineno=line)

        elif ttype == 'STRING_LITERAL':
            self.match('STRING_LITERAL')
            raw = tval
            content = bytes(raw[1:-1], "utf-8").decode("unicode_escape")
            node = StringLiteral(content, lineno=line)

        elif ttype == 'ID':
            self.match('ID')
            name = tval
            # REMOVIDO: A detecção de Call não acontece mais aqui dentro!
            # Apenas criamos a Var. O loop de sufixos cuidará dos parênteses.
            node = Var(name, lineno=line)
        
        else:
             self.syntax_error(f"Termo inesperado: {ttype}")

        if node:
            self.set_bounds(node, start_idx, self.pos - 1)

        # --- SUFIXOS (Loop de maior precedência) ---
        # ADICIONADO: 'LPAREN' na lista de sufixos permitidos
        while self.current()[0] in ('LBRACKET', 'DOT', 'ARROW', 'LPAREN', 'INC', 'DEC'):
            tok = self.current()
            line = tok[2]

            if tok[0] == 'LBRACKET':
                self.match('LBRACKET')
                idx = self.parse_expression()
                self.match('RBRACKET')
                node = ArrayAccess(node, idx, lineno=line)
                self.set_bounds(node, start_idx, self.pos - 1)

            elif tok[0] == 'DOT':
                self.match('DOT')
                field = self.match('ID')[1]
                node = FieldAccess(node, field, lineno=line)
                self.set_bounds(node, start_idx, self.pos - 1)

            elif tok[0] == 'ARROW':
                self.match('ARROW')
                field = self.match('ID')[1]
                node = ArrowAccess(node, field, lineno=line)
                self.set_bounds(node, start_idx, self.pos - 1)

            # NOVA LÓGICA DE CHAMADA DE FUNÇÃO (Call)
            elif tok[0] == 'LPAREN':
                self.match('LPAREN')
                args = []
                if self.current()[0] != 'RPAREN':
                    args.append(self.parse_expression())
                    while self.current()[0] == 'COMMA':
                        self.match('COMMA')
                        args.append(self.parse_expression())
                self.match('RPAREN')
                # O 'node' atual vira o 'callee' da chamada
                node = Call(node, args, lineno=line)
                self.set_bounds(node, start_idx, self.pos - 1)
                
            elif tok[0] == 'INC':
                self.match('INC')
                # O node atual (ex: Var('i')) passa a ser o alvo do PostInc
                node = PostInc(node, lineno=line)
                self.set_bounds(node, start_idx, self.pos - 1)

            elif tok[0] == 'DEC':
                self.match('DEC')
                node = PostDec(node, lineno=line)
                self.set_bounds(node, start_idx, self.pos - 1)

        return node
        
    # ============================================================
    # COMANDOS
    # ============================================================

    def parse_statements(self):
        stmts = []

        while self.current()[0] not in ('RBRACE','EOF'):
            stmt_start_idx = self.pos # INJEÇÃO DE LIMITES (Comandos Genéricos)
            tok = self.current()
            ttype, tval, line = tok[:3]
            
            # comando vazio
            if ttype == 'SEMI':
                self.match('SEMI')
                continue

            # -------------------------------------------------------
            # 1. Declaração de Typedef dentro da função (Escopo local)
            # -------------------------------------------------------
            if ttype == 'TYPEDEF':
                # Consome o typedef e registra na tabela, mas não gera AST
                self.parse_declaration() 
                continue

            # -------------------------------------------------------
            # 2. Declarações de Variáveis (Primitivas ou via Typedef)
            # -------------------------------------------------------
            # Verifica se é int/char OU se é um ID que representa um tipo
            is_user_type = (ttype == 'ID' and tval in self.typedef_names)
            
            if ttype in ('INT', 'CHAR', 'VOID', 'STRUCT') or is_user_type:
                # Tratamento especial para struct proibido (já existente no seu código)
                if ttype == 'STRUCT':
                    if (self.pos + 2 < len(self.tokens) and
                        self.tokens[self.pos + 1][0] == 'ID' and
                        self.tokens[self.pos + 2][0] == 'LBRACE'):
                        self.syntax_error("Definição de struct não permitida dentro de função")

                decls = self.parse_declaration()
                if isinstance(decls, list):
                    stmts.extend(decls)
                continue

            # break
            if ttype == 'ID' and tval == 'break':
                self.match('ID')
                self.match('SEMI')
                stmts.append(self.set_bounds(Break(lineno=line), stmt_start_idx, self.pos - 1))
                continue

            # continue
            if ttype == 'ID' and tval == 'continue':
                self.match('ID')
                self.match('SEMI')
                stmts.append(self.set_bounds(Continue(lineno=line), stmt_start_idx, self.pos - 1))
                continue

            # -------------------------------------------------------
            # 3. Comandos / Expressões
            # -------------------------------------------------------
            # MODIFICAÇÃO 1: Adicionar 'INC' e 'DEC' para suportar prefixos (++i;)
            if ttype in ('ID', 'TIMES', 'INC', 'DEC', 'LPAREN'):
                expr = self.parse_expression()

                # atribuição (lvalue completo!)
                if self.current()[0] in ('ASSIGN','PLUS_ASSIGN','MINUS_ASSIGN'):
                    op = self.current()[0]
                    self.match(op)
                    value = self.parse_expression()
                    self.match('SEMI')
                    stmts.append(self.set_bounds(Assignment(expr, value, lineno=line), stmt_start_idx, self.pos - 1))
                    continue

                # chamada isolada ou incremento isolado
                # MODIFICAÇÃO 2: Permitir os nós de incremento e decremento
                if isinstance(expr, (Call, PreInc, PreDec, PostInc, PostDec)):
                    self.match('SEMI')
                    self.set_bounds(expr, stmt_start_idx, self.pos - 1)
                    stmts.append(expr)
                    continue

                self.syntax_error("Comando inválido (expressão sem efeito).")


            # return
            if ttype == 'RETURN':
                stmts.append(self.parse_return()); continue

            # if
            if ttype == 'IF':
                stmts.append(self.parse_if()); continue

            # while
            if ttype == 'WHILE':
                stmts.append(self.parse_while()); continue
                
            # switch
            if ttype == 'SWITCH':
                stmts.append(self.parse_switch()); continue

            # for
            if ttype == 'FOR':
                stmts.append(self.parse_for()); continue

            # *x = ... (Deref no início da linha)
            if ttype == 'TIMES':
                stmts.append(self.parse_assignment()); continue
                
            # asm
            if ttype == 'ASM':
                self.match('ASM')
                self.match('LPAREN')
                
                # Esperamos uma string literal: asm("MOV SP")
                str_tok = self.match('STRING_LITERAL')
                raw_str = str_tok[1]
                
                # Remove aspas e processa escapes (permite \n para múltiplas linhas)
                content = bytes(raw_str[1:-1], "utf-8").decode("unicode_escape")
                
                self.match('RPAREN')
                self.match('SEMI')
                
                stmts.append(self.set_bounds(Asm(content, lineno=line), stmt_start_idx, self.pos - 1))
                continue

            self.syntax_error(f"Comando inesperado: {ttype}")

        return stmts


    def parse_if(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.match('IF')
        line = tok[2]

        self.match('LPAREN')
        cond = self.parse_expression()
        self.match('RPAREN')

        self.match('LBRACE')
        then_body = self.parse_statements()
        self.match('RBRACE')

        else_body = None
        if self.current()[0] == 'ELSE':
            self.match('ELSE')
            self.match('LBRACE')
            else_body = self.parse_statements()
            self.match('RBRACE')

        if_node = If(cond, then_body, else_body, lineno=line)
        return self.set_bounds(if_node, start_idx, self.pos - 1)


    def parse_while(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.match('WHILE')
        line = tok[2]

        self.match('LPAREN')
        cond = self.parse_expression()
        self.match('RPAREN')

        self.match('LBRACE')
        body = self.parse_statements()
        self.match('RBRACE')

        while_node = While(cond, body, lineno=line)
        return self.set_bounds(while_node, start_idx, self.pos - 1)


    def parse_switch(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.match('SWITCH')
        line = tok[2]

        # 1. Avalia a expressão alvo: switch ( expressão )
        self.match('LPAREN')
        expr = self.parse_expression()
        self.match('RPAREN')

        self.match('LBRACE')
        cases = []

        # 2. Percorre o corpo procurando 'case' ou 'default'
        while self.current()[0] not in ('RBRACE', 'EOF'):
            case_start_idx = self.pos # INJEÇÃO DE LIMITES NO CASE
            tok_type = self.current()[0]
            case_line = self.current()[2]

            if tok_type == 'CASE':
                self.match('CASE')
                # Em C, o valor do case deve ser constante, mas a verificação disso 
                # deixaremos para o Analisador Semântico! Aqui, apenas lemos a expressão.
                case_val = self.parse_expression()
                self.match('COLON')
            elif tok_type == 'DEFAULT':
                self.match('DEFAULT')
                case_val = None  # None identifica que este é o bloco default
                self.match('COLON')
            else:
                self.syntax_error("Esperado 'case' ou 'default' dentro do switch")

            # 3. Lê os comandos que pertencem a este case até achar o próximo case, default ou fim do switch
            case_body = []
            while self.current()[0] not in ('CASE', 'DEFAULT', 'RBRACE', 'EOF'):
                # Como parse_statements le ate fechar chaves, temos que ler comando a comando aqui.
                # Para reaproveitar a sua lógica do parse_statements, vamos instanciar 
                # um "mini" loop de parse_statements aqui dentro.
                
                # Para simplificar sem reescrever seu parse_statements, podemos ler as 
                # statements empilhando-as manualmente, usando as mesmas regras:
                
                stmt_start_idx = self.pos
                ttype = self.current()[0]
                
                if ttype == 'SEMI':
                    self.match('SEMI')
                    continue
                
                if ttype == 'ID' and self.current()[1] == 'break':
                    self.match('ID')
                    self.match('SEMI')
                    case_body.append(self.set_bounds(Break(lineno=self.current()[2]), stmt_start_idx, self.pos - 1))
                    continue
                    
                # Delegamos para parse_statements mas controlando quando parar!
                # (Um jeito elegante no seu parser é capturar o comando único, mas como o C 
                # permite declarar blocos inteiros, vamos emular as chamadas principais)
                
                if ttype == 'IF': case_body.append(self.parse_if()); continue
                if ttype == 'WHILE': case_body.append(self.parse_while()); continue
                if ttype == 'FOR': case_body.append(self.parse_for()); continue
                if ttype == 'RETURN': case_body.append(self.parse_return()); continue
                
                if ttype in ('ID', 'TIMES', 'INC', 'DEC', 'LPAREN'):
                    expr_stmt = self.parse_expression()
                    if self.current()[0] in ('ASSIGN', 'PLUS_ASSIGN', 'MINUS_ASSIGN'):
                        op = self.current()[0]
                        self.match(op)
                        val = self.parse_expression()
                        self.match('SEMI')
                        case_body.append(self.set_bounds(Assignment(expr_stmt, val, lineno=self.current()[2]), stmt_start_idx, self.pos - 1))
                    elif isinstance(expr_stmt, (Call, PreInc, PreDec, PostInc, PostDec)):
                        self.match('SEMI')
                        self.set_bounds(expr_stmt, stmt_start_idx, self.pos - 1)
                        case_body.append(expr_stmt)
                    else:
                        self.syntax_error("Comando inválido no case.")
                    continue

                self.syntax_error(f"Comando inesperado no corpo do case: {ttype}")

            case_node = Case(case_val, case_body, lineno=case_line)
            cases.append(self.set_bounds(case_node, case_start_idx, self.pos - 1))

        self.match('RBRACE')
        
        switch_node = Switch(expr, cases, lineno=line)
        return self.set_bounds(switch_node, start_idx, self.pos - 1)


    def parse_for(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.match('FOR')
        line = tok[2]

        self.match('LPAREN')

        # 1. Inicialização
        init = self.parse_assignment(inline=True)
        self.match('SEMI')

        # 2. Condição
        cond = self.parse_expression()
        self.match('SEMI')

        # ----------------------------------------------------
        # 3. Incremento (AQUI ESTÁ A CORREÇÃO)
        # ----------------------------------------------------
        incr = self.parse_expression()
        
        # Se depois da expressão vier um sinal de igual, é uma atribuição (ex: i = i + 1)
        if self.current()[0] in ('ASSIGN', 'PLUS_ASSIGN', 'MINUS_ASSIGN'):
            op = self.current()[0]
            self.match(op)
            val = self.parse_expression()
            # Certifique-se de que o nome da sua classe é Assignment ou Assign
            incr = Assignment(incr, val, lineno=line)
        # ----------------------------------------------------

        self.match('RPAREN')

        self.match('LBRACE')
        body = self.parse_statements()
        self.match('RBRACE')

        for_node = For(init, cond, incr, body, lineno=line)
        return self.set_bounds(for_node, start_idx, self.pos - 1)


    # ============================================================
    # AJUDA
    # ============================================================

    def describe_expr(self, expr):
        if isinstance(expr, Const):
            return str(expr.value)
        if isinstance(expr, Var):
            return expr.name
        if isinstance(expr, AddressOf):
            return f'&{expr.var.name}'
        if isinstance(expr, Deref):
            return f'*{self.describe_expr(expr.ptr)}'
        if isinstance(expr, BinaryOp):
            return f'({self.describe_expr(expr.left)} {expr.op} {self.describe_expr(expr.right)})'
        if isinstance(expr, Call):
            args = ', '.join(self.describe_expr(a) for a in expr.args)
            return f'{expr.name}({args})'
        return '<expr>'


    def syntax_error(self, msg):
        tok = self.current()
        _, value, line = tok[:3]
        raise SyntacticError(f"Erro na linha {line}: {msg} (token: {value})")


    def parse_struct_decl(self):
        start_idx = self.pos # INJEÇÃO DE LIMITES
        tok = self.match('STRUCT')
        line = tok[2]

        name = self.match('ID')[1]

        self.match('LBRACE')
        fields = []

        while self.current()[0] != 'RBRACE':
            ftype = self.parse_type()
            fid = self.match('ID')
            line = fid[2]

            # array em campo de struct
            if self.current()[0] == 'LBRACKET':
                self.match('LBRACKET')
                sizetok = self.match('NUM')
                size = int(sizetok[1])
                self.match('RBRACKET')
                self.match('SEMI')

                field_type = ArrayType(ftype, size)
                fields.append((fid[1], field_type, line))
            else:
                self.match('SEMI')
                fields.append((fid[1], ftype, line))


        self.match('RBRACE')
        self.match('SEMI')

        struct_node = StructDecl(name, fields, lineno=line)
        return self.set_bounds(struct_node, start_idx, self.pos - 1)

    def set_bounds(self, node, start_idx, end_idx):
        """Injeta as coordenadas de início e fim no nó da AST."""
        if not node: return node
        
        start_tok = self.tokens[start_idx]
        # Previne erro se o end_idx passar do tamanho (EOF)
        end_tok = self.tokens[end_idx] if end_idx < len(self.tokens) else self.tokens[-1]
        
        node.lineno = start_tok[2]
        # Se o seu lexer já retornar a coluna, use start_tok[3]. 
        # Se não, defina como 0 por enquanto.
        node.colno = start_tok[3] if len(start_tok) > 3 else 0 
        
        node.end_lineno = end_tok[2]
        
        # A coluna final é a coluna do último token + o tamanho do texto dele
        if len(end_tok) > 3:
            node.end_colno = end_tok[3] + len(str(end_tok[1]))
        else:
            node.end_colno = 'end'
            
        return node
        
    def _apply_binop_bounds(self, node, left, right, op_tok):
        """Função auxiliar para injetar limites dinâmicos em nós binários."""
        if not node: return node
        
        node.lineno = getattr(left, 'lineno', op_tok[2])
        node.colno = getattr(left, 'colno', 0)
        
        node.end_lineno = getattr(right, 'end_lineno', op_tok[2])
        node.end_colno = getattr(right, 'end_colno', 'end')
        
        return node
