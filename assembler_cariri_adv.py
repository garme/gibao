from pyparsing import *
import re

class AssemblerCariri:
    def __init__(self):
        # Mapa de instruções
        self.instrucoes = {
            "LDA": "0", "STA": "1", "INT": "2", "CALL": "3", "ADD": "4", "SUB": "5", 
            "SOP": "6", "MOV": "7", "JMP": "8", "JN": "9", "JZ": "a", "LDI": "b", 
            "STI": "c", "NAND": "d", "SHIFT": "e", "RET": "f"
        }

        # Mapa reverso
        self.codigos = {v: k for k, v in self.instrucoes.items()}

        self.ops_sem_ops = ['RET']
        self.org_op = ['ORG']
        
        # Mapeamento de registradores especiais
        self.special_reg_map = {
            '-$CS': 'ff1', '-$DS': 'ff2', '-$SS': 'ff3', '-$SP': 'ff4',
            '$CS': 'ff5', '$DS': 'ff6', '$SS': 'ff7', '$SP': 'ff8'
        }

        self.tabela_simbolos = [] 
        
        self.CS = 0
        self.DS = 0
        self.SS = 0
        self.stack_size = 0
        
        self.codigo = None
        self.assembled_code = None

# =======================================================================
#  BNF / PARSER
# =======================================================================
    def parser(self, codigo):
        
        CHAR = Regex(r"[^'\n]") 
        valid_string_chars = "".join(c for c in printables if c != '"') + " "
        STRING = Word(valid_string_chars)
        
        NOME = Word(alphas, alphanums + '_')
        
        NUM_BINARIO = Combine(Word("01") + CaselessLiteral("b"))
        NUM_BINARIO.setParseAction(lambda t: str(int(t[0][:-1], 2) & 0xFFFF))
        
        NUM_HEX = CaselessLiteral("0x").suppress() + Word(hexnums)
        NUM_HEX.setParseAction(lambda t: str(int(t[0], 16) & 0xFFFF))
        
        NUM_DECIMAL = Word("-"+nums, nums)
        NUM_DECIMAL.setParseAction(lambda t: str(int(t[0]) & 0xFFFF))
        
        NUMERO = (NUM_HEX | NUM_BINARIO | NUM_DECIMAL)
        
        NUMERO12B = NUMERO.copy().setParseAction(lambda t: str(int(t[0]) & 0xFFF))
        ENDERECO = Literal("@").suppress() + NUMERO12B

        LABEL = NOME + Literal(":").suppress()
        # Ação para registrar todos os labels encontrados na lista bruta (para debug)
        LABEL.setParseAction(lambda t: self.tabela_simbolos.append(t[0])) 
        
        COMENTARIOS = OneOrMore(Literal(";") + restOfLine).suppress()

        REG_NAMES = Combine(Optional(Literal("-")) + Literal("$") + oneOf("cs ds ss sp", caseless=True))
        OPERANDO = (NOME | ENDERECO)
        OPERANDO_MOV = (REG_NAMES | NUMERO12B | NOME | ENDERECO)

        ops_especiais = ["RET", "MOV"]
        keys_genericas = [k for k in self.instrucoes.keys() if k not in ops_especiais]
        
        MNEMONIC = oneOf(" ".join(keys_genericas), caseless=True)
        RET = CaselessLiteral("RET")
        ORG = CaselessLiteral("ORG")
        MOV = CaselessLiteral("MOV")

        # --- CORREÇÃO: Adicionado Group(LABEL) para aceitar labels isolados ---
        INSTRUCAO = (
            Group(Optional(LABEL) + RET) |                     
            Group(Optional(LABEL) + MOV + OPERANDO_MOV) |      
            Group(Optional(LABEL) + MNEMONIC + OPERANDO) |     
            Group(ORG + NUMERO12B) |
            Group(LABEL) # <--- Linha nova: Permite label sozinho na linha
        ) + Optional(COMENTARIOS)
        
        CODE_SEG = CaselessLiteral(".code").suppress() + Optional(COMENTARIOS) + OneOrMore(INSTRUCAO)

        QUOTED_STRING = Group(Literal("\"") + STRING + Literal("\""))
        QUOTED_CHAR   = Group(Literal("'") + CHAR + Literal("'"))

        LIST_ELEM = (QUOTED_CHAR | QUOTED_STRING | NUMERO | NOME)
        LISTA_VALORES = Group(delimitedList(LIST_ELEM))

        DATA_OP = oneOf("DD DB INITD INITB", caseless=True)
        DATA_ARGS = (LISTA_VALORES | NUMERO | NOME | ENDERECO | QUOTED_CHAR | QUOTED_STRING)
        
        DATA_DEF = Group(Optional(LABEL) + DATA_OP + DATA_ARGS) + Optional(COMENTARIOS)
        DATA_SEG = CaselessLiteral(".data").suppress() + Optional(COMENTARIOS) + Optional(OneOrMore(DATA_DEF | Group(ORG + NUMERO12B)))

        BSS_OP = oneOf("RESB RESD", caseless=True)
        BSS_DEF = Group(Optional(LABEL) + BSS_OP + NUMERO) + Optional(COMENTARIOS)
        BSS_SEG = CaselessLiteral(".bss").suppress() + Optional(COMENTARIOS) + OneOrMore(BSS_DEF | Group(ORG + NUMERO12B))

        STACK_SEG = CaselessLiteral(".stack").suppress() + NUMERO + Optional(COMENTARIOS)

        PROGRAMA = Optional(COMENTARIOS) + CODE_SEG + Optional(DATA_SEG) + Optional(BSS_SEG) + STACK_SEG

        self.tabela_simbolos = []
        self.codigo = PROGRAMA.parseString(codigo)

    # Heurística melhorada para detecção de Opcode
    def _detect_op_index(self, tokens):
        if len(tokens) >= 3:
            return 1
        if len(tokens) == 2:
            first = str(tokens[0]).upper()
            second = str(tokens[1]).upper()
            if first in self.instrucoes or first == "ORG": return 0
            if second in self.instrucoes or second == "ORG": return 1
            return 0
        return 0

    def assemble_code(self, codigo):
        try:
            self.parser(codigo)
            self.step_one()
            self.step_two()
            
            # Lógica de erro semântico exigida pelo Desktop antigo
            if isinstance(self.assembled_code, str):
                linhas = codigo.split("\n")
                
                simbolo_falho = None
                if "'" in self.assembled_code:
                    simbolo_falho = self.assembled_code.split("'")[1]
                    
                for linha in range(len(linhas)):
                    # Procura apenas o símbolo na linha original do código
                    if simbolo_falho and simbolo_falho in linhas[linha].split():
                        return ("Error", "Semantic", linha+1)
                    # Mantém o seu código antigo como segurança para outros erros
                    elif self.assembled_code in linhas[linha]:
                        return ("Error", "Semantic", linha+1)
                        
                return ("Error", "Semantic", 0) # Fallback
            
            return ("Ok", self.assembled_code)
            
        except ParseException as e:
            # Envia a tupla (linha, coluna) que a GUI Desktop espera
            return ("Error", "Syntactic", (str(e.lineno), str(e.col)))
        except AttributeError:  
            # O Desktop espera apenas 2 parâmetros aqui
            return ("Error", "Platform")

    def get_code_report(self, codigo):
        try:
            # Gera o código primeiro usando a nossa função adaptada
            res = self.assemble_code(codigo)
            if res[0] == "Error": 
                return res # Repassa o erro exatamente no formato Desktop

            # Se deu OK, constrói a string do relatório
            s = f" {'='*25}\n    SYMBOL TABLE\n {'-'*25}\n SYM\tADD\n {'-'*11}\n"
            for i in sorted(self.tabela_simbolos.keys()):
                s += f" {i} \t{format(int(self.tabela_simbolos[i]), '03x')}\n"
                
            s += f"\n {'='*25}\n SEGMENTS ADDRESSES\n {'-'*25}\n SEG\tADD\n {'-'*11}\n"
            s += f" TEXT:\t{self.CS}\n DATA:\t{self.DS}\n STACK:\t{self.SS}\n\n"
            s += f" {'='*25}\n STACK: {self.stack_size} palavras\n {'-'*25}\n\n"
            
            s += f" {'='*25}\n    GENERATED CODE\n {'-'*25}\n ADD\tINS\n {'-'*11}\n"
            for i, code in enumerate(self.assembled_code):
                s += f" {format(i, '03x')} \t{code}\n"
                
            return ("Ok", s + f"\n {'='*25}")
            
        except ParseException as e:
            return ("Error", "Syntactic", (str(e.lineno), str(e.col)))
        except AttributeError:  
            return ("Error", "Platform")

# =======================================================================
#  ASSEMBLER LOGIC
# =======================================================================
    def step_one(self):
        c = self.codigo[:]
        endereco = 0
        nova_tabela = {}
        
        # MPU: Forçamos as bases arquiteturais de 4KB
        CS = 0
        DS = 4096 
        SS = 4096 
        
        var_ops = ["DD", "DB", "RESB", "RESD", "INITD", "INITB"]
        in_data_section = False # Flag para saber se já chegamos nos dados

        while c:
            linha = c.pop(0)
            
            if isinstance(linha, str) and linha.isdigit():
                self.stack_size = int(linha)
                continue

            if len(linha) == 1:
                token = str(linha[0]).upper()
                if token not in self.instrucoes and token not in var_ops and token != "ORG":
                    nova_tabela[linha[0]] = str(endereco)
                    continue 

            op_idx = self._detect_op_index(linha)
            token_op = ""
            if len(linha) > op_idx:
                token_op = str(linha[op_idx]).upper()
            
            # =======================================================
            # MPU LOGIC: Salta o contador para o bloco de 4KB
            # =======================================================
            if token_op in var_ops and not in_data_section:
                in_data_section = True
                if endereco < 4096:
                    endereco = 4096 # Move o apontador virtual para 0x1000
            
            if op_idx == 1:
                label_name = linha[0]
                nova_tabela[label_name] = str(endereco)

            incremento = 1

            if token_op in var_ops:
                val = linha[-1]
                if token_op in ["DB", "INITB"]:
                    if isinstance(val, (list, ParseResults)): 
                        incremento = 0
                        for item in val:
                            if isinstance(item, (list, ParseResults)) and len(item) >= 2 and item[0] == '"': 
                                incremento += len(item[1])
                            elif isinstance(item, (list, ParseResults)) and len(item) >= 2 and item[0] == "'": 
                                incremento += 1
                            else:
                                incremento += 1
                    else:
                        incremento = 1

                elif token_op in ["RESB", "RESD"]:
                    incremento = int(val)
                elif token_op in ["INITD"]:
                    if isinstance(val, (list, ParseResults)):
                        incremento = len(val)
                    else:
                        incremento = 1
            
            elif token_op == "ORG":
                incremento = int(linha[1])
            
            endereco += incremento
            SS = endereco

        if DS == CS: DS = SS
        
        self.tabela_simbolos = nova_tabela
        self.CS, self.DS, self.SS = CS, DS, SS

# =======================================================================
    def step_two(self):
        c = self.codigo[:]
        codigo_final = []

        in_data_section_step2 = False

        while c:
            linha = c.pop(0)
            if isinstance(linha, str): continue

            tokens = [x if not isinstance(x, str) else x for x in linha]
            
            # Se for label isolado, ignora na geração de código
            if len(tokens) == 1:
                token = str(tokens[0]).upper()
                # Verifica se NÃO é instrução (ex: RET)
                if token not in self.instrucoes and token != "ORG":
                     continue

            op_idx = self._detect_op_index(tokens)
                
            token_op = ""
            if len(tokens) > op_idx:
                token_op = str(tokens[op_idx]).upper()

            # --- DADOS ---
            if token_op in ["DD", "DB", "RESB", "RESD", "INITD", "INITB"]:
                
                # =======================================================
                # MPU LOGIC: Padding físico da memória até 0x1000
                # =======================================================
                if not in_data_section_step2:
                    in_data_section_step2 = True
                    tamanho_atual = len(codigo_final)
                    if tamanho_atual < 4096:
                        # Preenche com "0000" até bater 4096
                        codigo_final.extend(["0000"] * (4096 - tamanho_atual))
                
                val = tokens[-1]
                
                if token_op in ["RESD", "RESB"]:
                    codigo_final.extend(["0000"] * int(val))
                
                elif token_op in ["DD", "INITD"]:
                    items = val if isinstance(val, (list, ParseResults)) else [val]
                    for item in items:
                        if isinstance(item, (list, ParseResults)): continue 

                        if item in self.tabela_simbolos:
                            codigo_final.append(format(int(self.tabela_simbolos[item]), "04x"))
                        else:
                            try:
                                codigo_final.append(format(int(item), "04x"))
                            except ValueError:
                                self.assembled_code = f"Erro de montagem: Valor inválido '{item}'"
                                return

                elif token_op in ["DB", "INITB"]:
                    items = val if isinstance(val, (list, ParseResults)) else [val]
                    for item in items:
                        if isinstance(item, (list, ParseResults)) and len(item) >= 2 and item[0] == '"':
                            content = item[1]
                            for char in content: codigo_final.append(format(ord(char), "04x"))
                        elif isinstance(item, (list, ParseResults)) and len(item) >= 2 and item[0] == "'":
                            char = item[1]
                            codigo_final.append(format(ord(char), "04x"))
                        elif isinstance(item, str):
                            if item in self.tabela_simbolos:
                                val_label = int(self.tabela_simbolos[item])
                                codigo_final.append(format(val_label, "04x"))
                            elif item.isdigit() or (item.startswith('-') and item[1:].isdigit()):
                                codigo_final.append(format(int(item), "04x"))
                continue

            # --- INSTRUÇÕES ---
            if token_op == "ORG":
                codigo_final.extend(["0000"] * int(tokens[1]))
                continue

            if token_op in self.instrucoes:
                opcode = self.instrucoes[token_op]
                
                if token_op == "RET":
                    codigo_final.append(opcode + "000")
                    continue
                
                operando_raw = tokens[op_idx + 1]
                
                if str(operando_raw).upper() in self.special_reg_map:
                    codigo_final.append(opcode + self.special_reg_map[str(operando_raw).upper()])
                    continue
                
                if operando_raw in self.tabela_simbolos:
                    # ========================================================
                    # MPU LOGIC: Converte endereço absoluto em Offset (12 bits)
                    # ========================================================
                    valor_abs = int(self.tabela_simbolos[operando_raw])
                    
                    if token_op in ["JMP", "JN", "JZ", "CALL"]:
                        # Saltos são relativos ao Code Segment
                        valor = (valor_abs - self.CS) & 0xFFF
                    elif token_op in ["LDA", "STA", "ADD", "SUB", "NAND", "SHIFT", "LDI", "STI", "SOP", "INT"]:
                        # Acessos à memória são relativos ao Data Segment
                        valor = (valor_abs - self.DS) & 0xFFF
                    else:
                        # Para MOV e outras diretivas, mantém o valor absoluto
                        valor = valor_abs & 0xFFF
                else:
                    try:
                        valor = int(operando_raw) & 0xFFF # Garante o limite de 12 bits
                    except ValueError:
                        self.assembled_code = f"Erro: Label '{operando_raw}' não encontrado."
                        return

                codigo_final.append(opcode + format(valor, "03x"))

        self.assembled_code = codigo_final

# =======================================================================
# =======================================================================
    def get_variables_addresses(self):
        from pyparsing import ParseResults # Garantia de importação para validação de tipo
        
        # 1. BLINDAGEM DESKTOP: 
        # Se o CompSim.py chamar este método antes do step_one() ser executado,
        # a tabela será uma lista crua. Forçamos a geração do dicionário aqui.
        if isinstance(self.tabela_simbolos, list):
            if self.codigo is not None:
                self.step_one()
            else:
                return {}

        mapa = {}
        
        # 2. Agora temos garantia matemática de que é um dicionário
        for var, addr_str in self.tabela_simbolos.items():
            addr = int(addr_str)
            found = False
            
            for linha in self.codigo:
                if not isinstance(linha, str) and len(linha) >= 3 and linha[0] == var:
                    op = str(linha[1]).upper()
                    size = 1
                    
                    if op in ["RESB", "RESD"]: 
                        size = int(linha[2])
                    elif op in ["DB", "INITB"]:
                        val = linha[-1]
                        if isinstance(val, (list, ParseResults)):
                            size = 0
                            for item in val:
                                if isinstance(item, (list, ParseResults)) and len(item) >= 2 and item[0] == '"': 
                                    size += len(item[1])
                                else: 
                                    size += 1
                        else:
                            size = 1
                            
                    elif op in ["INITD", "DD"] and isinstance(linha[2], (list, ParseResults)): 
                        size = len(linha[2])
                    
                    mapa[var] = [addr + i for i in range(size)]
                    found = True
                    break
            
            # Se não for um array com tamanho explícito, mas estiver na área de Dados, 
            # assume tamanho 1
            if not found and addr >= self.DS:
                 mapa[var] = [addr]
                 
        return mapa

    def configure_processor(self):
        # 1. Calcula quantas palavras as variáveis globais ocuparam (Ex: 517)
        tamanho_vars = self.SS - self.DS
        
        # 2. O SP inicial começa DEPOIS das variáveis globais
        sp_inicial = tamanho_vars + int(self.stack_size)
        
        # 3. MPU: O Segmento de Pilha (SS) deve ser idêntico ao de Dados (DS)
        # para que o malloc do SO funcione em harmonia com as instruções PUSH/POP
        return (self.CS, self.DS, self.DS, sp_inicial)

    
    def get_memory_map(self):
        from pyparsing import ParseResults 
        if self.codigo is None: return ""
        s = ''
        c = 0
        in_data = False # <--- Nova Flag
        
        for item in self.codigo:
            if isinstance(item, str): continue
            
            # Verifica se é label isolado
            if len(item) == 1 and str(item[0]).upper() not in self.instrucoes and str(item[0]).upper() != "ORG":
                 continue
                 
            op_idx = self._detect_op_index(item)
            token_op = str(item[op_idx]).upper() if len(item) > op_idx else ""

            if token_op == "ORG":
                try:
                    incremento = int(item[op_idx + 1])
                    for _ in range(incremento):
                        if self.assembled_code and c < len(self.assembled_code):
                            hex_val = self.assembled_code[c]
                            s += f"{format(c, '04x')} {hex_val} 0000 (ORG SKIP)\n"
                            c += 1
                except: pass
                continue

            if token_op in ["DD", "DB", "RESB", "RESD", "INITD", "INITB"]:
                # ========================================================
                # CORREÇÃO DA UI: Força o cursor a pular o Padding da MPU!
                # ========================================================
                if not in_data:
                    in_data = True
                    if c < self.DS:
                        c = self.DS
                
                incremento = 1
                val = item[-1]
                
                if token_op in ["DB", "INITB"]:
                    if isinstance(val, (list, ParseResults)):
                        incremento = 0
                        for v in val:
                            if isinstance(v, (list, ParseResults)) and len(v) >= 2 and v[0] == '"': 
                                incremento += len(v[1])
                            else: incremento += 1
                    else: incremento = 1
                elif token_op in ["RESB", "RESD"]:
                    incremento = int(val)
                elif token_op in ["INITD", "DD"]:
                    if isinstance(val, (list, ParseResults)): incremento = len(val)
                    else: incremento = 1
                
                for i in range(incremento):
                    if self.assembled_code and c < len(self.assembled_code):
                        hex_val = self.assembled_code[c]
                        prefix = f" [{i}]" if incremento > 1 else ""
                        s += f"{format(c, '04x')} {hex_val} {item}{prefix}\n"
                        c += 1
                continue

            if self.assembled_code and c < len(self.assembled_code):
                hex_val = self.assembled_code[c]
                s += f"{format(c, '04x')} {hex_val} {item}\n"
                c += 1

        return s
    
    def get_stack(self):
        return (self.SS, self.SS + int(self.stack_size))

    def get_data_as_hex(self, valor):
        return format(valor & 0xFFFF, "04x")
    
    def get_reserved_keywords(self):
        return ['.code', '.data', '.bss', '.stack', 
                'LDA', 'STA', 'INT', 'CALL', 'ADD', 'SUB','SOP', 
                'MOV', 'JMP', 'JN', 'JZ', 'LDI', 'STI', 'NAND', 
                'SHIFT', 'RET', 'DD', 'DB', 'RESD', 'RESB',
                'INITD', 'INITB', 'ORG']
                
    def get_comment_symbol(self):
        return ";"

if __name__ == "__main__":
    codigo = '''.code
    main: 
        SOP pop
    loop:
        JMP main
    end:
    .data
        pop: DD 0
        var: DD 0
    .stack 10
    '''
    asm = AssemblerCariri()
    print(asm.assemble_code(codigo))
