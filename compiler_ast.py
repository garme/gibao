# ============================
#       TIPOS DE DADOS
# ============================

class Type:
    def is_int(self): return False
    def is_char(self): return False
    def is_pointer(self): return False
    def is_array(self): return False
    def __repr__(self): return self.__class__.__name__


class IntType(Type):
    def is_int(self): return True
    def __repr__(self): return "int"


class CharType(Type):
    def is_char(self): return True
    def __repr__(self): return "char"


class StringLiteral:
    def __init__(self, value, lineno=None):
        self.value = value
        self.vartype = PointerType(CharType())
        self.lineno = lineno

    def typeof(self):
        return self.vartype
    
    def __repr__(self):
        return f'StringLiteral("{self.value}")'


class PointerType(Type):
    def __init__(self, base):
        self.base = base
    def is_pointer(self): return True
    def __repr__(self): return f"{self.base}*"


class ArrayType(Type):
    def __init__(self, base, size):
        self.base = base
        self.size = size
    def is_array(self): return True
    def __repr__(self): return f"{self.base}[{self.size}]"


# ============================
#       NÓS DA AST
# ============================

class Program:
    def __init__(self, items, lineno=None):
        self.items = items
        self.lineno = lineno
    
    def __repr__(self):
        return f"Program(items={self.items})"


class VarDecl:
    def __init__(self, vartype, names, lineno=None):
        self.vartype = vartype
        self.names = names
        self.lineno = lineno
    
    def __repr__(self):
        return f"VarDecl(type={self.vartype}, names={self.names})"


class Assignment:
    def __init__(self, target, value, lineno=None):
        self.target = target
        self.value = value
        self.lineno = lineno
    
    def __repr__(self):
        return f"Assignment(target={self.target}, value={self.value})"


class Return:
    def __init__(self, value, lineno=None):
        self.value = value
        self.lineno = lineno
    
    def __repr__(self):
        return f"Return(value={self.value})"


class BinaryOp:
    def __init__(self, op, left, right, lineno=None):
        self.op = op
        self.left = left
        self.right = right
        self.lineno = lineno
    
    def __repr__(self):
        return f"BinaryOp(op='{self.op}', left={self.left}, right={self.right})"


class Var:
    def __init__(self, name, lineno=None):
        self.name = name
        self.vartype = None
        self.lineno = lineno
    
    def __repr__(self):
        return f"Var(name='{self.name}')"


class Const:
    def __init__(self, value, literal_type="int", lineno=None):
        self.literal_type = literal_type
        self.value = value
        self.lineno = lineno

    def typeof(self):
        return CharType() if self.literal_type == "char" else IntType()
    
    def __repr__(self):
        return f"Const(value={self.value}, type='{self.literal_type}')"


class If:
    def __init__(self, condition, then_body, else_body=None, lineno=None):
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body
        self.lineno = lineno
    
    def __repr__(self):
        return f"If(cond={self.condition}, then={self.then_body}, else={self.else_body})"


class While:
    def __init__(self, condition, body, lineno=None):
        self.condition = condition
        self.body = body
        self.lineno = lineno
    
    def __repr__(self):
        return f"While(cond={self.condition}, body={self.body})"


class For:
    def __init__(self, init, condition, increment, body, lineno=None):
        self.init = init
        self.condition = condition
        self.increment = increment
        self.body = body
        self.lineno = lineno
    
    def __repr__(self):
        return f"For(init={self.init}, cond={self.condition}, incr={self.increment}, body={self.body})"


class Param:
    def __init__(self, name, vartype, lineno=None):
        self.name = name
        self.vartype = vartype
        self.lineno = lineno
    
    def __repr__(self):
        return f"Param(name='{self.name}', type={self.vartype})"


class Function:
    def __init__(self, rettype, name, params, body, is_naked=False, lineno=None):
        self.rettype = rettype
        self.name = name
        self.params = params
        self.body = body
        self.is_naked = is_naked
        self.lineno = lineno
        
    
    def __repr__(self):
        return f"Function(name='{self.name}', naked={self.is_naked}, ret={self.rettype}, params={self.params}, body={self.body})"


class Call:
    # Mudamos 'name' para 'callee' (quem está sendo chamado)
    def __init__(self, callee, args, lineno=None):
        self.callee = callee  # Agora é um nó da AST (Var, Deref, etc), não string
        self.args = args
        self.lineno = lineno
    
    def __repr__(self):
        return f"Call(callee={self.callee}, args={self.args})"


class AddressOf:
    def __init__(self, var, lineno=None):
        self.var = var
        self.vartype = None
        self.lineno = lineno
    
    def __repr__(self):
        return f"AddressOf(var={self.var})"


class Deref:
    def __init__(self, ptr, lineno=None):
        self.ptr = ptr
        self.vartype = None
        self.lineno = lineno
    
    def __repr__(self):
        return f"Deref(ptr={self.ptr})"


class UnaryOp:
    def __init__(self, op, expr, lineno=None):
        self.op = op
        self.expr = expr
        self.lineno = lineno
    
    def __repr__(self):
        return f"UnaryOp(op='{self.op}', expr={self.expr})"


class Stmt:
    pass


class Break(Stmt):
    def __init__(self, lineno=None):
        self.lineno = lineno
    
    def __repr__(self):
        return "Break()"


class Continue(Stmt):
    def __init__(self, lineno=None):
        self.lineno = lineno
    
    def __repr__(self):
        return "Continue()"


class ArrayDecl:
    def __init__(self, name, arrtype, init=None, lineno=None):
        self.name = name
        self.arrtype = arrtype
        self.init = init or []
        self.lineno = lineno
    
    def __repr__(self):
        return f"ArrayDecl(name='{self.name}', type={self.arrtype}, init={self.init})"


class ArrayAccess:
    def __init__(self, array, index, lineno=None):
        self.array = array
        self.index = index
        self.vartype = None
        self.lineno = lineno
    
    def __repr__(self):
        return f"ArrayAccess(arr={self.array}, idx={self.index})"


class LibraryImport:
    def __init__(self, name, lineno=None):
        self.name = name
        self.lineno = lineno
    
    def __repr__(self):
        return f"Import({self.name})"

#Structs

class StructType(Type):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"struct {self.name}"


class StructDecl:
    def __init__(self, name, fields, lineno=None):
        self.name = name
        self.fields = fields  # lista de (name, type, line)
        self.lineno = lineno
    
    def __repr__(self):
        return f"StructDecl(name='{self.name}', fields={self.fields})"

class FieldAccess:
    def __init__(self, base, field, lineno=None):
        self.base = base      # expressão
        self.field = field   # string
        self.vartype = None
        self.lineno = lineno
    
    def __repr__(self):
        return f"FieldAccess(base={self.base}, field='{self.field}')"

class ArrowAccess:
    def __init__(self, base, field, lineno=None):
        self.base = base
        self.field = field
        self.vartype = None
        self.lineno = lineno
    
    def __repr__(self):
        return f"ArrowAccess(base={self.base}, field='{self.field}')"

class SizeOf:
    def __init__(self, target, lineno=None):
        self.target = target  # Pode ser um Type() ou uma Expr()
        self.vartype = IntType() # sizeof sempre resulta em int
        self.lineno = lineno

    def __repr__(self):
        return f"SizeOf(target={self.target})"

class Asm(Stmt):
    def __init__(self, code, lineno=None):
        self.code = code  # String contendo o código assembly cru
        self.lineno = lineno
    
    def __repr__(self):
        return f'Asm(code="{self.code.strip()}")'


class TypeCast:
    def __init__(self, target_type, expr, lineno=None):
        self.target_type = target_type
        self.expr = expr
        self.vartype = target_type # O tipo resultante é o alvo do cast
        self.lineno = lineno
    
    def __repr__(self):
        return f"Cast({self.target_type}, {self.expr})"

class PreInc:
    def __init__(self, target, lineno=None):
        self.target = target
        self.vartype = None
        self.lineno = lineno
    def __repr__(self): return f"PreInc({self.target})"

class PreDec:
    def __init__(self, target, lineno=None):
        self.target = target
        self.vartype = None
        self.lineno = lineno
    def __repr__(self): return f"PreDec({self.target})"

class PostInc:
    def __init__(self, target, lineno=None):
        self.target = target
        self.vartype = None
        self.lineno = lineno
    def __repr__(self): return f"PostInc({self.target})"

class PostDec:
    def __init__(self, target, lineno=None):
        self.target = target
        self.vartype = None
        self.lineno = lineno
    def __repr__(self): return f"PostDec({self.target})"

class Case:
    def __init__(self, value, body, lineno=None):
        self.value = value  # Expressão do case (ex: Const(1)). Se for None, é o 'default'
        self.body = body    # Lista de comandos a serem executados
        self.lineno = lineno

class Switch:
    def __init__(self, expr, cases, lineno=None):
        self.expr = expr    # A variável ou expressão sendo testada: switch(expr)
        self.cases = cases  # Lista de objetos 'Case'
        self.lineno = lineno
