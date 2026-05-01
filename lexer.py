import re

# Tokens básicos (palavras-chave, identificadores, operadores, etc.)
TOKEN_SPEC = [
    ('COMMENT', r'//[^\n]*'),
    ('PREPROC', r'#(define|pragma|ifndef|endif|ifdef)[^\n]*'), 
    ('INCLUDE', r'#include'),
    ('TYPEDEF', r'typedef\b'),
    ('SIZEOF', r'sizeof\b'),
    ('ASM',     r'asm\b'),
    ('NAKED',   r'naked\b'),

    ('STRUCT',  r'struct\b'),
    ('INT',     r'int\b'),
    ('CHAR',    r'char\b'),
    ('VOID',    r'void\b'),

    ('IF',      r'if\b'),
    ('ELSE',    r'else\b'),
    ('WHILE',   r'while\b'),
    ('FOR',     r'for\b'),
    ('RETURN',  r'return\b'),
    ('SWITCH',  r'switch\b'),
    ('CASE',    r'case\b'),
    ('DEFAULT', r'default\b'),

    ('STRING_LITERAL', r'"([^"\\]|\\.)*"'),
    ('CHAR_LITERAL',   r"'([^'\\]|\\.)'"),
    
    ('COLON',   r':'),
    ('LAND',    r'&&'),
    ('LOR',     r'\|\|'),
    
    ('LSHIFT',  r'<<'),
    ('RSHIFT',  r'>>'),
    ('PIPE',    r'\|'),
    ('TILDE',   r'~'),
    ('CARET',   r'\^'),
    
    ('EQ',      r'=='),
    ('NE',      r'!='),
    ('LNOT',    r'!'),
    ('LE',      r'<='),
    ('GE',      r'>='),

    ('ARROW',   r'->'),
    ('ASSIGN',  r'='),
    ('LT',      r'<'),
    ('GT',      r'>'),

    ('INC',     r'\+\+'),
    ('DEC',     r'--'),
    ('PLUS_ASSIGN', r'\+='),
    ('MINUS_ASSIGN', r'-='),

    ('PLUS',    r'\+'),
    ('MINUS',   r'-'),
    ('TIMES',   r'\*'),
    ('DIV',     r'/'),
    ('AMP',     r'&'),
    ('DOT',     r'\.'),

    ('ID',      r'[a-zA-Z_]\w*'),
    ('NUM',     r'\d+'),

    ('SEMI',    r';'),
    ('LPAREN',  r'\('),
    ('RPAREN',  r'\)'),
    ('LBRACE',  r'\{'),
    ('RBRACE',  r'\}'),
    ('LBRACKET', r'\['),
    ('RBRACKET', r'\]'),
    ('COMMA',   r','),

    ('WS',      r'\s+'),
]

# Função de análise léxica
def tokenize(code):
    pattern = '|'.join(f'(?P<{name}>{regex})' for name, regex in TOKEN_SPEC)
    regex = re.compile(pattern)

    pos = 0
    line = 1
    line_start = 0
    in_include = False

    while pos < len(code):
        match = regex.match(code, pos)

        # 🚨 ERRO LÉXICO: nada casou aqui
        if not match:
            char = code[pos]
            raise SyntaxError(f"Erro Léxico na linha {line}: caractere inválido '{char}'")
        
        kind = match.lastgroup
        value = match.group()
        start = match.start()

        # Atualiza linhas
        newlines = code[line_start:start].count('\n')
        line += newlines
        if newlines > 0:
            line_start = code.rfind('\n', 0, start) + 1

        # --- NOVO: Cálculo exato da coluna ---
        column = start - line_start

        # #include
        if kind == 'INCLUDE':
            in_include = True
            yield ('INCLUDE', value, line, column) # Injetando column
            pos = match.end()
            continue

        # contextual <...>
        if in_include:
            if kind == 'LT':
                kind = 'LANGLE'
            elif kind == 'GT':
                kind = 'RANGLE'
                in_include = False
        
        # --- ATUALIZADO: O lexer agora ignora as macros soltas ---
        if kind not in ('WS', 'COMMENT', 'PREPROC'):
            yield (kind, value, line, column)

        pos = match.end()
