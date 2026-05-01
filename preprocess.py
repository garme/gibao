import os
import re

class PreprocessorError(Exception):
    def __init__(self, message):
        super().__init__(f"Erro de Pré-processador: {message}")

class Preprocessor:
    STDLIB_DIR = "stdlib"
    LOCAL_INCLUDE_DIRS = ["./"]

    # --- REGEX ATUALIZADO: Suporte a ifdef e ifndef ---
    inc_pattern = re.compile(r'^\s*#\s*include\s*(<([^>]+)>|"([^"]+)")')
    define_pattern = re.compile(r'^\s*#\s*define\s+([A-Za-z_]\w*)\s*(.*)')
    undef_pattern = re.compile(r'^\s*#\s*undef\s+([A-Za-z_]\w*)')
    
    # MODIFICAÇÃO: Atualizado para capturar ifdef e ifndef
    if_pattern = re.compile(r'^\s*#\s*(if|ifdef|ifndef|elif)\s+(.*)')
    
    else_pattern = re.compile(r'^\s*#\s*else')
    endif_pattern = re.compile(r'^\s*#\s*endif')

    # ANSI colors (opcionais)
    RED   = "\033[31m"
    GREEN = "\033[32m"
    BLUE  = "\033[34m"
    YELLOW = "\033[33m"
    CYAN  = "\033[36m"
    RESET = "\033[0m"

    def __init__(self, file_system=None, verbose=False, use_colors=False):
        self.macros = {}
        self.cond_stack = []  # format: [(active, matched)]
        self.log = []
        self.verbose = verbose
        self.use_colors = use_colors
        self.final_code = ""
        # Dicionário { "nome_arquivo": "conteúdo" } vindo do Front-end (VFS)
        self.file_system = file_system if file_system is not None else {}

    # -----------------------------
    # Helper: Remover Comentários (CORRIGIDO)
    # -----------------------------
    def remove_comments(self, text):
        """
        Remove comentários C (// e /* */) preservando strings e QUEBRAS DE LINHA.
        Evita que o Lexer perca a contagem original das linhas.
        """
        def replacer(match):
            s = match.group(0)
            if s.startswith('/'): 
                # Retorna um espaço e a MESMA quantidade de quebras de linha removidas!
                return " " + ("\n" * s.count('\n'))
            else: 
                return s # Retorna strings inalteradas
        
        # Regex complexo que casa: Comentários //, Comentários /* */, Strings "" e Strings ''
        pattern = re.compile(
            r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
            re.DOTALL | re.MULTILINE
        )
        return re.sub(pattern, replacer, text)
        
    # -----------------------------
    # Logging
    # -----------------------------
    def add_log(self, msg, line=None, category="INFO"):
        prefix = f"[{category}]"
        if line is not None:
            prefix += f" ({line})"

        entry = f"{prefix} {msg}"
        self.log.append(entry)

        if self.verbose:
            print(entry)

    def get_log(self):
        return "\n".join(self.log)

    # -----------------------------
    # Avaliação de expressões inteiras
    # -----------------------------
    def eval_int_expr(self, expr: str):
        for k, v in self.macros.items():
            if isinstance(v, int):
                expr = re.sub(rf'\b{k}\b', str(v), expr)

        # Substitui qualquer palavra restante (macros indefinidas) por '0'
        expr = re.sub(r'\b[A-Za-z_]\w*\b', '0', expr)

        try:
            return int(eval(expr, {"__builtins__": None}, {}))
        except Exception as e:
            raise PreprocessorError(f"Erro ao avaliar expressão '{expr}': {e}")

    # -----------------------------
    # Processamento de includes (MANTIDO)
    # -----------------------------
    def handle_include(self, line, out_lines, lineno):
        m = self.inc_pattern.match(line)
        if not m: return False

        angle = m.group(2)
        quote = m.group(3)

        # 1. Include de Sistema <lib>
        if angle is not None:
            name = angle
            self.add_log(f'#include <{name}> -> referência mantida', lineno, "INCLUDE")
            out_lines.append(line + "\n")
            return True

        # 2. Include Local "file.h"
        if quote is not None:
            name = quote
            content = None
            origin = ""

            # A) Verifica no VFS (Memória)
            if name in self.file_system:
                content = self.file_system[name]
                origin = "VFS (Memória)"
            
            # B) Verifica no Disco Físico
            else:
                for d in self.LOCAL_INCLUDE_DIRS:
                    path = os.path.join(d, name)
                    if os.path.exists(path):
                        origin = f"Disco ({path})"
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                content = f.read()
                            break
                        except Exception as e:
                            raise PreprocessorError(f"Erro ao ler arquivo '{path}': {e}")

            if content is not None:
                self.add_log(f'#include "{name}" -> encontrado em {origin}', lineno, "INCLUDE")
                
                # Recursividade
                included_processed_code = self.preprocess(content)
                
                # --- FIX: ACHATA O CÓDIGO INCLUÍDO PARA 1 LINHA ---
                # Como C ignora espaços em branco, transformamos todo o arquivo incluído
                # em uma única linha longa. Isso garante que a diretiva #include ocupe 
                # apenas a 1 linha original, mantendo a sincronia perfeita!
                flat_code = included_processed_code.replace('\n', ' ')
                
                out_lines.append(flat_code + "\n")
                return True
            
            raise PreprocessorError(f'Arquivo não encontrado para include "{name}".')

        return False

    # -----------------------------
    # Define / undef
    # -----------------------------
    def handle_define(self, line, lineno):
        m = self.define_pattern.match(line)
        if not m: return False

        name, value = m.group(1), m.group(2).strip()

        if value == "":
            self.macros[name] = ""
            self.add_log(f"#define {name} -> vazio", lineno, "DEFINE")
        else:
            try:
                val = self.eval_int_expr(value)
                self.macros[name] = val
                self.add_log(f"#define {name} {value} -> {val}", lineno, "DEFINE")
            except:
                self.macros[name] = value
                self.add_log(f"#define {name} {value} -> texto", lineno, "DEFINE")

        return True

    def handle_undef(self, line, lineno):
        m = self.undef_pattern.match(line)
        if not m: return False

        name = m.group(1)
        if name in self.macros:
            del self.macros[name]
        return True

    # -----------------------------
    # Substituição de macros
    # -----------------------------
    def substitute_macros(self, line, lineno):
        for k in sorted(self.macros.keys(), key=lambda s: -len(s)):
            v = str(self.macros[k])
            pattern = rf'\b{re.escape(k)}\b'
            if re.search(pattern, line):
                line = re.sub(pattern, v, line)
                self.add_log(f"Expansão: {k} -> {v}", lineno, "EXPAND")
        return line

    # -----------------------------
    # Condicionais (CORRIGIDO E EXPANDIDO)
    # -----------------------------
    def handle_conditionals(self, line, lineno):
        m = self.if_pattern.match(line)
        if m:
            directive, expr = m.group(1), m.group(2).strip()
            cond = False
            
            # Avalia a condição baseada na diretiva
            if directive == "if":
                try: cond = (self.eval_int_expr(expr) != 0)
                except: cond = False
            elif directive == "ifdef":
                cond = (expr in self.macros)
            elif directive == "ifndef":
                cond = (expr not in self.macros)
            
            # Lógica de elif (requer pilha existente)
            if directive == "elif":
                if not self.cond_stack: raise PreprocessorError("#elif sem #if")
                _, matched_previously = self.cond_stack[-1]
                if matched_previously:
                    self.cond_stack[-1] = (False, True)
                else:
                    # Avalia a expressão do elif como um 'if' normal
                    try: val = (self.eval_int_expr(expr) != 0)
                    except: val = False
                    self.cond_stack[-1] = (val, val or matched_previously)
            else:
                # Push para if, ifdef, ifndef
                self.cond_stack.append((cond, cond))
                
            return True

        if self.else_pattern.match(line):
            if not self.cond_stack: raise PreprocessorError("#else sem #if")
            _, matched_previously = self.cond_stack[-1]
            if matched_previously:
                self.cond_stack[-1] = (False, True)
            else:
                self.cond_stack[-1] = (True, True)
            return True

        if self.endif_pattern.match(line):
            if not self.cond_stack: raise PreprocessorError("#endif sem #if")
            self.cond_stack.pop()
            return True

        return False

    # -----------------------------
    # Pré-processamento principal
    # -----------------------------
    def preprocess(self, source_code: str):
        out_lines = []
        lineno = 0

        lines = source_code.splitlines()
        
        for raw_line in lines:
            lineno += 1
            line = raw_line.rstrip("\n")

            # Lógica de Condicionais (Skip block)
            if self.cond_stack:
                active, _ = self.cond_stack[-1]
                if not active:
                    if self.handle_conditionals(line, lineno): 
                        out_lines.append("\n") # Mantém a linha vazia
                        continue
                    out_lines.append("\n") # Código desativado vira linha vazia
                    continue

            if self.handle_conditionals(line, lineno): 
                out_lines.append("\n")
                continue
            
            if self.handle_include(line, out_lines, lineno): 
                continue # Include injeta várias linhas, o shift é inevitável aqui

            if self.handle_define(line, lineno): 
                out_lines.append("\n") # Substitui o #define por linha vazia
                continue
                
            if self.handle_undef(line, lineno): 
                out_lines.append("\n")
                continue

            expanded = self.substitute_macros(line, lineno)
            out_lines.append(expanded + "\n")

        # Junta todas as linhas processadas
        raw_result = "".join(out_lines)
        
        # --- LIMPEZA FINAL ---
        # Remove todos os comentários para entregar código limpo ao Lexer
        self.final_code = self.remove_comments(raw_result)
        
        return self.final_code

    def get_final_code(self):
        return self.final_code
