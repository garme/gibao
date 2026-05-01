from compiler_ast import *

class ASTFormatter:
    def __init__(self):
        self.indent_level = 0
        self.indent_str = "    " # 4 espaços

    def _get_indent(self):
        return self.indent_str * self.indent_level

    def format(self, node):
        if node is None: return ""
        # FIX: Proteção para formatar primitivos isolados (ex: o '0' do array de chars)
        if isinstance(node, (int, str, float, bool)): return str(node)
        
        method_name = f'visit_{node.__class__.__name__}'
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node):
        return f"/* TODO: Formatter for {node.__class__.__name__} */"

    # --- TIPOS DE DADOS ---
    def _format_type(self, t, name=""):
        if t is None: return f"void {name}".strip()
        t_name = t.__class__.__name__
        
        if t_name == 'IntType': return f"int {name}".strip()
        if t_name == 'CharType': return f"char {name}".strip()
        if t_name == 'VoidType': return f"void {name}".strip()
        if t_name == 'StructType': return f"struct {getattr(t, 'name', '')} {name}".strip()
        
        if t_name == 'PointerType': 
            return self._format_type(getattr(t, 'base', None), f"*{name}")
        if t_name == 'ArrayType': 
            return self._format_type(getattr(t, 'base', None), f"{name}[{getattr(t, 'size', '')}]")
            
        return f"unknown {name}".strip()

    # --- ESTRUTURAS PRINCIPAIS ---
    def visit_Program(self, node):
        code = ""
        for item in getattr(node, 'items', []):
            code += self.format(item) + "\n\n"
        return code.strip() + "\n"

    def visit_LibraryImport(self, node):
        name = getattr(node, 'name', '')
        
        # Se o Parser capturou o nome já com aspas (ex: "tasks_3.c"), nós mantemos (Inclusão local).
        if name.startswith('"') and name.endswith('"'):
            return f"#include {name}"
            
        # Caso contrário (ex: printint, os_core.h), formatamos com os chevrons padrão do C < >
        return f"#include <{name}>"
        
    def visit_StructDecl(self, node):
        code = f"{self._get_indent()}struct {node.name} {{\n"
        self.indent_level += 1
        for fname, ftype, _ in node.fields:
            code += f"{self._get_indent()}{self._format_type(ftype, fname)};\n"
        self.indent_level -= 1
        code += f"{self._get_indent()}}};"
        return code

    def visit_Function(self, node):
        # Modificador naked
        naked_str = "naked " if getattr(node, 'is_naked', False) else ""
        ret = self._format_type(node.rettype)
        params = ", ".join([self._format_type(p.vartype, p.name) for p in node.params])
        
        code = f"{self._get_indent()}{naked_str}{ret} {node.name}({params}) {{\n"
        self.indent_level += 1
        for stmt in node.body:
            # Garante que todo comando no corpo tenha indentação e quebra de linha
            stmt_code = self.format(stmt)
            if not stmt_code.startswith(self.indent_str):
                stmt_code = self._get_indent() + stmt_code
            if not stmt_code.endswith(";") and not stmt_code.endswith("}"):
                stmt_code += ";"
            code += stmt_code + "\n"
        self.indent_level -= 1
        code += f"{self._get_indent()}}}"
        return code

    # --- CONTROLE DE FLUXO ---
    def visit_If(self, node):
        code = f"{self._get_indent()}if ({self.format(node.condition)}) {{\n"
        self.indent_level += 1
        for stmt in node.then_body:
            code += f"{self.format(stmt)}\n" if str(self.format(stmt)).startswith(self.indent_str) else f"{self._get_indent()}{self.format(stmt)};\n"
        self.indent_level -= 1
        
        if node.else_body:
            code += f"{self._get_indent()}}} else {{\n"
            self.indent_level += 1
            for stmt in node.else_body:
                code += f"{self.format(stmt)}\n" if str(self.format(stmt)).startswith(self.indent_str) else f"{self._get_indent()}{self.format(stmt)};\n"
            self.indent_level -= 1
            
        code += f"{self._get_indent()}}}"
        return code

    def visit_While(self, node):
        code = f"{self._get_indent()}while ({self.format(node.condition)}) {{\n"
        self.indent_level += 1
        for stmt in node.body:
            code += f"{self.format(stmt)}\n" if str(self.format(stmt)).startswith(self.indent_str) else f"{self._get_indent()}{self.format(stmt)};\n"
        self.indent_level -= 1
        code += f"{self._get_indent()}}}"
        return code

    def visit_For(self, node):
        init = self.format(node.init).strip().rstrip(";")
        cond = self.format(node.condition).strip()
        incr = self.format(node.increment).strip().rstrip(";")
        
        code = f"{self._get_indent()}for ({init}; {cond}; {incr}) {{\n"
        self.indent_level += 1
        for stmt in node.body:
            code += f"{self.format(stmt)}\n" if str(self.format(stmt)).startswith(self.indent_str) else f"{self._get_indent()}{self.format(stmt)};\n"
        self.indent_level -= 1
        code += f"{self._get_indent()}}}"
        return code

    def visit_Switch(self, node):
        code = f"{self._get_indent()}switch ({self.format(node.expr)}) {{\n"
        self.indent_level += 1
        for case_node in node.cases:
            if case_node.value is None:
                code += f"{self._get_indent()}default:\n"
            else:
                code += f"{self._get_indent()}case {self.format(case_node.value)}:\n"
            
            self.indent_level += 1
            for stmt in case_node.body:
                code += f"{self.format(stmt)}\n" if str(self.format(stmt)).startswith(self.indent_str) else f"{self._get_indent()}{self.format(stmt)};\n"
            self.indent_level -= 1
        self.indent_level -= 1
        code += f"{self._get_indent()}}}"
        return code

    def visit_Return(self, node):
        if node.value:
            return f"{self._get_indent()}return {self.format(node.value)};"
        return f"{self._get_indent()}return;"

    def visit_Break(self, node): return f"{self._get_indent()}break;"
    def visit_Continue(self, node): return f"{self._get_indent()}continue;"
    
    def visit_Asm(self, node):
        return f"{self._get_indent()}asm(\"{node.content}\");"

    # --- EXPRESSÕES E OPERAÇÕES ---
    def visit_Assignment(self, node):
        # A atribuição no For pode vir sem self._get_indent() se chamada diretamente, então ajustamos
        if hasattr(node.value, 'op') and getattr(node.value, 'op') in ('+', '-') and isinstance(node.value.left, Var) and isinstance(node.target, Var) and node.value.left.name == node.target.name:
            # Açucar sintático (x = x + 1 vira x += 1) - Opcional
            return f"{self.format(node.target)} {node.value.op}= {self.format(node.value.right)}"
        return f"{self.format(node.target)} = {self.format(node.value)}"

    def visit_BinaryOp(self, node):
        return f"{self.format(node.left)} {node.op} {self.format(node.right)}"

    def visit_UnaryOp(self, node):
        return f"{node.op}{self.format(node.expr)}"

    def visit_PreInc(self, node): return f"++{self.format(node.target)}"
    def visit_PreDec(self, node): return f"--{self.format(node.target)}"
    def visit_PostInc(self, node): return f"{self.format(node.target)}++"
    def visit_PostDec(self, node): return f"{self.format(node.target)}--"
    
    def visit_AddressOf(self, node): return f"&{self.format(node.var)}"
    def visit_Deref(self, node): return f"*{self.format(node.ptr)}"
    
    def visit_SizeOf(self, node):
        if isinstance(node.target, Type):
            return f"sizeof({self._format_type(node.target)})"
        return f"sizeof({self.format(node.target)})"
        
    def visit_TypeCast(self, node):
        return f"({self._format_type(node.target_type)}) {self.format(node.expr)}"

    def visit_ArrayAccess(self, node):
        return f"{self.format(node.array)}[{self.format(node.index)}]"

    def visit_FieldAccess(self, node):
        return f"{self.format(node.base)}.{node.field}"

    def visit_ArrowAccess(self, node):
        return f"{self.format(node.base)}->{node.field}"

    def visit_Call(self, node):
        args = ", ".join([self.format(arg) for arg in node.args])
        return f"{self.format(node.callee)}({args})"

    def visit_Var(self, node):
        return str(node.name)
    
    def visit_Const(self, node):
        if getattr(node, 'literal_type', 'int') == 'char':
            val = str(node.value)
            # Remove aspas simples se o Lexer já as tiver incluído
            if val.startswith("'") and val.endswith("'"):
                val = val[1:-1]
            return f"'{val}'"
        return str(node.value)

    def visit_StringLiteral(self, node):
        val = str(node.value)
        # Remove aspas duplas se o Lexer já as tiver incluído
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        
        # Converte quebras de linha reais (na memória) de volta para símbolos de escape (\n)
        val = val.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f'"{val}"'

    def visit_VarDecl(self, node):
        names_str = []
        for name, init in node.names:
            decl_str = self._format_type(node.vartype, name)
            
            if init is not None:
                if isinstance(init, list):
                    # Se for uma lista de tamanho 1, temos de decidir se leva chaves ou não
                    if len(init) == 1:
                        val_fmt = self.format(init[0])
                        is_string = val_fmt.startswith('"') and val_fmt.endswith('"')
                        is_array_or_struct = getattr(node.vartype, '__class__', '').__name__ in ('ArrayType', 'StructType')
                        
                        # Não usa chaves para strings nem para tipos primitivos/ponteiros
                        if is_string or not is_array_or_struct:
                            names_str.append(f"{decl_str} = {val_fmt}")
                        else:
                            names_str.append(f"{decl_str} = {{{val_fmt}}}")
                    else:
                        init_vals = ", ".join([self.format(v) for v in init])
                        names_str.append(f"{decl_str} = {{{init_vals}}}")
                else:
                    names_str.append(f"{decl_str} = {self.format(init)}")
            else:
                names_str.append(decl_str)
        
        return f"{self._get_indent()}{', '.join(names_str)};"

    def visit_ArrayDecl(self, node):
        decl = self._format_type(node.arrtype, node.name)
        if getattr(node, 'init', None) is not None:
            if isinstance(node.init, list):
                if len(node.init) == 1:
                    val_fmt = self.format(node.init[0])
                    # Se inicializou array com uma string, não precisa de chaves
                    if val_fmt.startswith('"') and val_fmt.endswith('"'):
                        return f"{self._get_indent()}{decl} = {val_fmt};"
                    return f"{self._get_indent()}{decl} = {{{val_fmt}}};"
                
                init_vals = ", ".join([self.format(v) for v in node.init])
                return f"{self._get_indent()}{decl} = {{{init_vals}}};"
            else:
                return f"{self._get_indent()}{decl} = {self.format(node.init)};"
        return f"{self._get_indent()}{decl};"
