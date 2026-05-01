import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, Toplevel
import re
import os
import time
import webbrowser
import json

# Importações do seu compilador GIBÃO
try:
    from preprocess import Preprocessor
    from lexer import tokenize
    from parser import Parser, SyntacticError
    from semantic import Semantic, SemanticError
    from codegen import CodeGen, CodeGenError
    from optimizer import optimize_with_log
    from formatter import ASTFormatter
except ImportError as e:
    print(f"Erro ao importar módulos do compilador: {e}")
    pass

# =============================================================================
# IMAGEM DO COMPSIM (BASE64)
# =============================================================================
cs_image ="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"

def format_ast(node, indent="", is_last=True, field_name=None):
    """Gera uma visualização em árvore (ASCII Art) da AST do compilador."""
    if node is None: return ""
    
    prefix = f"{indent}{'└── ' if is_last else '├── '}"
    
    if isinstance(node, (int, str, float, bool, tuple)):
        return f"{prefix}{field_name + ': ' if field_name else ''}{node}\n"
        
    if hasattr(node, '__dict__'):
        node_name = node.__class__.__name__
        
        if node_name == 'Var':
            return f"{prefix}{field_name + ': ' if field_name else ''}Var({getattr(node, 'name', '')})\n"
        if node_name == 'Const':
            return f"{prefix}{field_name + ': ' if field_name else ''}Const({getattr(node, 'value', '')})\n"
        if 'Type' in node_name:
            return f"{prefix}{field_name + ': ' if field_name else ''}{node}\n"
            
        desc = f"{field_name}: {node_name}" if field_name else node_name
        
        if node_name == 'BinaryOp': desc += f" '{getattr(node, 'op', '')}'"
        if node_name == 'Function': desc += f" {getattr(node, 'name', '')}()"
        if node_name == 'Import': desc += f" {getattr(node, 'name', '')}"
            
        # --- FIX: Injeta o número da linha visualmente na AST ---
        lineno = getattr(node, 'lineno', None)
        if lineno:
            desc += f" [Ln: {lineno}]"
            
        res = f"{prefix}{desc}\n"
        
        children = [(k, v) for k, v in vars(node).items() 
                    if k not in ('lineno', 'op', 'name') and not k.startswith('_') and v is not None and v != []]
        
        next_indent = indent + ("    " if is_last else "│   ")
        for i, (k, v) in enumerate(children):
            child_last = (i == len(children) - 1)
            
            if isinstance(v, list):
                res += f"{next_indent}{'└── ' if child_last else '├── '}{k}\n"
                sub_indent = next_indent + ("    " if child_last else "│   ")
                for j, item in enumerate(v):
                    item_last = (j == len(v) - 1)
                    res += format_ast(item, sub_indent, item_last)
            else:
                res += format_ast(v, next_indent, child_last, k)
                
        return res
        
    return f"{prefix}{node}\n"

# =============================================================================
# DEFINIÇÃO DOS SNIPPETS E TOOLTIPS 
# =============================================================================
# =============================================================================
# DEFINIÇÃO DOS SNIPPETS E TOOLTIPS 
# =============================================================================
CODE_SNIPPETS = {
    "Estruturas Básicas": {
        "Main Function": "int main() {\n    $0\n    return 0;\n}",
        "Include (Básico)": "#include <${1:lib}>$0",
        "Include (Local)": "#include \"${1:arquivo.c}\"$0",
        "Use Lib": "use ${1:io};$0",
        "Define": "#define ${1:MAX} 100$0",
    },
    "Controle de Fluxo": {
        "If": "if (${1:expr}) {\n    $0\n}",
        "If / Else": "if (${1:expr}) {\n    $0\n} else {\n    \n}",
        "While": "while (${1:expr}) {\n    $0\n}",
        "For Loop": "for (${1:i} = 0; ${1:i} < 10; ${1:i}++) {\n    $0\n}",
        "Switch": "switch (${1:expr}) {\n    case ${2:1}:\n        $0\n        break;\n    default:\n        break;\n}",
        "Case": "case ${1:1}:\n    $0\n    break;"
    },
    "Tipos e Structs": {
        "Struct Def": "struct ${1:Nome} {\n    $0\n};",
        "Typedef": "typedef int ${1:Inteiro};$0",
        "Typedef Struct": "typedef struct {\n    int ${1:x};\n    int ${2:y};\n} ${3:Nome};$0"
    },
    "Variáveis e Arrays": {
        "Var (int)": "int ${1:count};$0",
        "Var (char)": "char ${1:letter};$0",
        "Ponteiro (int)": "int *${1:ptr};$0",
        "Ponteiro (char)": "char *${1:str};$0",
        "Array (int)": "int ${1:lista}[${2:10}];$0",
        "Array (char) / String": "char ${1:buffer}[${2:256}];$0",
    },
    "Funções": {
        "Função Void": "void ${1:procedure}() {\n    $0\n}",
        "Função Int": "int ${1:soma}(int a, int b) {\n    $0\n    return a + b;\n}",
    },
    "Avançado / Baixo Nível": {
        "Inline Assembly": "asm(\"${1:MOV 0}\");$0",
        "Interrupt (ASM)": "asm(\"INT ${1:TIMER_INT}\");$0",
        "Função Naked (ISR)": "naked void ${1:isr_handler}() {\n    $0\n    asm(\"INT IRET_INT\");\n}",
        "Manipulação de Pilha (POP)": "asm(\"SOP pop\"); asm(\"STA ${1:tmp_val}\");$0",
        "Manipulação de Pilha (PUSH)": "LDA ${1:tmp_val}; asm(\"SOP push\");$0",
    }
}

TOOLTIPS_DB = {
    "abs":      "int abs(int val)\nCalcula o valor absoluto de um número inteiro.",
    "mul":      "int mul(int a, int b)\nCalcula a multiplicação inteira ente os números a e b.",
    "div":      "int div(int a, int b)\nCalcula a divisão inteira dos números a por b.",
    "max":      "int max(int a, int b)\nRetorna o maior número inteiro entre a e b.",
    "min":      "int min(int a, int b)\nRetorna o menor número inteiro entre a e b.",
    "mod":      "int mod(int a, int b)\nRetorna o resto da divisão inteira entre a e b.",
    "pow":      "int pow(int a, int b)\nRetorna a potência dos numérios inteiros a por b.",
    "main":     "int main()\nPonto de entrada principal do programa C.",
    "include": "Diretiva do Pré-processador\nImporta definições de funções, macros e estruturas de dados.",
    "define":  "Diretiva do Pré-processador\nDefine macro ou constante simbólicas.",
    "struct":   "Palavra-chave\nDefine uma nova estrutura de dados customizada.",
    "typedef":  "Palavra-chave\nDefine um novo tipo de dados customizado.",
    "int":      "Tipo Primitivo\nInteiro numérico de 16-bits da arquitetura CARIRI.",
    "char":     "Tipo Primitivo\nCaractere simples ou base para Strings (char*).",
    "void":     "Tipo Vazio\nIndica que a função não retorna valores.",
    "naked":    "Modificador (Assembly)\nImpede a geração do prólogo/epílogo padrão da função.",
    "asm":      "void asm()\nPermite injetar código assembly puro no código C."
}

# =============================================================================
# WIDGET CUSTOMIZADO: CODE EDITOR
# =============================================================================
class CodeEditor(ttk.Frame):
    def __init__(self, parent, show_line_numbers=True, language="c", width=40, height=12, 
                 on_change_callback=None, on_cursor_callback=None, on_linter_callback=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.show_line_numbers = show_line_numbers
        self.language = language 
        self.on_change_callback = on_change_callback 
        self.on_cursor_callback = on_cursor_callback
        self.on_linter_callback = on_linter_callback # <--- NOVO: Conector do Linter
        
        self.filename = None
        self.workspace_dir = None
        
        self.font_family = "Consolas"
        self.font_size = 11
        
        self.folded_blocks = set() 
        
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._on_scroll)
        self.text_area = tk.Text(self, wrap="none", undo=True, autoseparators=False, width=width, height=height,
                                 font=(self.font_family, self.font_size),
                                 yscrollcommand=self._on_text_scroll, bd=0, padx=5, pady=5)
        
        self.line_numbers = tk.Text(self, width=12, padx=4, takefocus=0, bd=0,
                                    font=(self.font_family, self.font_size),
                                    state='disabled', pady=5, wrap="none")

        self.scrollbar.pack(side="right", fill="y")
        if self.show_line_numbers:
            self.line_numbers.pack(side="left", fill="y")
        self.text_area.pack(side="left", fill="both", expand=True)

        self.text_area.tag_configure("folded", elide=True)
        self.text_area.tag_configure("bookmark_data")
        
        self.apply_theme(dark=True) 

        self.tooltip_window = None
        self.linter_after_id = None 

        self.text_area.bind("<<Modified>>", self._on_modified)
        self.text_area.bind("<<Change>>", self._on_content_changed)
        self.text_area.bind("<Configure>", self._on_content_changed)
        self.text_area.bind("<KeyRelease>", self._on_key_release)
        self.text_area.bind("<ButtonRelease-1>", self._on_click_release)
        self.text_area.bind("<Button-1>", self._on_click)
        self.text_area.bind("<Return>", self._auto_indent)
        
        self.text_area.bind("<Control-a>", self._select_all)
        self.text_area.bind("<Control-A>", self._select_all)
        self.text_area.bind("<<Selection>>", self._highlight_occurrences)
        self.text_area.bind("<Control-Button-1>", self._go_to_definition)
        
        self.text_area.bind("<Control-b>", self.toggle_bookmark)
        self.text_area.bind("<Control-B>", self.toggle_bookmark)
        
        self.text_area.bind("<KeyPress>", self._handle_keypress)
        self.text_area.bind("<Motion>", self._on_hover)
        self.text_area.bind("<Leave>", self._hide_tooltip)
        
        self.text_area.bind("<Control-slash>", self.toggle_comment)
        # --- NOVO: Atalhos do Refactor Rename ---
        self.text_area.bind("<Control-r>", self.refactor_rename)
        self.text_area.bind("<Control-R>", self.refactor_rename)
        self.line_numbers.bind("<Button-1>", self._on_line_number_click)

        # Eventos granulares de Undo / Redo
        self.text_area.bind("<Control-z>", self._perform_undo)
        self.text_area.bind("<Control-Z>", self._perform_redo) 
        self.text_area.bind("<Control-y>", self._perform_redo)
        self.text_area.bind("<Control-Y>", self._perform_redo)
        
        # --- FIX DO TKINTER: Sequestrar o Shift-Up antes do evento nativo ---
        self.text_area.bind('<Shift-Alt-Up>', self.expand_selection)
        self.text_area.bind('<Shift-Alt-Down>', self.shrink_selection)
        
        self.text_area.bind("<Button-1>", self._clear_sel_history, add="+")
        self.text_area.bind("<KeyPress>", self._clear_sel_history, add="+")
        
        self.snippet_marks = None
        self.text_area.bind("<Tab>", self._handle_tab)

        for w in (self.text_area, self.line_numbers):
            w.bind("<MouseWheel>", self._on_mousewheel)
            w.bind("<Button-4>", self._on_mousewheel) 
            w.bind("<Button-5>", self._on_mousewheel) 
            
            w.bind("<Control-MouseWheel>", self._on_mouse_zoom)
            w.bind("<Control-Button-4>", self._on_mouse_zoom) 
            w.bind("<Control-Button-5>", self._on_mouse_zoom) 

    def _perform_undo(self, event=None):
        try:
            self.text_area.edit_undo()
            self._on_content_changed()
        except tk.TclError:
            pass
        return "break"

    def _perform_redo(self, event=None):
        try:
            self.text_area.edit_redo()
            self._on_content_changed()
        except tk.TclError:
            pass
        return "break"

    def _handle_keypress(self, event):
        # 1. FIX: Sobrescreve o texto selecionado se o usuário digitar uma letra/número novo
        if event.char and event.char.isprintable():
            try:
                if self.text_area.tag_ranges("sel"):
                    self.text_area.delete("sel.first", "sel.last")
            except tk.TclError:
                pass

        # 2. Comportamento original
        if event.char in [' ', '\r', '\n', '\t', '.', ',', ';', ':', '(', ')', '{', '}', '[', ']']:
            self.text_area.edit_separator()

        char = event.char
        pairs = {'(': ')', '{': '}', '[': ']', '"': '"', "'": "'"}
        if char in pairs:
            self.text_area.insert("insert", char + pairs[char])
            self.text_area.mark_set("insert", "insert-1c")
            return "break"
            
    def _on_mousewheel(self, event):
        if event.num == 4:
            steps = -3  
        elif event.num == 5:
            steps = 3   
        elif event.delta:
            if event.delta % 120 == 0:
                steps = int(-1 * (event.delta / 120) * 3) 
            else:
                steps = -1 if event.delta > 0 else 1      
        else:
            return "break"
            
        self.text_area.yview_scroll(steps, "units")
        self._sync_lines_view()
        self._hide_tooltip()
        return "break" 
        
    def _on_mouse_zoom(self, event):
        if event.num == 4 or event.delta > 0:
            self.zoom_in()
        elif event.num == 5 or event.delta < 0:
            self.zoom_out()
        return "break"

    def _on_text_scroll(self, *args):
        self.scrollbar.set(*args)
        self._sync_lines_view()

    def _on_scroll(self, *args):
        self.text_area.yview(*args)
        self._sync_lines_view()
        self._hide_tooltip()

    def _sync_lines_view(self):
        yview = self.text_area.yview()
        self.line_numbers.yview_moveto(yview[0])

    @property
    def bookmarks(self):
        ranges = self.text_area.tag_ranges("bookmark_data")
        return {int(str(r).split('.')[0]) for r in ranges[::2]}

    def toggle_bookmark(self, event=None):
        self.text_area.focus_set()
        line = int(self.text_area.index("insert").split('.')[0])
        
        if line in self.bookmarks:
            self.text_area.tag_remove("bookmark_data", f"{line}.0", f"{line}.end")
        else:
            self.text_area.tag_add("bookmark_data", f"{line}.0", f"{line}.end")
            
        self.update_line_numbers()
        return "break"

    def goto_next_bookmark(self, event=None):
        self.text_area.focus_set()
        bms = self.bookmarks
        if not bms: return "break"
        
        curr_line = int(self.text_area.index("insert").split('.')[0])
        next_lines = sorted([b for b in bms if b > curr_line])
        
        target = next_lines[0] if next_lines else sorted(list(bms))[0] 
        self.text_area.mark_set("insert", f"{target}.0")
        self.text_area.see(f"{target}.0")
        self._highlight_current_line()
        self._update_cursor_status()
        return "break"

    def _get_fold_blocks(self):
        text = self.text_area.get("1.0", "end-1c")
        lines = text.split('\n')
        blocks = {}
        stack = []
        for i, line in enumerate(lines):
            for char in line:
                if char == '{':
                    stack.append(i + 1)
                elif char == '}':
                    if stack:
                        start = stack.pop()
                        if start != i + 1: 
                            blocks[start] = i + 1
        return blocks

    def _sync_folds_from_tags(self):
        ranges = self.text_area.tag_ranges("folded")
        self.folded_blocks = {int(str(r).split('.')[0]) for r in ranges[::2]}

    def _apply_folds(self):
        self.text_area.tag_remove("folded", "1.0", "end")
        blocks = self._get_fold_blocks()
        
        self.folded_blocks = {b for b in self.folded_blocks if b in blocks}

        for start_line in self.folded_blocks:
            end_line = blocks[start_line]
            self.text_area.tag_add("folded", f"{start_line}.end", f"{end_line}.0")
            
        self.update_line_numbers()

    def _on_line_number_click(self, event):
        idx = self.line_numbers.index(f"@{event.x},{event.y}")
        line_in_gutter = idx.split('.')[0]
        text_at_line = self.line_numbers.get(f"{line_in_gutter}.0", f"{line_in_gutter}.end")
        
        match = re.search(r'(\d+)$', text_at_line)
        if match:
            actual_line = int(match.group(1))
            blocks = self._get_fold_blocks()
            
            if actual_line in blocks:
                if actual_line in self.folded_blocks:
                    self.folded_blocks.remove(actual_line)
                else:
                    self.folded_blocks.add(actual_line)
                self._apply_folds()
        return "break"

    def _select_all(self, event=None):
        self.text_area.tag_add("sel", "1.0", "end")
        return "break"

    def _on_modified(self, event=None):
        if self.text_area.edit_modified():
            if self.on_change_callback:
                self.on_change_callback(True)

    def reset_modified(self):
        self.text_area.edit_modified(False)
        if self.on_change_callback:
            self.on_change_callback(False)

    def is_modified(self):
        return self.text_area.edit_modified()
                
    def _apply_zoom(self):
        base_font = (self.font_family, self.font_size)
        self.text_area.configure(font=base_font)
        self.line_numbers.configure(font=base_font)
        
        bold_font = (self.font_family, self.font_size, "bold")
        self.text_area.tag_config("kw_type", font=bold_font)
        self.text_area.tag_config("kw_flow", font=bold_font)
        self.text_area.tag_config("asm_op", font=bold_font)
        self.line_numbers.tag_config("bookmark_line", font=bold_font)
        
        self.update_line_numbers()

    def zoom_in(self, event=None):
        self.font_size += 1
        self._apply_zoom()
        return "break"

    def zoom_out(self, event=None):
        self.font_size = max(6, self.font_size - 1)
        self._apply_zoom()
        return "break"

    def apply_theme(self, dark=False):
        self.is_dark = dark
        if dark:
            self.colors = {
                "bg": "#1e1e1e", "fg": "#d4d4d4",
                "ln_bg": "#252526", "ln_fg": "#858585",
                "select_bg": "#264f78", "insert": "#ffffff",
                "kw_type": "#569cd6", "kw_flow": "#c586c0",
                "asm_op": "#4ec9b0", "string": "#ce9178",
                "comment": "#6a9955", "number": "#b5cea8",
                "bracket_hl": "#5a5a5a", "error_hl": "#4a1e1e",
                "curr_line": "#2a2d2e",
                "linter_err": "#ff3333",
                "word_hl": "#464646",
                "bookmark": "#ffcc00",
                "linter_warn": "#cca700", 
                "warn_hl": "#332b00",
                "hl_function": "#dcdcaa",  # Amarelo VS Code
                "hl_global": "#f07178",    # Coral/Vermelho claro
                "hl_struct": "#4ec9b0",    # Verde-água
                "hl_builtin": "#569cd6"    # Azul claro
            }
        else:
            self.colors = {
                "bg": "#ffffff", "fg": "#000000",
                "ln_bg": "#f0f0f0", "ln_fg": "#888888",
                "select_bg": "#add6ff", "insert": "#000000",
                "kw_type": "#0000ff", "kw_flow": "#800080",
                "asm_op": "#008000", "string": "#a31515",
                "comment": "#008000", "number": "#098658",
                "bracket_hl": "#ffcc00", "error_hl": "#ffcccc",
                "curr_line": "#e8f2ff",
                "linter_err": "#cc0000",
                "word_hl": "#d3d3d3",
                "bookmark": "#ff8800",
                "linter_warn": "#e69500", 
                "warn_hl": "#fffbe6",
                "hl_function": "#795e26",  # Amarelo escuro
                "hl_global": "#b31d28",    # Vermelho escuro
                "hl_struct": "#267f99",    # Verde escuro
                "hl_builtin": "#0000ff"    # Azul
            }
        
        self.text_area.config(bg=self.colors["bg"], fg=self.colors["fg"], 
                              insertbackground=self.colors["insert"], 
                              selectbackground=self.colors["select_bg"])
        self.line_numbers.config(bg=self.colors["ln_bg"], fg=self.colors["ln_fg"])
        
        font_bold = (self.font_family, self.font_size, "bold")
        self.text_area.tag_config("kw_type", foreground=self.colors["kw_type"], font=font_bold)
        self.text_area.tag_config("kw_flow", foreground=self.colors["kw_flow"], font=font_bold)
        self.text_area.tag_config("asm_op", foreground=self.colors["asm_op"], font=font_bold)
        self.text_area.tag_config("string", foreground=self.colors["string"])
        self.text_area.tag_config("comment", foreground=self.colors["comment"])
        self.text_area.tag_config("number", foreground=self.colors["number"])
        self.text_area.tag_config("bracket_match", background=self.colors["bracket_hl"])
        self.text_area.tag_config("current_line", background=self.colors["curr_line"])
        self.text_area.tag_config("word_highlight", background=self.colors["word_hl"])
        
        self.text_area.tag_config("linter_error", foreground=self.colors["linter_err"], underline=True)
        self.text_area.tag_config("error_line", background=self.colors["error_hl"], underline=True)
        self.text_area.tag_config("linter_warning", foreground=self.colors["linter_warn"], underline=True)
        self.text_area.tag_config("warning_line", background=self.colors["warn_hl"])
        
        self.line_numbers.tag_config("bookmark_line", foreground=self.colors["bookmark"], font=font_bold)
        
        self.text_area.tag_config("hl_function", foreground=self.colors["hl_function"])
        self.text_area.tag_config("hl_global", foreground=self.colors["hl_global"], font=(self.font_family, self.font_size, "italic")) # Globais ficam em itálico!
        self.text_area.tag_config("hl_struct", foreground=self.colors["hl_struct"])
        self.text_area.tag_config("hl_builtin", foreground=self.colors["hl_builtin"])
        
        # Cor de destaque para o Source Mapping (Live Disassembly)
        self.text_area.tag_config("mapped_highlight", background="#2b455b" if dark else "#cce8ff")
        
        self.text_area.tag_config("snippet_hl", background="#335243" if dark else "#dcedd5", borderwidth=1, relief="solid")

        self.text_area.tag_config("sel", background=self.colors["select_bg"], foreground=self.colors["fg"])
        self.text_area.tag_raise("sel")
        
        self.highlight_syntax()
        self._highlight_current_line()

    def highlight_mapped_lines(self, lines):
        """Destaca múltiplas linhas no editor e rola a tela para a primeira."""
        self.text_area.tag_remove("mapped_highlight", "1.0", "end")
        if not lines: return
        
        for ln in lines:
            self.text_area.tag_add("mapped_highlight", f"{ln}.0", f"{ln}.end")
            
        # Rola a tela suavemente para a primeira linha gerada
        self.text_area.see(f"{lines[0]}.0")
        
    def _highlight_occurrences(self, event=None):
        self.text_area.tag_remove("word_highlight", "1.0", "end")
        try:
            sel_start = self.text_area.index("sel.first")
            sel_end = self.text_area.index("sel.last")
            word = self.text_area.get(sel_start, sel_end).strip() 
            
            if not re.match(r'^[A-Za-z_]\w*$', word): 
                return
            
            idx = "1.0"
            while True:
                idx = self.text_area.search(word, idx, stopindex="end", exact=True)
                if not idx: break
                
                end_idx = f"{idx}+{len(word)}c"
                char_before = self.text_area.get(f"{idx}-1c") if self.text_area.index(idx) != "1.0" else " "
                char_after = self.text_area.get(end_idx)
                
                if not (char_before.isalnum() or char_before == '_') and not (char_after.isalnum() or char_after == '_'):
                    self.text_area.tag_add("word_highlight", idx, end_idx)
                    
                idx = end_idx
        except tk.TclError:
            pass

    def _go_to_definition(self, event=None):
        if self.language != 'c': return "break"
        
        # Pega a posição do clique ou do cursor do teclado
        if event and getattr(event, 'num', None) == 1:
            idx = self.text_area.index(f"@{event.x},{event.y}")
        else:
            idx = self.text_area.index("insert")
            
        line, col = map(int, idx.split('.'))
        line_text = self.text_area.get(f"{line}.0", f"{line}.end")
        
        word_start = col
        while word_start > 0 and (line_text[word_start-1].isalnum() or line_text[word_start-1] == '_'):
            word_start -= 1
            
        word_end = col
        while word_end < len(line_text) and (line_text[word_end].isalnum() or line_text[word_end] == '_'):
            word_end += 1
            
        word = line_text[word_start:word_end].strip()
        if not word: return "break"

        # --- 1. DETECÇÃO DE CONTEXTO (O mesmo cérebro do Tooltip) ---
        is_field = False
        parent_var = ""
        
        if word_start > 0 and line_text[word_start-1] == '.':
            is_field = True
            p_end = word_start - 1
            p_start = p_end
            while p_start > 0 and (line_text[p_start-1].isalnum() or line_text[p_start-1] == '_'):
                p_start -= 1
            parent_var = line_text[p_start:p_end]
            
        elif word_start > 1 and line_text[word_start-2:word_start] == '->':
            is_field = True
            p_end = word_start - 2
            p_start = p_end
            while p_start > 0 and (line_text[p_start-1].isalnum() or line_text[p_start-1] == '_'):
                p_start -= 1
            parent_var = line_text[p_start:p_end]

        target_line = None
        lines = self.get_text().split('\n')

        # --- 2. BUSCA DO ALVO ---
        if is_field and parent_var:
            # Lógica para campos de Struct (Busca dentro do bloco correto)
            struct_name = None
            parent_info = self._find_local_or_macro_definition(parent_var, line)
            
            if parent_info: 
                match = re.search(r'struct\s+(\w+)', parent_info)
                if match: struct_name = match.group(1)
            elif hasattr(self, 'latest_semantic') and self.latest_semantic:
                sem = self.latest_semantic
                if hasattr(sem, 'global_scope') and parent_var in sem.global_scope:
                    full_decl = self._format_c_type(sem.global_scope[parent_var], parent_var)
                    match = re.search(r'struct\s+(\w+)', full_decl)
                    if match: struct_name = match.group(1)
                    
            if struct_name:
                in_target_struct = False
                for i, l in enumerate(lines):
                    if re.search(r'struct\s+' + re.escape(struct_name) + r'\s*\{', l):
                        in_target_struct = True
                    elif in_target_struct and '}' in l:
                        in_target_struct = False
                        
                    if in_target_struct:
                        field_pattern = re.compile(r'\b(int|char|void|struct\s+\w+)\s*(\**)\s*' + re.escape(word) + r'\b')
                        if field_pattern.search(l):
                            target_line = i + 1
                            break

        else:
            # Lógica para Variáveis Locais, Globais, Macros e Funções
            
            # Tenta aproveitar a linha que o Tooltip Local já calculou!
            local_info = self._find_local_or_macro_definition(word, line)
            if local_info:
                match = re.search(r'linha\s+(\d+)', local_info)
                if match:
                    target_line = int(match.group(1))
                elif "Macro" in local_info:
                    for i, l in enumerate(lines):
                        if re.match(r'^\s*#\s*define\s+' + re.escape(word) + r'\b', l):
                            target_line = i + 1
                            break
            
            # Se não achou localmente, busca no motor Semântico Global
            if not target_line and hasattr(self, 'latest_semantic') and self.latest_semantic:
                sem = self.latest_semantic
                if hasattr(sem, 'functions') and word in sem.functions:
                    target_line = getattr(sem.functions[word], 'lineno', None)
                
                if not target_line:
                    for i, l in enumerate(lines):
                        if re.search(r'struct\s+' + re.escape(word) + r'\s*\{', l):
                            target_line = i + 1
                            break
                        elif re.search(r'\b(int|char|void|struct\s+\w+)\s*(\**)\s*' + re.escape(word) + r'\b', l):
                            target_line = i + 1
                            break

        # --- 3. O SALTO VISUAL ---
        if target_line:
            # Acha a coluna exata da palavra na linha de destino
            target_line_text = self.text_area.get(f"{target_line}.0", f"{target_line}.end")
            match = re.search(r'\b' + re.escape(word) + r'\b', target_line_text)
            target_col = match.start() if match else 0
            
            pos = f"{target_line}.{target_col}"
            
            # Move o cursor e rola a tela
            self.text_area.mark_set("insert", pos)
            self.text_area.see(pos)
            self._highlight_current_line()
            
            # NOVO: Efeito de "piscar" a palavra encontrada para guiar os olhos do usuário!
            end_pos = f"{target_line}.{target_col + len(word)}"
            self.text_area.tag_add("bracket_match", pos, end_pos)
            self.after(400, lambda: self.text_area.tag_remove("bracket_match", "1.0", "end"))

        return "break"
        
        
    def _run_linter(self):
        if self.language != 'c': return
        self.text_area.tag_remove("linter_error", "1.0", "end")
        
        if hasattr(self, 'workspace_dir') and self.workspace_dir:
            try: os.chdir(self.workspace_dir)
            except: pass
            if hasattr(Preprocessor, 'LOCAL_INCLUDE_DIRS'):
                Preprocessor.LOCAL_INCLUDE_DIRS = [self.workspace_dir, "./"]
        
        code = self.get_text()
        if not code.strip(): return
        
        try:
            pre = Preprocessor()
            clean_code = pre.preprocess(code)
            tokens = list(tokenize(clean_code))
            parser = Parser(tokens)
            ast = parser.parse_program()
            
            semantic = Semantic(ast)
            semantic.analyze()
            self.latest_semantic = semantic
            
            self.apply_semantic_highlighting()
            warnings_list = getattr(semantic, 'warnings', [])
            
            for w in warnings_list:
                # Pinta as cobrinhas amarelas no texto
                match = re.search(r'(?:linha|line)\s+(\d+)', w, re.IGNORECASE)
                if match:
                    lineno = match.group(1)
                    word_match = re.search(r"'(.*?)'", w)
                    if word_match:
                        word = word_match.group(1)
                        idx = self.text_area.search(word, f"{lineno}.0", stopindex=f"{lineno}.end")
                        if idx:
                            end_idx = f"{idx}+{len(word)}c"
                            self.text_area.tag_add("linter_warning", idx, end_idx)
                    else:
                        line_text = self.text_area.get(f"{lineno}.0", f"{lineno}.end")
                        offset = len(line_text) - len(line_text.lstrip())
                        self.text_area.tag_add("linter_warning", f"{lineno}.{offset}", f"{lineno}.end")

            # Sem erros, envia None, mas repassa a lista de warnings
            if self.on_linter_callback: 
                self.on_linter_callback("", None, warnings_list)
                
        except Exception as e:
            error_msg = str(e)
            lineno = None
            
            match = re.search(r'(linha|line)\s+(\d+)', error_msg, re.IGNORECASE)
            if match:
                lineno = match.group(2)
                word_match = re.search(r"'(.*?)'", error_msg)
                if word_match:
                    word = word_match.group(1)
                    idx = self.text_area.search(word, f"{lineno}.0", stopindex=f"{lineno}.end")
                    if idx:
                        end_idx = f"{idx}+{len(word)}c"
                        self.text_area.tag_add("linter_error", idx, end_idx)
                        if self.on_linter_callback:
                            self.on_linter_callback(error_msg, lineno, []) # Avisos vazios se houver erro
                        return
                
                line_text = self.text_area.get(f"{lineno}.0", f"{lineno}.end")
                offset = len(line_text) - len(line_text.lstrip())
                self.text_area.tag_add("linter_error", f"{lineno}.{offset}", f"{lineno}.end")

            if self.on_linter_callback:
                self.on_linter_callback(error_msg, lineno, [])
        
    def _highlight_current_line(self):
        self.text_area.tag_remove("current_line", "1.0", "end")
        self.text_area.tag_add("current_line", "insert linestart", "insert lineend+1c")
        self.text_area.tag_lower("current_line")

    def _update_cursor_status(self):
        idx = self.text_area.index("insert")
        line, col = idx.split('.')
        if self.on_cursor_callback:
            self.on_cursor_callback(line, col)

    def highlight_syntax(self):
        self._clear_tags()
        
        if self.language == 'c':
            # 1. Pinta primeiro o que "engole" o resto (Comentários e Strings)
            self._highlight_regex(r'//.*', "comment")
            self._highlight_regex(r'".*?"', "string")
            self._highlight_regex(r"'.*?'", "string")
            
            # 2. Trava de segurança: não pinta se já for comentário ou string!
            ignore = ["comment", "string"]
            
            # 3. Pinta a sintaxe básica respeitando a trava
            self._highlight_regex(r'\b(int|char|void|struct|typedef)\b', "kw_type", ignore_tags=ignore)
            self._highlight_regex(r'\b(if|else|while|for|return|break|continue|switch|case|default)\b', "kw_flow", ignore_tags=ignore)
            self._highlight_regex(r'\b\d+\b', "number", ignore_tags=ignore)
            self._highlight_regex(r'^\s*#\w+', "kw_flow", ignore_tags=ignore) 
            
        elif self.language == 'asm':
            # A mesma lógica para o Assembly!
            self._highlight_regex(r';.*', "comment")
            
            ignore = ["comment"]
            self._highlight_regex(r'\b(LDA|STA|ADD|SUB|MUL|DIV|JMP|JZ|JN|CALL|RET|MOV|SOP|LDI|STI|INT|NAND|SHIFT)\b', "asm_op", ignore_tags=ignore)
            self._highlight_regex(r'\b\d+\b', "number", ignore_tags=ignore)

        # 4. Chama a Coloração Semântica (que já tem a trava embutida)
        self.apply_semantic_highlighting()
        
    def apply_semantic_highlighting(self):
        """Pinta variáveis globais, funções e structs baseado no conhecimento real do compilador."""
        if not hasattr(self, 'latest_semantic') or not self.latest_semantic:
            return
            
        sem = self.latest_semantic

        # 1. Agrupa os nomes conhecidos
        globals_names = [v for v in sem.global_scope.keys() if v not in sem.functions] if hasattr(sem, 'global_scope') else []
        struct_names = list(sem.structs.keys()) if hasattr(sem, 'structs') else []
        func_names = list(sem.functions.keys()) if hasattr(sem, 'functions') else []
        builtin_names = [f for funcs in sem.BUILTIN_LIBS.values() for f in funcs.keys()] if hasattr(sem, 'BUILTIN_LIBS') else []

        # 2. Aplica as cores via Regex (Ignorando Comentários e Strings!)
        ignore = ["comment", "string"]
        
        if globals_names:
            pattern = r'\b(' + '|'.join(map(re.escape, globals_names)) + r')\b'
            self._highlight_regex(pattern, "hl_global", ignore_tags=ignore)

        if struct_names:
            pattern = r'\b(' + '|'.join(map(re.escape, struct_names)) + r')\b'
            self._highlight_regex(pattern, "hl_struct", ignore_tags=ignore)

        if func_names:
            pattern = r'\b(' + '|'.join(map(re.escape, func_names)) + r')\b'
            self._highlight_regex(pattern, "hl_function", ignore_tags=ignore)

        if builtin_names:
            pattern = r'\b(' + '|'.join(map(re.escape, builtin_names)) + r')\b'
            self._highlight_regex(pattern, "hl_builtin", ignore_tags=ignore)

        # 3. CORREÇÃO DO SHADOWING UNIVERSAL (Variáveis locais mascarando globais, funções ou structs)
        if hasattr(sem, 'local_symbols'):
            lines = self.get_text().split('\n')
            blocks = self._get_fold_blocks()
            
            # Para cada bloco de chaves { } no código
            for start_line, end_line in blocks.items():
                func_name = None
                signature_line_idx = start_line - 1
                
                # Procura a assinatura da função (ex: void atacar()) na linha da chave ou acima
                for offset in [0, -1, -2]:
                    idx = start_line + offset - 1
                    if 0 <= idx < len(lines):
                        match = re.search(r'\b([a-zA-Z_]\w*)\s*\(', lines[idx])
                        if match:
                            func_name = match.group(1)
                            signature_line_idx = idx
                            break
                            
                # Se achou a função, verifica se ela tem variáveis locais fazendo shadowing
                if func_name and func_name in sem.local_symbols:
                    local_vars = sem.local_symbols[func_name]
                    
                    # Para cada variável local, verifica se ela "roubou" o nome de algo global
                    for var_name in local_vars:
                        tags_to_remove = []
                        if var_name in globals_names: tags_to_remove.append("hl_global")
                        if var_name in func_names:    tags_to_remove.append("hl_function")
                        if var_name in struct_names:  tags_to_remove.append("hl_struct")
                        if var_name in builtin_names: tags_to_remove.append("hl_builtin")
                        
                        # Se houver conflito, arranca as cores especiais dentro deste escopo local
                        if tags_to_remove:
                            pattern = r'\b' + re.escape(var_name) + r'\b'
                            for i in range(signature_line_idx, end_line):
                                for match in re.finditer(pattern, lines[i]):
                                    s_idx = f"{i+1}.{match.start()}"
                                    e_idx = f"{i+1}.{match.end()}"
                                    for tag in tags_to_remove:
                                        self.text_area.tag_remove(tag, s_idx, e_idx)

    def _highlight_regex(self, pattern, tag, ignore_tags=None):
        full_text = self.text_area.get("1.0", "end")
        for match in re.finditer(pattern, full_text, re.MULTILINE):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            
            # --- FIX: Ignora a pintura se a palavra já estiver dentro de um comentário ou string ---
            if ignore_tags:
                current_tags = self.text_area.tag_names(start_idx)
                if any(t in current_tags for t in ignore_tags):
                    continue
                    
            self.text_area.tag_add(tag, start_idx, end_idx)
            
    def _clear_tags(self):
        for tag in ["kw_type", "kw_flow", "asm_op", "string", "comment", "number", "error_line", "warning_line", "linter_warning", "linter_error", "hl_function", "hl_global", "hl_struct", "hl_builtin"]:
            self.text_area.tag_remove(tag, "1.0", "end")

    def match_brackets(self):
        self.text_area.tag_remove("bracket_match", "1.0", tk.END)
        insert_idx = self.text_area.index("insert")
        char_before = self.text_area.get(f"{insert_idx}-1c")
        char_after = self.text_area.get(insert_idx)
        
        pairs = {')': '(', ']': '[', '}': '{', '(': ')', '[': ']', '{': '}'}
        openers = ['(', '[', '{']
        closers = [')', ']', '}']

        target_char = None
        direction = None 
        start_pos = None

        if char_before in closers:
            target_char = char_before; direction = 'back'; start_pos = f"{insert_idx}-1c"
        elif char_after in openers:
            target_char = char_after; direction = 'forward'; start_pos = insert_idx 
        
        if not target_char: return

        match_char = pairs[target_char]
        count = 1
        
        if direction == 'back':
            search_pos = f"{start_pos}-1c"
            while True:
                pos = self.text_area.search(r'[(){}\[\]]', search_pos, stopindex="1.0", backwards=True, regexp=True)
                if not pos: break
                found = self.text_area.get(pos)
                if found == target_char: count += 1
                elif found == match_char: count -= 1
                
                if count == 0:
                    self.text_area.tag_add("bracket_match", pos)
                    self.text_area.tag_add("bracket_match", start_pos)
                    return
                search_pos = f"{pos}-1c"

        elif direction == 'forward':
            search_pos = f"{start_pos}+1c"
            while True:
                pos = self.text_area.search(r'[(){}\[\]]', search_pos, stopindex="end", forwards=True, regexp=True)
                if not pos: break
                found = self.text_area.get(pos)
                if found == target_char: count += 1
                elif found == match_char: count -= 1
                
                if count == 0:
                    self.text_area.tag_add("bracket_match", pos)
                    self.text_area.tag_add("bracket_match", start_pos)
                    return
                search_pos = f"{pos}+1c"

    def format_code(self, event=None):
        if self.language != 'c': return "break"
        
        self.text_area.edit_separator()
        code_text = self.get_text()
        
        # 1. TENTA FORMATAR PELA ÁRVORE SINTÁTICA (AST)
        try:
            tokens = list(tokenize(code_text))
            parser = Parser(tokens)
            ast = parser.parse_program()
            
            formatter = ASTFormatter()
            perfect_code = formatter.format(ast)
            
            self.set_text(perfect_code)
            
            # Avisa que a AST teve sucesso
            if hasattr(self, 'msg_tab'):
                self.log(self.msg_tab, "🪄 Formatação Inteligente (AST) aplicada com sucesso.", clear=True)
            
        except Exception as e:
            # 2. FALLBACK: O CÓDIGO TEM ERROS DE SINTAXE. 
            if hasattr(self, 'msg_tab') and hasattr(self, 'msg_notebook'):
                self.log(self.msg_tab, f"⚠️ Formatação Inteligente abortada devido a Erro de Sintaxe: {e}\nAplicando alinhamento básico de emergência.", clear=True)
                self.msg_notebook.select(self.msg_tab.master)
                
            self.format_code_basic(code_text)
            
        self.text_area.edit_separator()
        return "break"

    def format_code_basic(self, text):
        """Formatador heurístico de emergência (Fallback).
        Quebra o código em linhas caso esteja espremido e aplica indentação básica."""
        
        # 1. Separa o código forçando quebras de linha após chaves e ponto-e-vírgulas
        res = ""
        in_str = False
        paren_level = 0
        
        for i, c in enumerate(text):
            # Controle de Strings (para não quebrar blocos lá dentro)
            if c == '"' and (i == 0 or text[i-1] != '\\'):
                in_str = not in_str
                
            # Controle de Parênteses (para não quebrar o ; dentro do for(;;))
            if not in_str:
                if c == '(': paren_level += 1
                elif c == ')': paren_level = max(0, paren_level - 1)
                
            res += c
            
            # Força a quebra de linha imediatamente após estes símbolos
            if not in_str:
                if c == '{' or c == '}':
                    res += '\n'
                elif c == ';' and paren_level == 0:
                    res += '\n'
                    
        # Junta "}\n else" para ficar elegante na mesma linha "} else"
        res = re.sub(r'\}\s*else', '} else', res)
        
        # 2. Agora aplica a Indentação (COM CORREÇÃO DE CASCATA)
        lines = res.split('\n')
        formatted = []
        indent = 0
        
        for line in lines:
            s = line.strip()
            # Ignora linhas puramente vazias geradas pelas quebras forçadas
            if not s: 
                continue
            
            # Conta o total de chaves abertas e fechadas na linha atual
            opens = s.count('{')
            closes = s.count('}')
            
            # Se a linha começa fechando a chave, diminui o recuo desta linha
            if s.startswith("}"):
                indent = max(0, indent - 1)
                closes -= 1 # Desconta a chave inicial para não abater duas vezes depois
                
            formatted.append("    " * indent + s)
            
            # Atualiza o recuo para a PRÓXIMA linha baseado no saldo de chaves
            indent = max(0, indent + opens - closes)
                
        self.set_text("\n".join(formatted))
            
    def toggle_comment(self, event=None):
        self.text_area.focus_set()
        self.text_area.edit_separator()
        
        ranges = self.text_area.tag_ranges("sel")
        
        if ranges:
            start_line = int(self.text_area.index(ranges[0]).split('.')[0])
            end_line = int(self.text_area.index(ranges[1]).split('.')[0])
            
            if self.text_area.index(ranges[1]).split('.')[1] == '0' and end_line > start_line:
                end_line -= 1
        else:
            start_line = int(self.text_area.index("insert").split('.')[0])
            end_line = start_line

        for line in range(start_line, end_line + 1):
            pos = f"{line}.0"
            text = self.text_area.get(pos, f"{pos}+2c")
            if text == "//": 
                self.text_area.delete(pos, f"{pos}+2c")
            else: 
                self.text_area.insert(pos, "//")
                
        self.highlight_syntax()
        self.text_area.edit_separator()
        return "break" 

    def refactor_rename(self, event=None):
        if self.language != 'c': return "break"
        
        # 1. Pega a palavra exatamente sob o cursor
        idx = self.text_area.index("insert")
        line, col = map(int, idx.split('.'))
        line_text = self.text_area.get(f"{line}.0", f"{line}.end")
        
        word_start = col
        while word_start > 0 and (line_text[word_start-1].isalnum() or line_text[word_start-1] == '_'):
            word_start -= 1
            
        word_end = col
        while word_end < len(line_text) and (line_text[word_end].isalnum() or line_text[word_end] == '_'):
            word_end += 1
            
        old_word = line_text[word_start:word_end].strip()
        
        if not old_word or not re.match(r'^[A-Za-z_]\w*$', old_word):
            messagebox.showwarning("Refatorar", "Posicione o cursor sobre uma variável ou função válida.")
            return "break"

        # 2. Cria o Painel de Renomeação
        dialog = tk.Toplevel(self)
        dialog.title(f"Renomear: {old_word}")
        dialog.geometry("350x180")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        bg_color = self.colors["bg"]
        fg_color = self.colors["fg"]
        dialog.configure(bg=bg_color)
        
        tk.Label(dialog, text=f"Novo nome para '{old_word}':", bg=bg_color, fg=fg_color).pack(pady=(10, 5))
        new_name_var = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=new_name_var, width=30)
        entry.pack(pady=5)
        entry.focus_set()
        
        scope_var = tk.StringVar(value="local")
        frame_radios = tk.Frame(dialog, bg=bg_color)
        frame_radios.pack(pady=5)
        tk.Radiobutton(frame_radios, text="Escopo Local", variable=scope_var, value="local", bg=bg_color, fg=fg_color, selectcolor=self.colors.get("ln_bg", "gray")).pack(side="left", padx=5)
        tk.Radiobutton(frame_radios, text="Escopo Global", variable=scope_var, value="global", bg=bg_color, fg=fg_color, selectcolor=self.colors.get("ln_bg", "gray")).pack(side="left", padx=5)

        def apply_rename(event=None):
            new_word = new_name_var.get().strip()
            if not new_word or new_word == old_word or not re.match(r'^[A-Za-z_]\w*$', new_word):
                dialog.destroy()
                return
                
            is_global = (scope_var.get() == "global")
            start_idx = "1.0"
            end_idx = "end"
            
            if not is_global:
                # Usa a engenharia de blocos do Folding para detectar os limites da função atual
                cursor_line = int(self.text_area.index("insert").split('.')[0])
                blocks = self._get_fold_blocks()
                
                enclosing_start, enclosing_end = None, None
                for s, e in sorted(blocks.items()):
                    if s <= cursor_line <= e:
                        if enclosing_start is None or (s <= enclosing_start and e >= enclosing_end):
                            enclosing_start = s
                            enclosing_end = e
                            
                if enclosing_start and enclosing_end:
                    start_idx = f"{max(1, enclosing_start - 1)}.0" # Pega a assinatura da função
                    end_idx = f"{enclosing_end}.end"
            
            # --- Proteção de Undo/Redo Granular ---
            self.text_area.edit_separator()
            
            count = 0
            search_idx = start_idx
            
            while True:
                # Busca exata e verifica as bordas manualmente (foge do conflito de RegEx do Tcl)
                pos = self.text_area.search(old_word, search_idx, stopindex=end_idx, exact=True)
                if not pos: break
                    
                match_end = f"{pos}+{len(old_word)}c"
                char_before = self.text_area.get(f"{pos}-1c") if self.text_area.index(pos) != "1.0" else " "
                char_after = self.text_area.get(match_end)
                
                # Verifica se é uma palavra isolada (Word Boundary manual)
                if not (char_before.isalnum() or char_before == '_') and not (char_after.isalnum() or char_after == '_'):
                    tags = self.text_area.tag_names(pos)
                    
                    # CIENTE DO LEXER: Só renomeia se NÃO for um Comentário ou uma String
                    if "string" not in tags and "comment" not in tags:
                        self.text_area.delete(pos, match_end)
                        self.text_area.insert(pos, new_word)
                        search_idx = f"{pos}+{len(new_word)}c"
                        count += 1
                    else:
                        search_idx = match_end
                else:
                    search_idx = match_end
            
            self.text_area.edit_separator()
            self.highlight_syntax()
            dialog.destroy()
            
            if count > 0:
                self.after(200, self._run_linter) # Valida as alterações
                messagebox.showinfo("Refatoração", f"Símbolo '{old_word}' renomeado para '{new_word}' em {count} locais.", parent=self.winfo_toplevel())
            else:
                messagebox.showinfo("Refatoração", "Nenhuma ocorrência alterada.", parent=self.winfo_toplevel())

        ttk.Button(dialog, text="Renomear", command=apply_rename).pack(pady=(10, 0))
        entry.bind("<Return>", apply_rename)
        
        return "break"
    
    def _format_c_type(self, t, name):
        """Monta a string de declaração C perfeitamente, juntando ponteiros e arrays."""
        if not t: return f"desconhecido {name}"
        t_name = t.__class__.__name__
        
        if t_name == 'IntType': return f"int {name}".strip()
        if t_name == 'CharType': return f"char {name}".strip()
        if t_name == 'VoidType': return f"void {name}".strip()
        if t_name == 'StructType': return f"struct {getattr(t, 'name', '')} {name}".strip()
        
        # Recursividade para montar ponteiros e arrays de dentro pra fora
        if t_name == 'PointerType': 
            return self._format_c_type(getattr(t, 'base', None), f"*{name}")
        if t_name == 'ArrayType': 
            return self._format_c_type(getattr(t, 'base', None), f"{name}[{getattr(t, 'size', '')}]")
            
        return f"{t} {name}".strip()

    def _find_struct_field(self, struct_name, field_name):
        """Busca a declaração de um campo específico dentro de uma struct."""
        text = self.get_text()
        # Encontra o bloco da struct específica
        struct_pattern = re.compile(r'struct\s+' + re.escape(struct_name) + r'\s*\{([^}]*)\}')
        match = struct_pattern.search(text)
        if match:
            body = match.group(1)
            # Procura o campo dentro deste bloco
            field_pattern = re.compile(r'\b(int|char|void|struct\s+\w+)\s*(\**)\s*' + re.escape(field_name) + r'\b\s*(\[.*?\])?')
            f_match = field_pattern.search(body)
            if f_match:
                base_type = f_match.group(1).strip()
                pointers = f_match.group(2).strip() if f_match.group(2) else ""
                arrays = f_match.group(3).strip() if f_match.group(3) else ""
                full_decl = f"{base_type} {pointers}{field_name}{arrays}"
                return f"⚙️ Campo da Struct ({struct_name}): {full_decl}"
        return None

    def _find_local_or_macro_definition(self, word, cursor_line):
        """Escaneia o texto da IDE em busca de Macros ou Variáveis Locais/Parâmetros."""
        text = self.get_text()
        lines = text.split('\n')
        
        # 1. Checar Macros (#define) no arquivo inteiro
        for i, line in enumerate(lines):
            # Casa com: #define DEZ 10
            match = re.match(r'^\s*#\s*define\s+' + re.escape(word) + r'\b\s*(.*)', line)
            if match:
                val = match.group(1).strip()
                return f"🔄 Macro (#define): {word}\nSubstitui por: {val}"
                
        # 2. Checar Variáveis Locais e Parâmetros (Lendo de baixo pra cima a partir do mouse)
        # --- FIX: Adicionado \b no final da variável para evitar falsos positivos (ex: 'p' dentro de 'pt_ptr') ---
        pattern = re.compile(r'\b(int|char|void|struct\s+\w+)\s*(\**)\s*' + re.escape(word) + r'\b\s*(\[.*?\])?')
        
        for i in range(cursor_line - 1, -1, -1):
            if i < len(lines):
                line = lines[i]
                match = pattern.search(line)
                if match:
                    base_type = match.group(1).strip()
                    pointers = match.group(2).strip() if match.group(2) else ""
                    arrays = match.group(3).strip() if match.group(3) else ""
                    
                    # Monta bonitinho: int *c ou int a[10]
                    full_decl = f"{base_type} {pointers}{word}{arrays}"
                    return f"📍 Local / Parâmetro: {full_decl}\nDeclarado na linha {i+1}"
                    
        return None
    
    def _on_hover(self, event):
        if self.language != 'c': return
        
        idx = self.text_area.index(f"@{event.x},{event.y}")
        line, col = map(int, idx.split('.'))
        
        line_text = self.text_area.get(f"{line}.0", f"{line}.end")
        
        word_start = col
        while word_start > 0 and (line_text[word_start-1].isalnum() or line_text[word_start-1] == '_'):
            word_start -= 1
            
        word_end = col
        while word_end < len(line_text) and (line_text[word_end].isalnum() or line_text[word_end] == '_'):
            word_end += 1
            
        word = line_text[word_start:word_end]
        if not word:
            self._hide_tooltip()
            return
            
        if hasattr(self, 'current_hover_word') and self.current_hover_word == word:
            return

        # --- FIX: Detecção Inteligente de Acesso a Campo (. ou ->) ---
        is_field = False
        parent_var = ""
        
        if word_start > 0 and line_text[word_start-1] == '.':
            is_field = True
            p_end = word_start - 1
            p_start = p_end
            while p_start > 0 and (line_text[p_start-1].isalnum() or line_text[p_start-1] == '_'):
                p_start -= 1
            parent_var = line_text[p_start:p_end]
            
        elif word_start > 1 and line_text[word_start-2:word_start] == '->':
            is_field = True
            p_end = word_start - 2
            p_start = p_end
            while p_start > 0 and (line_text[p_start-1].isalnum() or line_text[p_start-1] == '_'):
                p_start -= 1
            parent_var = line_text[p_start:p_end]

        tooltip_text = None

        if is_field and parent_var:
            # Se for um campo de struct, pula a busca local e caça o pai!
            struct_name = None
            parent_info = self._find_local_or_macro_definition(parent_var, line)
            
            if parent_info: # O pai é local (ex: pt ou pt_ptr)
                match = re.search(r'struct\s+(\w+)', parent_info)
                if match: struct_name = match.group(1)
            elif hasattr(self, 'latest_semantic') and self.latest_semantic: # O pai é global
                sem = self.latest_semantic
                if hasattr(sem, 'global_scope') and parent_var in sem.global_scope:
                    full_decl = self._format_c_type(sem.global_scope[parent_var], parent_var)
                    match = re.search(r'struct\s+(\w+)', full_decl)
                    if match: struct_name = match.group(1)
                    
            if struct_name:
                tooltip_text = self._find_struct_field(struct_name, word)
                
            if not tooltip_text:
                tooltip_text = f"⚙️ Campo: {word} (Struct {struct_name or '?'})"
        else:
            # --- 1. BUSCA LOCAL E MACROS (Variáveis Normais) ---
            local_macro_info = self._find_local_or_macro_definition(word, line)
            if local_macro_info:
                tooltip_text = local_macro_info

        # --- 2. BUSCA DINÂMICA GERAL (Consulta o Analisador Semântico) ---
        if not tooltip_text and hasattr(self, 'latest_semantic') and self.latest_semantic:
            sem = self.latest_semantic
            
            # 1º PRIORIDADE: É uma função Nativa importada via #include <...> (Ex: printint, mul)
            if hasattr(sem, 'BUILTIN_LIBS') and word in sem.BUILTIN_LIBS:
                params_count = sem.BUILTIN_LIBS[word].get(word, '?')
                tooltip_text = f"📚 Função Padrão (stdlib): {word}()\nArgumentos esperados: {params_count}"
            
            # 2º: É uma Função do usuário?
            elif hasattr(sem, 'functions') and word in sem.functions:
                func = sem.functions[word]
                # Usa a nova formatação para pegar o retorno da função!
                ret_type = self._format_c_type(getattr(func, 'rettype', None), "")
                linha = getattr(func, 'lineno', '?')
                tooltip_text = f"⚡ Função: {ret_type} {word}()\nDefinida na linha {linha}"
                
            # 3º: É uma Variável Global (agora detecta array e ponteiro com perfeição!)
            elif hasattr(sem, 'global_scope') and word in sem.global_scope:
                v_type = sem.global_scope[word]
                full_decl = self._format_c_type(v_type, word)
                tooltip_text = f"📦 Variável Global: {full_decl}"
                
            # 4º: É uma Struct?
            elif hasattr(sem, 'structs') and word in sem.structs:
                st = sem.structs[word]
                size = st.get('size', '?') if isinstance(st, dict) else '?'
                tooltip_text = f"🧱 Struct: {word}\nTamanho na memória: {size} palavra(s) de 16-bits"
                
        # --- 3. BUSCA ESTÁTICA (Fallback do Dicionário para palavras-chave) ---
        if not tooltip_text and word in TOOLTIPS_DB:
            tooltip_text = TOOLTIPS_DB[word]

        # --- EXIBIÇÃO DO BALÃO ---
        if tooltip_text:
            self._show_tooltip(event.x_root, event.y_root + 15, tooltip_text)
            self.current_hover_word = word
        else:
            self._hide_tooltip()    
    
    def _show_tooltip(self, x, y, text):
        self._hide_tooltip()
        self.tooltip_window = tk.Toplevel(self)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.attributes('-topmost', True)
        
        bg_color = "#3e3e42" if self.is_dark else "#f3f3f3"
        fg_color = "#ffffff" if self.is_dark else "#000000"
        
        label = tk.Label(self.tooltip_window, text=text, justify="left", 
                         bg=bg_color, fg=fg_color, relief="solid", borderwidth=1, 
                         font=("Segoe UI", 10), padx=8, pady=4)
        label.pack()

    def _hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None
            if hasattr(self, 'current_hover_word'):
                del self.current_hover_word

    def _on_click(self, event=None):
        self.text_area.edit_separator()
        self._hide_tooltip()
        self._clear_snippet_mode()

    def _on_content_changed(self, event=None):
        self._sync_folds_from_tags()
        self._apply_folds()
        
        if self.show_line_numbers: self.update_line_numbers()
        self._sync_lines_view()
        self.highlight_syntax()
        
        if self.linter_after_id:
            self.after_cancel(self.linter_after_id)
        self.linter_after_id = self.after(1000, self._run_linter)

    def _on_key_release(self, event=None):
        self._on_content_changed()
        self.match_brackets()
        self._highlight_current_line()
        self._update_cursor_status()
        
        if hasattr(self, 'snippet_marks') and self.snippet_marks:
            # Ignora o sync se for apenas navegação do teclado
            if event and getattr(event, 'keysym', '') not in ["Tab", "Return", "Escape", "Up", "Down", "Left", "Right"]:
                self._sync_snippet()

    def _clear_snippet_mode(self):
        """Desativa o modo Live Snippet e limpa as pinturas visuais."""
        if hasattr(self, 'snippet_marks') and self.snippet_marks is not None:
            self.text_area.tag_remove("snippet_hl", "1.0", "end")
            self.snippet_marks = None
            self.snippet_final = None
            self.current_tab_stop = None

    def _paint_snippet_highlights(self):
        """Pinta todas as variáveis ativas do snippet no ecrã."""
        self.text_area.tag_remove("snippet_hl", "1.0", "end")
        if not hasattr(self, 'snippet_marks') or not self.snippet_marks: return
        for n_stop, data in self.snippet_marks.items():
            p_start, p_end = data["primary"]
            self.text_area.tag_add("snippet_hl", p_start, p_end)
            for s_start, s_end in data["syncs"]:
                self.text_area.tag_add("snippet_hl", s_start, s_end)

    def _handle_tab(self, event):
        """Captura a tecla TAB para saltar sequencialmente entre as variáveis e o fim do bloco."""
        if hasattr(self, 'snippet_marks') and self.snippet_marks is not None:
            stops = sorted(self.snippet_marks.keys())
            
            # Se ainda temos variáveis numéricas para pular ($1, $2, $3...)
            if self.current_tab_stop in stops:
                current_idx = stops.index(self.current_tab_stop)
                if current_idx + 1 < len(stops):
                    # Pula para a próxima variável
                    self.current_tab_stop = stops[current_idx + 1]
                    p_start, p_end = self.snippet_marks[self.current_tab_stop]["primary"]
                    self.text_area.tag_remove("sel", "1.0", "end")
                    self.text_area.tag_add("sel", p_start, p_end)
                    self.text_area.mark_set("insert", p_end)
                    self.text_area.see(p_start)
                    return "break"
                    
            # Se acabaram as variáveis numéricas, pula para a paragem final ($0)
            if hasattr(self, 'snippet_final') and self.snippet_final:
                try:
                    self.text_area.mark_set("insert", self.snippet_final)
                    self.text_area.tag_remove("sel", "1.0", "end")
                    self.text_area.see("insert")
                except tk.TclError:
                    pass
                    
            self._clear_snippet_mode()
            return "break" # Impede que o TAB injete um espaço em branco
        return None

    def _sync_snippet(self):
        """Reflete o texto digitado na variável principal atual para as réplicas."""
        if not hasattr(self, 'snippet_marks') or not self.snippet_marks:
            return
            
        if self.current_tab_stop not in self.snippet_marks:
            return
            
        active_data = self.snippet_marks[self.current_tab_stop]
        if not active_data.get("primary"): 
            return
            
        try:
            p_start, p_end = active_data["primary"]
            current_text = self.text_area.get(p_start, p_end)
            
            # Atualiza todas as sincronizações desta paragem atual
            for s_start, s_end in active_data["syncs"]:
                if self.text_area.get(s_start, s_end) != current_text:
                    self.text_area.delete(s_start, s_end)
                    self.text_area.insert(s_start, current_text)
                    
            self._paint_snippet_highlights()
                
        except tk.TclError:
            self._clear_snippet_mode()

    def insert_snippet(self, text):
        self.text_area.edit_separator()
        self._clear_snippet_mode()

        # 1. Fallback de Segurança: Auto-injetar caso o texto seja o modelo burro antigo
        if "$0" not in text and not re.search(r'\$\{\d+:', text):
            if "{\n    \n}" in text:
                text = text.replace("{\n    \n}", "{\n    $0\n}", 1)
            elif "{\n    \n" in text:
                text = text.replace("{\n    \n", "{\n    $0\n", 1)
            for ph in ["expr", "i", "Nome", "count", "letter", "ptr", "procedure", "soma"]:
                text = re.sub(rf'\b({ph})\b', rf'${{1:{ph}}}', text)
            if "$0" not in text:
                text += "$0"

        # 2. Calcular a indentação
        try:
            line_idx = self.text_area.index("insert").split(".")[0]
            current_line = self.text_area.get(f"{line_idx}.0", f"{line_idx}.end")
            indent = ""
            for char in current_line:
                if char in (" ", "\t"): indent += char
                else: break
        except:
            indent = ""

        # 3. Processar a string e ejetar no documento
        lines = text.split('\n')
        self.snippet_marks = {}
        self.snippet_final = None
        self.current_tab_stop = None
        
        # FIX: Regex atualizada para capturar MÚLTIPLOS índices numéricos (ex: ${1:...}, ${2:...})
        pattern = re.compile(r'(\$\{(\d+):([^\}]+)\})|(\$0)')
        
        for line_num, line in enumerate(lines):
            if line_num > 0:
                self.text_area.insert("insert", "\n" + indent)
                
            last_idx = 0
            for match in pattern.finditer(line):
                self.text_area.insert("insert", line[last_idx:match.start()])
                
                if match.group(4) == "$0":
                    mark_name = "snip_final"
                    self.text_area.mark_set(mark_name, "insert")
                    self.text_area.mark_gravity(mark_name, tk.LEFT)
                    self.snippet_final = mark_name
                else:
                    n_stop = int(match.group(2))
                    word = match.group(3)
                    
                    start_idx = self.text_area.index("insert")
                    self.text_area.insert("insert", word)
                    end_idx = self.text_area.index("insert")
                    
                    if n_stop not in self.snippet_marks:
                        p_start = f"snip_p_start_{n_stop}"
                        p_end = f"snip_p_end_{n_stop}"
                        self.text_area.mark_set(p_start, start_idx)
                        self.text_area.mark_gravity(p_start, tk.LEFT)
                        self.text_area.mark_set(p_end, end_idx)
                        self.text_area.mark_gravity(p_end, tk.LEFT)
                        self.snippet_marks[n_stop] = {"primary": (p_start, p_end), "syncs": []}
                    else:
                        s_start = f"snip_{n_stop}_s_start_{len(self.snippet_marks[n_stop]['syncs'])}"
                        s_end = f"snip_{n_stop}_s_end_{len(self.snippet_marks[n_stop]['syncs'])}"
                        self.text_area.mark_set(s_start, start_idx)
                        self.text_area.mark_gravity(s_start, tk.LEFT)
                        self.text_area.mark_set(s_end, end_idx)
                        self.text_area.mark_gravity(s_end, tk.LEFT)
                        self.snippet_marks[n_stop]["syncs"].append((s_start, s_end))
                        
                last_idx = match.end()
                
            self.text_area.insert("insert", line[last_idx:])
            
        # 4. Pós-processamento: Alterar gravidades para as variáveis expandirem ao digitar
        for n_stop, data in self.snippet_marks.items():
            self.text_area.mark_gravity(data["primary"][1], tk.RIGHT)
            for s_start, s_end in data["syncs"]:
                self.text_area.mark_gravity(s_end, tk.RIGHT)
                
        # 5. Seleciona o primeiro Tab Stop, ou pula para o final se não houver variáveis
        if self.snippet_marks:
            self.current_tab_stop = min(self.snippet_marks.keys())
            p_start, p_end = self.snippet_marks[self.current_tab_stop]["primary"]
            
            self.text_area.tag_remove("sel", "1.0", "end")
            self.text_area.tag_add("sel", p_start, p_end)
            self.text_area.mark_set("insert", p_end)
            self.text_area.see(p_start)
            
            self._paint_snippet_highlights()
                
        elif self.snippet_final:
            self.text_area.mark_set("insert", self.snippet_final)
            self.text_area.see("insert")

        self.highlight_syntax()
        self.text_area.edit_separator()
        self.text_area.focus()
            
    def _on_click_release(self, event=None):
        self.match_brackets()
        self._highlight_current_line()
        self._update_cursor_status()

    def update_line_numbers(self):
        try:
            current_yview = self.line_numbers.yview()
            
            self.line_numbers.config(state='normal')
            self.line_numbers.delete('1.0', 'end')
            
            blocks = self._get_fold_blocks()
            lines = int(self.text_area.index('end-1c').split('.')[0])
            bms = self.bookmarks
            
            i = 1
            while i <= lines:
                fold_symbol = "   "
                if i in blocks:
                    fold_symbol = "[+]" if i in self.folded_blocks else "[-]"
                    
                mark = "★ " if i in bms else "  "
                
                self.line_numbers.insert('end', f"{mark}{fold_symbol} {i}\n")
                
                if i in bms:
                    self.line_numbers.tag_add("bookmark_line", f"{self.line_numbers.index('end-2c')} linestart", f"{self.line_numbers.index('end-2c')} lineend")
                
                if i in self.folded_blocks:
                    i = blocks[i] 
                
                i += 1
                
            self.line_numbers.config(state='disabled')
            
            self.line_numbers.yview_moveto(current_yview[0])
            
        except: pass

    def _auto_indent(self, event):
        text = self.text_area
        line_idx = text.index("insert").split(".")[0]
        line_text = text.get(f"{line_idx}.0", f"{line_idx}.end")
        indent = ""
        for char in line_text:
            if char in (" ", "\t"): indent += char
            else: break
        if line_text.strip().endswith("{"): indent += "    "
        
        self.text_area.edit_separator()
        text.insert("insert", "\n" + indent)
        self.text_area.edit_separator()
        return "break"

    def highlight_error(self, lineno):
        self.text_area.tag_remove("error_line", "1.0", "end")
        
        line_text = self.text_area.get(f"{lineno}.0", f"{lineno}.end")
        offset = len(line_text) - len(line_text.lstrip())
        
        self.text_area.tag_add("error_line", f"{lineno}.{offset}", f"{lineno}.end")
        self.text_area.see(f"{lineno}.0")
        self.text_area.focus()
        
    def highlight_warning(self, lineno):
        self.text_area.tag_remove("warning_line", "1.0", "end")
        
        line_text = self.text_area.get(f"{lineno}.0", f"{lineno}.end")
        offset = len(line_text) - len(line_text.lstrip())
        
        self.text_area.tag_add("warning_line", f"{lineno}.{offset}", f"{lineno}.end")
        self.text_area.see(f"{lineno}.0")
        self.text_area.focus()

    def show_autocomplete(self, event=None):
        if self.language != 'c': return "break"
        self.text_area.focus_set() 
        
        if hasattr(self, 'ac_window') and self.ac_window.winfo_exists():
            self.ac_window.destroy()

        insert_idx = self.text_area.index("insert")
        line_start = f"{insert_idx} linestart"
        current_line = self.text_area.get(line_start, insert_idx)
        
        suggestions = []
        is_snippet = {}
        prefix = ""

        match_include = re.search(r'#include\s*[<"]\s*([a-zA-Z0-9_\.]*)$', current_line)
        
        if match_include:
            prefix = match_include.group(1).lower()
            stdlib_libs = []
            try:
                stdlib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stdlib')
                if os.path.exists(stdlib_path):
                    for f in os.listdir(stdlib_path):
                        if f.endswith('.cariri'): 
                            stdlib_libs.append(os.path.splitext(f)[0])
            except: pass
            
            suggestions = sorted([w for w in stdlib_libs if w.lower().startswith(prefix)])
            
        else:
            match_word = re.search(r'([a-zA-Z_]\w*)$', current_line)
            prefix = match_word.group(1).lower() if match_word else ""
            
            full_text = self.text_area.get("1.0", "end")
            all_words = set(re.findall(r'\b[a-zA-Z_]\w*\b', full_text))
            
            filtered_words = set()
            for w in all_words:
                if w.lower().startswith(prefix) and w.lower() != prefix:
                    filtered_words.add(w)
            
            suggestions.extend(sorted(list(filtered_words)))
            
            for cat, snips in CODE_SNIPPETS.items():
                for name, code in snips.items():
                    if not prefix or name.lower().startswith(prefix):
                        sug_name = f"💡 {name}"
                        suggestions.append(sug_name)
                        is_snippet[sug_name] = code

        if not suggestions: 
            suggestions = ["(Sem sugestões)"]

        self.text_area.update_idletasks()
        bbox = self.text_area.bbox("insert")
        
        if not bbox:
            return "break"
            
        x, y, cx, cy = bbox
        x += self.text_area.winfo_rootx() + 25
        y += self.text_area.winfo_rooty() + 20

        self.ac_window = tk.Toplevel(self)
        self.ac_window.wm_overrideredirect(True)
        self.ac_window.wm_geometry(f"+{x}+{y}")

        self.ac_window.transient(self.winfo_toplevel()) 
        self.ac_window.attributes("-topmost", True)     
        self.ac_window.lift()                           

        self.ac_list = tk.Listbox(self.ac_window, font=(self.font_family, self.font_size), 
                                  bg=self.colors["bg"], fg=self.colors["fg"], 
                                  selectbackground=self.colors["select_bg"], width=25)
        self.ac_list.pack()
        
        for w in suggestions: 
            self.ac_list.insert(tk.END, w)
        self.ac_list.selection_set(0)

        def close_ac(e=None):
            if hasattr(self, 'ac_window') and self.ac_window.winfo_exists():
                self.ac_window.destroy()
            self.text_area.after(10, self.text_area.focus_force)
            return "break"

        def insert_word(e=None):
            selection = self.ac_list.get(tk.ACTIVE)
            if selection == "(Sem sugestões)":
                return close_ac()
            
            if prefix:
                self.text_area.delete(f"insert-{len(prefix)}c", "insert")
            
            if selection in is_snippet:
                self.insert_snippet(is_snippet[selection])
            else:
                self.text_area.edit_separator()
                self.text_area.insert("insert", selection)
                self.highlight_syntax()
                self.text_area.edit_separator()
                
            return close_ac()

        self.ac_list.bind("<Return>", insert_word)
        self.ac_list.bind("<Double-Button-1>", insert_word)
        self.ac_list.bind("<Escape>", close_ac)
        self.ac_window.bind("<FocusOut>", lambda e: close_ac())

        self.ac_list.focus_set()
        return "break"

    def get_text(self): return self.text_area.get("1.0", "end-1c")
    def set_text(self, text): 
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", text)
        self.update_line_numbers()
        self.highlight_syntax()
        self.reset_modified() 
        
    def delete_text(self): 
        self.text_area.delete("1.0", "end")
        self.reset_modified()

    # Adicionar no final da classe CodeEditor:
    def get_state(self):
        """Retorna o estado atual da aba para ser salvo no .hist"""
        idx = self.text_area.index("insert")
        line, col = map(int, idx.split('.'))
        return {
            "filename": self.filename,
            "cursor": {"line": line, "col": col},
            "bookmarks": list(self.bookmarks),
            "folded_blocks": list(self.folded_blocks)
        }

    def restore_state(self, state):
        """Restaura o estado da aba a partir dos dados do .hist"""
        if "bookmarks" in state:
            for b in state["bookmarks"]:
                self.text_area.tag_add("bookmark_data", f"{b}.0", f"{b}.end")
        if "folded_blocks" in state:
            self.folded_blocks = set(state["folded_blocks"])
            self._apply_folds()
        if "cursor" in state:
            pos = f"{state['cursor']['line']}.{state['cursor']['col']}"
            self.text_area.mark_set("insert", pos)
            self.text_area.see(pos)
            self._highlight_current_line()
        self.update_line_numbers()
        
    # Adicione no __init__ do CodeEditor para rastrear o histórico de seleções
    # self.selection_history = []  <-- Coloque isso junto das outras variáveis do __init__

    def _clear_sel_history(self, event=None):
        """Limpa o histórico se o usuário clicar em outro lugar ou digitar."""
        if event and event.keysym in ['Shift_L', 'Shift_R', 'Alt_L', 'Alt_R', 'Up', 'Down']:
            return # Ignora se estiver apenas usando o atalho
        if hasattr(self, 'selection_history'):
            self.selection_history.clear()

    def expand_selection(self, event=None):
        if self.language != 'c': return "break"
        
        try:
            tokens = list(tokenize(self.get_text()))
            parser = Parser(tokens)
            real_ast = parser.parse_program()
        except Exception:
            return "break"

        try:
            sel_start = self.text_area.index("sel.first")
            sel_end = self.text_area.index("sel.last")
        except tk.TclError:
            sel_start = self.text_area.index("insert")
            sel_end = sel_start

        s_line, s_col = map(int, sel_start.split('.'))
        e_line, e_col = map(int, sel_end.split('.'))

        if not hasattr(self, 'selection_history'): self.selection_history = []
        self.selection_history.append((sel_start, sel_end))

        best_node = None
        best_node_size = float('inf')

        def search_node(node):
            nonlocal best_node, best_node_size
            if node is None: return

            if hasattr(node, 'lineno') and getattr(node, 'lineno') is not None:
                n_start_line = node.lineno
                n_start_col = getattr(node, 'colno', 0) 
                n_end_line = getattr(node, 'end_lineno', n_start_line)
                n_end_col = getattr(node, 'end_colno', 9999)
                if n_end_col == 'end': n_end_col = 9999

                starts_before = (n_start_line < s_line) or (n_start_line == s_line and n_start_col <= s_col)
                ends_after = (n_end_line > e_line) or (n_end_line == e_line and n_end_col >= e_col)

                node_size = (n_end_line - n_start_line) * 1000 + (n_end_col - n_start_col)
                current_size = (e_line - s_line) * 1000 + (e_col - s_col)

                if starts_before and ends_after and node_size > current_size:
                    if node_size < best_node_size:
                        best_node = node
                        best_node_size = node_size

            if hasattr(node, '__dict__'):
                for key, value in vars(node).items():
                    if key.startswith('_'): continue
                    
                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, tuple):
                                for sub in item:
                                    if hasattr(sub, '__dict__'): search_node(sub)
                            elif hasattr(item, '__dict__'):
                                search_node(item)
                    elif hasattr(value, '__dict__'):
                        search_node(value)

        search_node(real_ast)

        if best_node:
            new_start = f"{getattr(best_node, 'lineno')}.{getattr(best_node, 'colno', 0)}"
            new_end = f"{getattr(best_node, 'end_lineno', getattr(best_node, 'lineno'))}.{getattr(best_node, 'end_colno', 'end')}"

            self.text_area.tag_remove("sel", "1.0", "end")
            self.text_area.tag_add("sel", new_start, new_end)
            self.text_area.mark_set("insert", new_end)
            self.text_area.see(new_start)

        return "break"

    def shrink_selection(self, event=None):
        """Encolhe a seleção voltando no histórico salvo."""
        if self.language != 'c': return "break"
        if hasattr(self, 'selection_history') and self.selection_history:
            prev_start, prev_end = self.selection_history.pop()
            self.text_area.tag_remove("sel", "1.0", "end")
            
            if prev_start != prev_end:
                self.text_area.tag_add("sel", prev_start, prev_end)
                
            self.text_area.mark_set("insert", prev_end)
            self.text_area.see(prev_start)
        return "break"

# =============================================================================
# CLASSE PRINCIPAL DA IDE 
# =============================================================================
class CaririIDE:
    def __init__(self, root):
        self.root = root
        self.root.title("GIBAO IDE - Workspace CompSim")
        self.root.geometry("1200x700") 
        self.theme_dark = True 
        
        self.show_asm = tk.BooleanVar(value=True)
        self.show_logs = tk.BooleanVar(value=True)
        self.show_explorer = tk.BooleanVar(value=True)
        self.show_outline = tk.BooleanVar(value=True)
        self.auto_save_var = tk.BooleanVar(value=False)

        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.current_dir = os.getcwd()
        self.workspace_root = os.getcwd()
        
        self.create_widgets()
        self.bind_shortcuts()
        self.toggle_theme() 
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_file_explorer()
        
        self.load_workspace()
        
        self.auto_refresh_ms = 5000  # Intervalo de 5 segundos
        self.schedule_explorer_refresh() # Inicia o loop de atualização
    
    def schedule_explorer_refresh(self):
        """Atualiza o explorer e agenda a próxima atualização."""
        # Só atualiza se o explorer estiver visível para economizar processamento
        if self.show_explorer.get():
            self.refresh_file_explorer()
        
        # Agenda a execução novamente após o intervalo definido
        self._explorer_job = self.root.after(self.auto_refresh_ms, self.schedule_explorer_refresh)

    # --- RECURSO: Função Inteligente para Selecionar Tudo Global ---
    def global_select_all(self, event):
        widget = self.root.focus_get()
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end")
            return "break"
        elif isinstance(widget, (tk.Entry, ttk.Entry)):
            widget.select_range(0, tk.END)
            return "break"

    # --- NOVO: Auxiliar para resgatar todos os editores abertos em qualquer painel ---
    def _get_all_editors(self):
        editors = []
        for nb in (self.editor_notebook, getattr(self, 'editor_notebook_2', None)):
            if nb:
                for tab_id in nb.tabs():
                    editors.append((nb, self.root.nametowidget(tab_id)))
        return editors

    def get_current_editor(self):
        if getattr(self, 'active_notebook', None) is None:
            self.active_notebook = self.editor_notebook
            
        current_tab = self.active_notebook.select()
        if current_tab:
            return self.root.nametowidget(current_tab)
        return None

    def update_title(self, is_modified=False):
        editor = self.get_current_editor()
        if editor:
            name = os.path.basename(editor.filename) if editor.filename else "Sem Título"
            mod_mark = "*" if editor.is_modified() else ""
            self.root.title(f"GIBAO IDE - Workspace CompSim - {name}{mod_mark}")
        else:
            self.root.title("GIBAO IDE - Workspace CompSim")

    def update_tab_title(self, editor):
        try:
            # Encontra em qual notebook a aba está
            for nb, ed in self._get_all_editors():
                if ed == editor:
                    idx = nb.index(editor)
                    name = os.path.basename(editor.filename) if editor.filename else "Sem Título"
                    if editor.is_modified():
                        name += " *"
                    nb.tab(idx, text=name)
                    break
        except tk.TclError:
            pass

    def on_editor_change(self, is_modified, editor):
        self.update_tab_title(editor)
        if editor == self.get_current_editor():
            self.update_title()
        
        if self.auto_save_var.get() and editor.filename and is_modified:
            if hasattr(editor, 'autosave_id') and editor.autosave_id:
                self.root.after_cancel(editor.autosave_id)
            editor.autosave_id = self.root.after(1500, lambda: self._autosave_editor(editor))

        # --- NOVO: Sincronização em Tempo Real no Split View ---
        if is_modified and editor.filename:
            # Trava para evitar loop infinito de sincronização entre os painéis
            if not getattr(self, '_is_syncing', False):
                self._is_syncing = True
                current_text = editor.get_text()
                
                for nb, other_ed in self._get_all_editors():
                    if other_ed != editor and other_ed.filename == editor.filename:
                        # Salva o estado visual do outro editor
                        cursor_pos = other_ed.text_area.index("insert")
                        yview = other_ed.text_area.yview()
                        
                        # Atualiza o texto silenciosamente
                        other_ed.text_area.delete("1.0", "end")
                        other_ed.text_area.insert("1.0", current_text)
                        other_ed.update_line_numbers()
                        other_ed.highlight_syntax()
                        
                        # Força o status de modificado para aparecer o asterisco (*)
                        other_ed.text_area.edit_modified(True)
                        other_ed.on_change_callback(True)
                        
                        # Devolve o cursor e o scroll para onde estavam
                        other_ed.text_area.mark_set("insert", cursor_pos)
                        other_ed.text_area.yview_moveto(yview[0])
                        
                self._is_syncing = False
    
    def on_asm_cursor(self, line, col):
        """Mapeamento Reverso: Clicar no ASM destaca a linha C correspondente."""
        if hasattr(self, 'asm_to_c_map'):
            c_line = self.asm_to_c_map.get(int(line))
            ed = self.get_current_editor()
            if ed:
                if c_line:
                    ed.highlight_mapped_lines([c_line])
                else:
                    ed.highlight_mapped_lines([]) # Limpa se clicar em instrução sem mapa
    
    def _autosave_editor(self, editor):
        if editor.filename:
            with open(editor.filename, 'w', encoding='utf-8') as f:
                f.write(editor.get_text())
            editor.reset_modified()
            self.update_tab_title(editor)
            if editor == self.get_current_editor():
                self.update_title()

    def update_cursor_status(self, line, col):
        col_display = int(col) + 1 
        self.status_bar.config(text=f"Pronto | Ln {line}, Col {col_display} | Workspace CompSim | Ctrl+Space: Autocomplete | Alt+Shift+F: Formatar")
        
        # --- NOVO: LIVE DISASSEMBLY (C -> ASM) ---
        if hasattr(self, 'c_to_asm_map') and self.show_asm.get():
            c_line = int(line)
            asm_lines = self.c_to_asm_map.get(c_line, [])
            self.asm_editor.highlight_mapped_lines(asm_lines)
    
    def sync_file_views(self, source_ed):
        """Sincroniza o texto e a flag de modificação em tempo real para todos os espelhos do arquivo."""
        # --- FIX: winfo_exists() impede que a função tente ler uma aba que acabou de ser fechada
        if not source_ed or not source_ed.winfo_exists() or not source_ed.filename: return
        if getattr(self, '_is_syncing', False): return
        
        self._is_syncing = True
        
        try:
            current_text = source_ed.get_text()
            is_mod = source_ed.is_modified()
            
            for nb, other_ed in self._get_all_editors():
                # Proteção extra: verifica se a aba destino (other_ed) também não foi fechada
                if other_ed != source_ed and other_ed.winfo_exists() and other_ed.filename == source_ed.filename:
                    if other_ed.get_text() != current_text:
                        # Salva a posição do scroll e do cursor do painel espelho
                        cursor_pos = other_ed.text_area.index("insert")
                        yview = other_ed.text_area.yview()
                        
                        # Substitui o texto silenciosamente
                        other_ed.text_area.delete("1.0", "end")
                        other_ed.text_area.insert("1.0", current_text)
                        other_ed.update_line_numbers()
                        other_ed.highlight_syntax()
                        
                        # Devolve o cursor e o scroll
                        other_ed.text_area.mark_set("insert", cursor_pos)
                        other_ed.text_area.yview_moveto(yview[0])
                    
                    # Garante que a estrela (*) de modificado fique igual nos dois painéis
                    other_ed.text_area.edit_modified(is_mod)
                    if other_ed.on_change_callback:
                        other_ed.on_change_callback(is_mod)
                        
        finally:
            # O 'finally' garante que a trava seja liberada mesmo se algum outro erro oculto ocorrer
            self._is_syncing = False
    
    def add_editor_tab(self, filename=None, text=""):
        if getattr(self, 'active_notebook', None) is None:
            self.active_notebook = self.editor_notebook
            
        # --- FIX: Função atualizada para receber também os Warnings! ---
        def handle_linter(msg, lineno, warnings_list=None):
            if warnings_list is None:
                warnings_list = []
                
            filepath = editor.filename or "Sem Título"
            
            # Alimenta a tabela com erros e avisos
            self.update_diagnostics(filepath, msg, lineno, warnings_list)
            
            # Mantém o histórico textual no console
            if msg:
                self.log(self.msg_tab, f"❌ Erro Fatal: {msg}", clear=True)
            elif warnings_list:
                self.log(self.msg_tab, f"⚠️ Linter OK (com {len(warnings_list)} avisos).", clear=True)
            else:
                self.log(self.msg_tab, "✅ Linter: Código OK.", clear=True)

        editor = CodeEditor(self.active_notebook, language='c', width=45, height=12,
                            on_cursor_callback=self.update_cursor_status,
                            on_linter_callback=handle_linter) # <--- Pluga a função aqui!
                            
        editor.filename = filename
        editor.workspace_dir = os.path.dirname(filename) if filename else self.current_dir
        editor.on_change_callback = lambda modified, ed=editor: self.on_editor_change(modified, ed)
        editor.apply_theme(self.theme_dark)
        
        editor.text_area.bind("<Button-3>", lambda e: self.context_menu.post(e.x_root, e.y_root))
        
        def set_active_pane(event, nb=self.active_notebook):
            self.active_notebook = nb
            
        editor.text_area.bind("<FocusIn>", set_active_pane, add="+")
        editor.text_area.bind("<Button-1>", set_active_pane, add="+")
        
        def intercept_open(event):
            self.open_c_file()
            return "break" 
            
        def intercept_new(event):
            self.new_file()
            return "break"

        editor.text_area.bind('<Control-o>', intercept_open)
        editor.text_area.bind('<Control-O>', intercept_open)
        editor.text_area.bind('<Control-n>', intercept_new)
        editor.text_area.bind('<Control-N>', intercept_new)
        
        # --- NOVO: Engatilhar espelhamento no momento em que você digita ou cola ---
        editor.text_area.bind("<KeyRelease>", lambda e, ed=editor: self.sync_file_views(ed), add="+")
        editor.text_area.bind("<<Paste>>", lambda e, ed=editor: self.root.after(10, lambda: self.sync_file_views(ed)), add="+")
        editor.text_area.bind("<<Cut>>", lambda e, ed=editor: self.root.after(10, lambda: self.sync_file_views(ed)), add="+")
        # -------------------------------------------------------------------------
        
        editor.set_text(text)
        editor.reset_modified()
        
        title = os.path.basename(filename) if filename else "Sem Título"
        self.active_notebook.add(editor, text=title)
        self.active_notebook.select(editor)
        return editor
        
    def close_current_tab(self, event=None):
        editor = self.get_current_editor()
        if not editor: return "break"
        
        if editor.is_modified():
            ans = messagebox.askyesnocancel("Salvar", f"Deseja salvar as alterações em {os.path.basename(editor.filename) if editor.filename else 'Sem Título'}?")
            if ans is True:
                if not self.save_c_file(): return "break"
            elif ans is None:
                return "break"
                
        self.active_notebook.forget(editor)
        editor.destroy()
        self.on_tab_changed()
        return "break"

    def close_tab_by_index(self, index, notebook):
        editor = self.root.nametowidget(notebook.tabs()[index])
        notebook.select(editor)
        self.active_notebook = notebook
        self.close_current_tab()

    def on_tab_middle_click(self, event):
        try:
            notebook = event.widget
            idx = notebook.index(f"@{event.x},{event.y}")
            self.close_tab_by_index(idx, notebook)
        except tk.TclError:
            pass

    def on_tab_changed(self, event=None):
        if getattr(self, 'active_notebook', None) is None:
            self.active_notebook = self.editor_notebook
            
        # Atualiza a referência baseada no evento disparado
        if event and hasattr(event, 'widget'):
            self.active_notebook = event.widget

        editor = self.get_current_editor()
        if editor:
            self.update_title()
            editor._update_cursor_status()
        else:
            self.root.title("GIBAO IDE - Workspace CompSim")
            self.status_bar.config(text="Pronto | Nenhum arquivo aberto | Workspace CompSim")
    
    def toggle_split_view(self):
        if str(self.editor_notebook_2) in self.editor_split_pane.panes():
            # --- NOVO: Limpar as abas do painel inferior ao fechar ---
            for tab_id in list(self.editor_notebook_2.tabs()):
                ed = self.root.nametowidget(tab_id)
                
                # Verifica se o arquivo só está aberto embaixo e não foi salvo
                is_unique = True
                for nb, other_ed in self._get_all_editors():
                    if nb == self.editor_notebook and other_ed.filename == ed.filename:
                        is_unique = False
                        break
                
                if is_unique and ed.is_modified():
                    self.editor_notebook_2.select(ed)
                    ans = messagebox.askyesnocancel("Salvar", f"Deseja salvar as alterações em {os.path.basename(ed.filename) if ed.filename else 'Sem Título'} antes de fechar o painel?")
                    if ans is True:
                        self.active_notebook = self.editor_notebook_2
                        if not self.save_c_file():
                            return # Usuário cancelou no menu de salvar
                    elif ans is None:
                        return # Usuário cancelou o fechamento
                        
                # Destrói a aba inferior
                ed.destroy()
                
            # Esconde o painel de baixo
            self.editor_split_pane.forget(self.editor_notebook_2)
            self.active_notebook = self.editor_notebook
        else:
            # Exibe o painel de baixo
            self.editor_split_pane.add(self.editor_notebook_2, weight=1)
            self.active_notebook = self.editor_notebook_2
            
            # Espelhar a aba ativa de cima
            top_ed = None
            if self.editor_notebook.tabs():
                top_ed = self.root.nametowidget(self.editor_notebook.select())
                
            if top_ed:
                found = False
                for tab_id in self.editor_notebook_2.tabs():
                    bot_ed = self.root.nametowidget(tab_id)
                    if top_ed.filename and bot_ed.filename == top_ed.filename:
                        self.editor_notebook_2.select(bot_ed)
                        found = True
                        break
                
                if not found:
                    self.add_editor_tab(top_ed.filename, top_ed.get_text())

        # --- Forçar o reposicionamento dos divisores (Sash) ---
        def fix_layout():
            self.root.update_idletasks()
            
            if self.show_logs.get() and str(self.bottom_frame) in self.main_pane.panes():
                total_h = self.main_pane.winfo_height()
                if total_h > 100:
                    self.main_pane.sashpos(0, int(total_h * 0.65))
            
            if str(self.editor_notebook_2) in self.editor_split_pane.panes():
                ed_h = self.editor_split_pane.winfo_height()
                if ed_h > 50:
                    self.editor_split_pane.sashpos(0, int(ed_h * 0.5))
                    
        self.root.after(100, fix_layout)
    
    # --- WRAPPERS DE COMANDOS PARA A ABA ATUAL ---
    def expand_selection_current(self, event=None):
        ed = self.get_current_editor()
        if ed: ed.expand_selection(event)
        return "break"

    def shrink_selection_current(self, event=None):
        ed = self.get_current_editor()
        if ed: ed.shrink_selection(event)
        return "break"
        
    def format_current_editor(self, event=None):
        ed = self.get_current_editor()
        if ed: ed.format_code()

    def insert_snippet_current(self, code):
        ed = self.get_current_editor()
        if ed: ed.insert_snippet(code)

    def toggle_comment_current(self, event=None):
        ed = self.get_current_editor()
        if ed: ed.toggle_comment()
        
    def refactor_current_editor(self, event=None):
        ed = self.get_current_editor()
        if ed: ed.refactor_rename()
        return "break"

    def autocomplete_current(self, event=None):
        ed = self.get_current_editor()
        if ed: ed.show_autocomplete()

    def goto_def_current(self, event=None):
        ed = self.get_current_editor()
        if ed: ed._go_to_definition(event)

    def toggle_bookmark_current(self, event=None):
        ed = self.get_current_editor()
        if ed: ed.toggle_bookmark()

    def next_bookmark_current(self, event=None):
        ed = self.get_current_editor()
        if ed: ed.goto_next_bookmark()

    def undo_current_editor(self, event=None):
        ed = self.get_current_editor()
        if ed: ed._perform_undo()
        return "break"

    def redo_current_editor(self, event=None):
        ed = self.get_current_editor()
        if ed: ed._perform_redo()
        return "break"

    def create_widgets(self):
        self.status_bar = ttk.Label(self.root, text="Pronto | Ln 1, Col 1 | Workspace CompSim | Ctrl+Space: Autocomplete | Ctrl+Shift+F: Formatar", relief=tk.SUNKEN, anchor='w')
        self.status_bar.pack(side="bottom", fill="x")
        
        self.horizontal_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.horizontal_pane.pack(fill='both', expand=True, pady=(30, 0))

        # 1. Sidebar
        self.sidebar_nb = ttk.Notebook(self.horizontal_pane)
        self.horizontal_pane.add(self.sidebar_nb, weight=1)

        self.file_tree = ttk.Treeview(self.sidebar_nb, show="tree")
        self.file_tree.bind("<Double-1>", self.on_file_double_click)
        self.sidebar_nb.add(self.file_tree, text="Explorador")

        self.outline_tree = ttk.Treeview(self.sidebar_nb, show="tree")
        self.sidebar_nb.add(self.outline_tree, text="Estrutura")

        # 2. Área Direita Principal
        self.main_pane = ttk.PanedWindow(self.horizontal_pane, orient=tk.VERTICAL)
        self.horizontal_pane.add(self.main_pane, weight=4)

        self.top_pane = ttk.PanedWindow(self.main_pane, orient=tk.HORIZONTAL)
        self.main_pane.add(self.top_pane, weight=2)
        
        # --- ATUALIZADO: Configuração do Split View (Painel Vertical) ---
        self.editor_split_pane = ttk.PanedWindow(self.top_pane, orient=tk.VERTICAL)
        self.top_pane.add(self.editor_split_pane, weight=1)
        
        self.editor_notebook = ttk.Notebook(self.editor_split_pane)
        self.editor_split_pane.add(self.editor_notebook, weight=1)
        self.editor_notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.editor_notebook.bind("<Button-2>", self.on_tab_middle_click)
        self.editor_notebook.bind("<Button-1>", lambda e: setattr(self, 'active_notebook', self.editor_notebook))
        
        self.editor_notebook_2 = ttk.Notebook(self.editor_split_pane)
        self.editor_notebook_2.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.editor_notebook_2.bind("<Button-2>", self.on_tab_middle_click)
        self.editor_notebook_2.bind("<Button-1>", lambda e: setattr(self, 'active_notebook', self.editor_notebook_2))

        self.active_notebook = self.editor_notebook
        # -----------------------------------------------------------------
        
        self.asm_editor = CodeEditor(self.top_pane, show_line_numbers=True, width=35, height=12, language='asm', on_cursor_callback=self.on_asm_cursor)
        self.top_pane.add(self.asm_editor, weight=1)

        self.bottom_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.bottom_frame, weight=1)
        
        self.msg_notebook = ttk.Notebook(self.bottom_frame)
        self.msg_notebook.pack(fill='both', expand=True)
        
        # --- NOVO RECURSO: Aba de Problemas Globais (Diagnostics) ---
        self.problems_frame = ttk.Frame(self.msg_notebook)
        self.problems_tree = ttk.Treeview(self.problems_frame, columns=("File", "Line", "Description"), show="headings")
        self.problems_tree.heading("File", text="Arquivo")
        self.problems_tree.heading("Line", text="Linha")
        self.problems_tree.heading("Description", text="Descrição do Erro")
        self.problems_tree.column("File", width=150, anchor='w')
        self.problems_tree.column("Line", width=50, anchor='center')
        self.problems_tree.column("Description", width=600, anchor='w')
        
        scr_prob = ttk.Scrollbar(self.problems_frame, command=self.problems_tree.yview)
        self.problems_tree.configure(yscrollcommand=scr_prob.set)
        scr_prob.pack(side='right', fill='y')
        self.problems_tree.pack(side='left', fill='both', expand=True)
        
        self.problems_tree.bind("<Double-1>", self.on_problem_double_click)
        self.msg_notebook.add(self.problems_frame, text="✅ Problemas")
        # --------------------------------------------------------------

        def create_log_tab(name):
            frame = ttk.Frame(self.msg_notebook)
            text_widget = tk.Text(frame, font=("Consolas", 10), state='disabled', wrap='none', width=80, height=8)
            scr = ttk.Scrollbar(frame, command=text_widget.yview)
            text_widget.configure(yscrollcommand=scr.set)
            scr.pack(side='right', fill='y')
            text_widget.pack(side='left', fill='both', expand=True)
            self.msg_notebook.add(frame, text=name)
            
            text_widget.tag_config("hyperlink", foreground="blue", underline=True)
            text_widget.tag_bind("hyperlink", "<Enter>", lambda e: text_widget.config(cursor="hand2"))
            text_widget.tag_bind("hyperlink", "<Leave>", lambda e: text_widget.config(cursor=""))
            
            # --- FIX: Conecta o duplo-clique no painel ao mapeamento do código ---
            text_widget.bind("<Double-1>", lambda e, tw=text_widget: self.on_log_double_click(e, tw))
            
            return text_widget

        self.msg_tab = create_log_tab("Mensagens do Compilador")
        self.preproc_tab = create_log_tab("Pré-processador")
        self.tokens_tab = create_log_tab("Lexer (Tokens)")
        self.ast_tab = create_log_tab("Parser (AST)")
        self.semantic_tab = create_log_tab("Semântico")
        self.code_tab = create_log_tab("CodeGen (ASM)")
        self.optimizer_tab = create_log_tab("Otimizador")

        self.create_context_menu()
        self.create_menu()
        self.create_toolbar()

    def create_toolbar(self):
        toolbar = ttk.Frame(self.root)
        toolbar.place(x=0, y=0, relwidth=1)
        
        for text, cmd, bg in [("📄 Novo", self.new_file, None),
                              ("📂 Abrir", self.open_c_file, None),
                              ("💾 Salvar", self.save_c_file, None),
                              ("❌ Fechar Aba", self.close_current_tab, None),
                              ("|", None, None),
                              ("▶ COMPILAR", self.compile_code, "#2ea043"),
                              ("|", None, None),
                              ("🔍 Buscar", self.find_replace_dialog, None),
                              ("🪄 Formatar", self.format_current_editor, None),
                              ("🧹 Limpar Logs", self.clear_logs, None),
                              ("🎨 Tema", self.toggle_theme, None)]:
            if text == "|":
                ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5, fill='y', pady=2)
            elif bg:
                tk.Button(toolbar, text=text, command=cmd, bg=bg, fg="white", relief="flat").pack(side=tk.LEFT, padx=2, pady=2)
            else:
                ttk.Button(toolbar, text=text, command=cmd).pack(side=tk.LEFT, padx=2, pady=2)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Novo (Aba)", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Abrir", command=self.open_c_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Salvar Atual", command=self.save_c_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Fechar Aba Atual", command=self.close_current_tab, accelerator="Ctrl+W")
        file_menu.add_separator()
        file_menu.add_checkbutton(label="Auto-Salvar", variable=self.auto_save_var)
        file_menu.add_separator()
        file_menu.add_command(label="Salvar Assembly (CARIRI)", command=self.save_asm_file)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.on_close, accelerator="Ctrl+Q")
        menubar.add_cascade(label="Arquivo", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Desfazer", command=self.undo_current_editor, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Refazer", command=self.redo_current_editor, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Ir para Definição", command=self.goto_def_current, accelerator="F12")
        edit_menu.add_command(label="Encontrar Referências", command=self.find_references_current, accelerator="Shift+F12")
        edit_menu.add_separator()
        edit_menu.add_command(label="Localizar/Substituir (Aba)", command=self.find_replace_dialog, accelerator="Ctrl+F")
        edit_menu.add_command(label="Buscar em Arquivos (Global)", command=self.global_search_dialog, accelerator="Ctrl+Shift+F")
        edit_menu.add_command(label="Ir para Linha", command=self.goto_line, accelerator="Ctrl+G")
        edit_menu.add_separator()
        edit_menu.add_command(label="Alternar Marcador (Bookmark)", command=self.toggle_bookmark_current, accelerator="Ctrl+B")
        edit_menu.add_command(label="Próximo Marcador", command=self.next_bookmark_current, accelerator="F2")
        edit_menu.add_separator()
        edit_menu.add_command(label="Comentar/Descomentar", command=self.toggle_comment_current, accelerator="Ctrl+/")
        edit_menu.add_command(label="Autocompletar", command=self.autocomplete_current, accelerator="Ctrl+Space")
        edit_menu.add_command(label="Auto-Formatar Código", command=self.format_current_editor, accelerator="Shift+Alt+F")
        edit_menu.add_command(label="Renomear Símbolo (Refatorar)", command=self.refactor_current_editor, accelerator="Ctrl+R")
        menubar.add_cascade(label="Editar", menu=edit_menu)

        insert_menu = tk.Menu(menubar, tearoff=0)
        for category, snippets in CODE_SNIPPETS.items():
            cat_menu = tk.Menu(insert_menu, tearoff=0)
            for name, code in snippets.items():
                cat_menu.add_command(label=name, command=lambda c=code: self.insert_snippet_current(c))
            insert_menu.add_cascade(label=category, menu=cat_menu)
        menubar.add_cascade(label="Inserir", menu=insert_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Dividir Editor (Split View Cima/Baixo)", command=self.toggle_split_view)
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Painel Explorador", variable=self.show_explorer, command=self.toggle_panels)
        view_menu.add_checkbutton(label="Painel Estrutura", variable=self.show_outline, command=self.toggle_panels)
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Painel Assembly", variable=self.show_asm, command=self.toggle_panels)
        view_menu.add_checkbutton(label="Painel Logs", variable=self.show_logs, command=self.toggle_panels)
        menubar.add_cascade(label="Exibir", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Sobre o Compilador...", command=self.show_about_dialog)
        menubar.add_cascade(label="Ajuda", menu=help_menu)

        self.root.config(menu=menubar)

    def show_about_dialog(self):
        import webbrowser  
        
        about_win = tk.Toplevel(self.root)
        about_win.title("Sobre")
        about_win.geometry("420x340") 
        about_win.resizable(False, False)
        
        bg_color = "#1e1e1e" if self.theme_dark else "#ffffff"
        fg_color = "#d4d4d4" if self.theme_dark else "#000000"
        link_color = "#569cd6" if self.theme_dark else "#0000ee" 
        about_win.configure(bg=bg_color)
        
        try:
            logo_img = tk.PhotoImage(data=cs_image).subsample(4, 4)
            lbl_logo = tk.Label(about_win, image=logo_img, bg=bg_color)
            lbl_logo.image = logo_img 
        except Exception as e:
            lbl_logo = tk.Label(about_win, text="🌵", font=("Segoe UI Emoji", 36), bg=bg_color, fg="#2ea043")
            
        lbl_logo.pack(pady=(15, 5))
        
        lbl_title = tk.Label(about_win, text="GIBAO IDE", font=("Segoe UI", 16, "bold"), bg=bg_color, fg=fg_color)
        lbl_title.pack()
        
        lbl_comp = tk.Label(about_win, text="Generator of Instructions and Binary Assembly Objects C Compiler", font=("Segoe UI", 10, "italic"), bg=bg_color, fg=fg_color)
        lbl_comp.pack(pady=(0, 10))
        
        info_text = "Versão: 0.5.0\n" \
                    "Licença: Freeware\n" \
                    "Desenvolvedor: Garme (CompSim)"
                    
        lbl_info = tk.Label(about_win, text=info_text, font=("Segoe UI", 10), bg=bg_color, fg=fg_color, justify="center")
        lbl_info.pack(pady=(10, 0))
        
        lbl_link = tk.Label(about_win, text="http://compsim.crato.ifce.edu.br/", 
                            font=("Segoe UI", 10, "underline"), bg=bg_color, fg=link_color, cursor="hand2")
        lbl_link.pack(pady=(5, 15))
        lbl_link.bind("<Button-1>", lambda e: webbrowser.open("http://compsim.crato.ifce.edu.br/"))
        
        btn_ok = ttk.Button(about_win, text="OK", command=about_win.destroy)
        btn_ok.pack(pady=5)
        
        about_win.transient(self.root)
        about_win.grab_set()
        
        about_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (about_win.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (about_win.winfo_height() // 2)
        about_win.geometry(f"+{x}+{y}")
        
        self.root.wait_window(about_win)

    def create_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        
        self.context_menu.add_command(label="Desfazer (Ctrl+Z)", command=self.undo_current_editor)
        self.context_menu.add_command(label="Refazer (Ctrl+Y)", command=self.redo_current_editor)
        self.context_menu.add_separator()
        
        self.context_menu.add_command(label="Ir para Definição (F12)", command=self.goto_def_current)
        self.context_menu.add_separator()
        
        self.context_menu.add_command(label="Copiar", command=lambda: self.root.focus_get().event_generate("<<Copy>>"))
        self.context_menu.add_command(label="Colar", command=lambda: self.root.focus_get().event_generate("<<Paste>>"))
        self.context_menu.add_command(label="Formatar Documento", command=self.format_current_editor)
        self.context_menu.add_command(label="Renomear Símbolo (Refatorar)", command=self.refactor_current_editor)
        self.context_menu.add_command(label="Encontrar Referências (Shift+F12)", command=self.find_references_current)
        self.context_menu.add_separator()
        
        self.context_menu.add_command(label="Alternar Marcador (Ctrl+B)", command=self.toggle_bookmark_current)
        self.context_menu.add_command(label="Ir para Próximo Marcador (F2)", command=self.next_bookmark_current)
        self.context_menu.add_separator()
        
        snippet_menu = tk.Menu(self.context_menu, tearoff=0)
        for category, snippets in CODE_SNIPPETS.items():
            cat_menu = tk.Menu(snippet_menu, tearoff=0)
            for name, code in snippets.items():
                cat_menu.add_command(label=name, command=lambda c=code: self.insert_snippet_current(c))
            snippet_menu.add_cascade(label=category, menu=cat_menu)
        
        self.context_menu.add_cascade(label="Inserir Snippet", menu=snippet_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Compilar", command=self.compile_code)

    def bind_shortcuts(self):
        # --- FIX: Função auxiliar para bloquear eventos padrões invisíveis do Tkinter ---
        # Garante que ao pressionar Ctrl+O, ele não insira uma linha em branco no editor
        def run_and_break(func):
            def wrapper(event):
                func()
                return "break" # Aborta a propagação do evento
            return wrapper

        self.root.bind('<Control-n>', run_and_break(self.new_file))
        self.root.bind('<Control-N>', run_and_break(self.new_file))
        self.root.bind('<Control-o>', run_and_break(self.open_c_file))
        self.root.bind('<Control-O>', run_and_break(self.open_c_file))
        self.root.bind('<Control-s>', run_and_break(self.save_c_file))
        self.root.bind('<Control-S>', run_and_break(self.save_c_file))
        
        self.root.bind('<Control-w>', self.close_current_tab) # Já retorna "break" nativamente
        self.root.bind('<Control-q>', lambda e: self.on_close())
        self.root.bind('<Control-Q>', lambda e: self.on_close())
        
        self.root.bind('<F5>', run_and_break(self.compile_code))
        self.root.bind('<Control-f>', run_and_break(self.find_replace_dialog))
        self.root.bind('<Control-g>', run_and_break(self.goto_line))
        self.root.bind('<Control-G>', run_and_break(self.goto_line))
        self.root.bind('<Control-F>', run_and_break(self.global_search_dialog))
        self.root.bind('<Alt-F>', run_and_break(self.format_current_editor))
        self.root.bind('<Control-r>', self.refactor_current_editor)
        self.root.bind('<Control-R>', self.refactor_current_editor)
        self.root.bind('<F12>', run_and_break(self.goto_def_current))
        self.root.bind('<Shift-F12>', run_and_break(self.find_references_current))
        
        # Atalhos Globais Desfazer/Refazer
        self.root.bind('<Control-z>', self.undo_current_editor)
        self.root.bind('<Control-Z>', self.redo_current_editor) 
        self.root.bind('<Control-y>', self.redo_current_editor)
        self.root.bind('<Control-Y>', self.redo_current_editor)
        
        self.root.bind('<Control-space>', run_and_break(self.autocomplete_current))
        self.root.bind('<Control-b>', run_and_break(self.toggle_bookmark_current))
        self.root.bind('<Control-B>', run_and_break(self.toggle_bookmark_current))
        self.root.bind('<F2>', run_and_break(self.next_bookmark_current))
        self.root.bind('<Control-slash>', run_and_break(self.toggle_comment_current))
        
        self.root.bind('<Control-a>', self.global_select_all) # Já retorna "break" nativamente
        self.root.bind('<Control-A>', self.global_select_all)
        
        self.root.bind('<Shift-Alt-Up>', self.expand_selection_current)
        self.root.bind('<Shift-Alt-Down>', self.shrink_selection_current)
        
    
    def refresh_file_explorer(self):
        # Salva qual item estava selecionado antes de limpar
        selected_item = self.file_tree.selection()
        selected_text = ""
        if selected_item:
            selected_text = self.file_tree.item(selected_item[0], "text")

        self.file_tree.delete(*self.file_tree.get_children())
        try:
            # O restante do seu código original permanece...
            folder_node = self.file_tree.insert("", "end", text=os.path.basename(self.current_dir) or self.current_dir, open=True)
            
            arquivos_ordenados = sorted(os.listdir(self.current_dir), key=str.lower)
            for item in arquivos_ordenados:
                if item.endswith((".c", ".cariri", ".h", ".asm")):
                    node = self.file_tree.insert(folder_node, "end", text=item, values=[os.path.join(self.current_dir, item)])
                    # Tenta restaurar a seleção se o arquivo ainda existir
                    if item == selected_text:
                        self.file_tree.selection_set(node)
        except Exception:
            pass    
    
    def on_file_double_click(self, event):
        item = self.file_tree.selection()
        if not item: return
        values = self.file_tree.item(item[0], "values")
        if values:
            path = values[0]
            self.open_specific_file(path)

    def update_outline(self, semantic_obj, raw_code):
        self.outline_tree.delete(*self.outline_tree.get_children())
        
        prep_node = self.outline_tree.insert("", "end", text="Pré-processador", open=True)
        found_prep = False
        for match in re.finditer(r'^\s*#\s*(include|define|use)\s+(.*)', raw_code, re.MULTILINE):
            directive = match.group(1)
            val = match.group(2).strip()
            self.outline_tree.insert(prep_node, "end", text=f"#{directive} {val}")
            found_prep = True
        if not found_prep:
            self.outline_tree.delete(prep_node)

        if hasattr(semantic_obj, 'global_scope') and semantic_obj.global_scope:
            vars_node = self.outline_tree.insert("", "end", text="Variáveis Globais", open=True)
            for vname in semantic_obj.global_scope.keys():
                if not (hasattr(semantic_obj, 'functions') and vname in semantic_obj.functions):
                    self.outline_tree.insert(vars_node, "end", text=f"{vname}")

        if hasattr(semantic_obj, 'structs') and semantic_obj.structs:
            structs_node = self.outline_tree.insert("", "end", text="Structs", open=True)
            for sname in semantic_obj.structs.keys():
                self.outline_tree.insert(structs_node, "end", text=f"struct {sname}")
                
        if hasattr(semantic_obj, 'functions') and semantic_obj.functions:
            funcs_node = self.outline_tree.insert("", "end", text="Funções", open=True)
            for fname, func in semantic_obj.functions.items():
                if hasattr(func, 'rettype'):
                    self.outline_tree.insert(funcs_node, "end", text=f"{fname}()")

    def toggle_panels(self):
        if self.show_explorer.get():
            if str(self.file_tree) not in self.sidebar_nb.tabs():
                if len(self.sidebar_nb.tabs()) == 0:
                    self.sidebar_nb.add(self.file_tree, text="Explorador")
                else:
                    self.sidebar_nb.insert(0, self.file_tree, text="Explorador")
        else:
            if str(self.file_tree) in self.sidebar_nb.tabs():
                self.sidebar_nb.forget(self.file_tree)

        if self.show_outline.get():
            if str(self.outline_tree) not in self.sidebar_nb.tabs():
                self.sidebar_nb.add(self.outline_tree, text="Estrutura")
        else:
            if str(self.outline_tree) in self.sidebar_nb.tabs():
                self.sidebar_nb.forget(self.outline_tree)

        if not self.show_explorer.get() and not self.show_outline.get():
            if str(self.sidebar_nb) in self.horizontal_pane.panes():
                self.horizontal_pane.forget(self.sidebar_nb)
        else:
            if str(self.sidebar_nb) not in self.horizontal_pane.panes():
                self.horizontal_pane.insert(0, self.sidebar_nb, weight=1)

        if self.show_asm.get():
            if str(self.asm_editor) not in self.top_pane.panes():
                self.top_pane.add(self.asm_editor, weight=1)
        else:
            if str(self.asm_editor) in self.top_pane.panes():
                self.top_pane.forget(self.asm_editor)
        
        if self.show_logs.get():
            if str(self.bottom_frame) not in self.main_pane.panes():
                self.main_pane.add(self.bottom_frame, weight=1)
        else:
            if str(self.bottom_frame) in self.main_pane.panes():
                self.main_pane.forget(self.bottom_frame)
    
    def toggle_theme(self):
        self.theme_dark = not self.theme_dark
        self.asm_editor.apply_theme(self.theme_dark)
        
        for nb, ed in self._get_all_editors():
            ed.apply_theme(self.theme_dark)
        
        if self.theme_dark:
            # 1. Força a cor dark nos widgets nativos do TK (como o Menu principal)
            self.root.tk_setPalette(background="#1e1e1e", foreground="#d4d4d4",
                                    activeBackground="#37373d", activeForeground="#ffffff")
            
            # 2. Fundo da janela principal
            self.root.configure(bg="#1e1e1e")
            
            # 3. Estiliza os contêineres, barras e painéis para remover as bordas cinzas
            self.style.configure("TFrame", background="#1e1e1e")
            self.style.configure("TPanedwindow", background="#1e1e1e")
            self.style.configure("TLabel", background="#1e1e1e", foreground="#d4d4d4")
            self.style.configure("TButton", background="#333333", foreground="#d4d4d4")
            
            # (O resto da sua configuração dark continua igual)
            self.style.configure("Treeview", background="#252526", foreground="#d4d4d4", fieldbackground="#252526", borderwidth=0)
            self.style.configure("Treeview.Heading", background="#333333", foreground="#ffffff", borderwidth=1)
            self.style.map("Treeview", background=[("selected", "#37373d")], foreground=[("selected", "#ffffff")])
            
            self.problems_tree.tag_configure("error_row", foreground="#ff6b6b")
            self.problems_tree.tag_configure("warning_row", foreground="#dcdcaa")
            
            self.style.configure("TNotebook", background="#1e1e1e")
            self.style.configure("TNotebook.Tab", background="#333333", foreground="#ffffff")
            self.style.map("TNotebook.Tab", background=[("selected", "#007acc")])
            
            bg_log = "#1e1e1e"
            fg_log = "#d4d4d4"
        else:
            # 1. Volta os widgets nativos do TK para o modo claro
            self.root.tk_setPalette(background="#f0f0f0", foreground="#000000",
                                    activeBackground="#add6ff", activeForeground="#000000")
            
            # 2. Fundo da janela principal
            self.root.configure(bg="#f0f0f0")
            
            # 3. Retorna os contêineres e barras para o modo claro
            self.style.configure("TFrame", background="#f0f0f0")
            self.style.configure("TPanedwindow", background="#f0f0f0")
            self.style.configure("TLabel", background="#f0f0f0", foreground="#000000")
            self.style.configure("TButton", background="#e0e0e0", foreground="#000000")
            
            # (O resto da sua configuração light continua igual)
            self.style.configure("Treeview", background="#ffffff", foreground="#000000", fieldbackground="#ffffff", borderwidth=0)
            self.style.configure("Treeview.Heading", background="#f0f0f0", foreground="#000000", borderwidth=1)
            self.style.map("Treeview", background=[("selected", "#007acc")], foreground=[("selected", "#ffffff")])
            
            self.problems_tree.tag_configure("error_row", foreground="#cc0000")
            self.problems_tree.tag_configure("warning_row", foreground="#996600")
            
            self.style.configure("TNotebook", background="#f0f0f0")
            self.style.configure("TNotebook.Tab", background="#e0e0e0", foreground="#000000")
            self.style.map("TNotebook.Tab", background=[("selected", "#add6ff")])
            
            bg_log = "#ffffff"
            fg_log = "#000000"
        
        for tab in [self.msg_tab, self.preproc_tab, self.tokens_tab, self.ast_tab, 
                    self.semantic_tab, self.code_tab, self.optimizer_tab]:
            tab.config(bg=bg_log, fg=fg_log)
    
    def log(self, widget, msg, clear=False):
        widget.config(state='normal')
        if clear: widget.delete("1.0", "end")
        
        text = str(msg)
        pattern = re.compile(r'(linha\s*\d+|line\s*\d+)', re.IGNORECASE)
        
        start = 0
        for match in pattern.finditer(text):
            if match.start() > start:
                widget.insert("end", text[start:match.start()])
            
            link_text = match.group(0)
            lineno = int(re.search(r'\d+', link_text).group(0))
            tag_name = f"link_{lineno}_{widget.index('end')}"
            
            widget.insert("end", link_text, ("hyperlink", tag_name))
            widget.tag_bind(tag_name, "<Button-1>", lambda e, ln=lineno: self.jump_to_error(ln))
            start = match.end()
            
        if start < len(text):
            widget.insert("end", text[start:])
            
        widget.insert("end", "\n")
        widget.config(state='disabled')
        widget.see("end")

    def jump_to_error(self, lineno):
        editor = self.get_current_editor()
        if editor: editor.highlight_error(lineno)
        
    def on_log_double_click(self, event, text_widget):
        """Mapeamento Bidirecional: Clica num log e pula para o código-fonte."""
        try:
            # 1. Pega o texto exato da linha onde o usuário deu duplo-clique no painel de log
            idx = text_widget.index(f"@{event.x},{event.y}")
            line_str = text_widget.get(f"{idx.split('.')[0]}.0", f"{idx.split('.')[0]}.end")
            
            # 2. Regex inteligente para pescar o número da linha C correspondente
            # Captura: "[Ln: 10]" da AST, "linha 10" do Semântico, ou "..., 10)" dos Tokens do Lexer
            match = re.search(r'(?:Ln:|linha|line)\s*(\d+)|,\s*(\d+)\)$', line_str, re.IGNORECASE)
            
            if match:
                # O grupo 1 captura o padrão nomeado, o grupo 2 captura a tupla do Lexer
                target_line = int(match.group(1) or match.group(2))
                
                # 3. Mágica: Pula a IDE para o código-fonte C!
                self.jump_to_error(target_line)
        except Exception:
            pass

    def on_problem_double_click(self, event):
        """Pula para o arquivo e linha ao dar duplo-clique no painel de Problemas."""
        selected = self.problems_tree.selection()
        if not selected: return
        
        item = selected[0]
        file_path, lineno, desc = self.problems_tree.item(item, "values")
        
        if file_path and lineno and lineno != "?":
            ed = self.open_specific_file(file_path)
            if ed:
                # Pequeno atraso para a IDE desenhar a aba antes de piscar a linha
                # --- CORREÇÃO AQUI: Chama o highlight_warning se for aviso! ---
                if "⚠️" in desc:
                    self.root.after(50, lambda: ed.highlight_warning(int(lineno)))
                else:
                    self.root.after(50, lambda: ed.highlight_error(int(lineno)))

    def update_diagnostics(self, filepath, error_msg, lineno, warnings_list=[]):
        """Atualiza a tabela global de erros com Erros e Avisos."""
        # 1. Limpa os erros velhos associados a este arquivo
        for item in self.problems_tree.get_children():
            if self.problems_tree.item(item, "values")[0] == filepath:
                self.problems_tree.delete(item)
                
        errors_count = 0
        warns_count = 0

        # 2. Injeta o Erro Fatal (se houver)
        if error_msg:
            # Pega só a primeira frase do erro para a tabela ficar bonita e limpa
            clean_desc = error_msg.split('\n')[0].strip()
            if not lineno:
                match = re.search(r'(?:linha|line)\s+(\d+)', error_msg, re.IGNORECASE)
                lineno = match.group(1) if match else "?"
            self.problems_tree.insert("", "end", values=(filepath, lineno, f"❌ ERRO: {clean_desc}"), tags=("error_row",))
            errors_count = 1
            
        # 3. Injeta os Avisos (mesmo sem erros)
        for w in warnings_list:
            match = re.search(r'(?:linha|line)\s+(\d+)', w, re.IGNORECASE)
            w_line = match.group(1) if match else "?"
            self.problems_tree.insert("", "end", values=(filepath, w_line, f"⚠️ AVISO: {w}"), tags=("warning_row",))
            warns_count += 1

        # 4. Atualiza o ícone e a contagem da aba em tempo real
        if errors_count > 0:
            self.msg_notebook.tab(self.problems_frame, text=f"🔴 Problemas ({errors_count} Erro, {warns_count} Avisos)")
        elif warns_count > 0:
            self.msg_notebook.tab(self.problems_frame, text=f"⚠️ Problemas ({warns_count} Avisos)")
        else:
            self.msg_notebook.tab(self.problems_frame, text="✅ Problemas")
    
    def find_replace_dialog(self):
        editor = self.get_current_editor()
        if not editor: return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Localizar e Substituir")
        dialog.geometry("380x160")
        
        ttk.Label(dialog, text="Localizar:").grid(row=0, column=0, padx=5, pady=5)
        find_entry = ttk.Entry(dialog, width=30)
        find_entry.grid(row=0, column=1, padx=5, pady=5)
        find_entry.focus_set()

        ttk.Label(dialog, text="Substituir:").grid(row=1, column=0, padx=5, pady=5)
        replace_entry = ttk.Entry(dialog, width=30)
        replace_entry.grid(row=1, column=1, padx=5, pady=5)

        def find_next():
            target = find_entry.get()
            if target:
                text = editor.text_area
                idx = text.search(target, "insert", stopindex="end")
                if not idx:
                    idx = text.search(target, "1.0", stopindex="end")
                
                if idx:
                    text.tag_remove("sel", "1.0", "end")
                    end_idx = f"{idx}+{len(target)}c"
                    text.tag_add("sel", idx, end_idx)
                    text.mark_set("insert", end_idx)
                    text.see(idx)
                    text.focus()
                else:
                    messagebox.showinfo("Resultado", "Texto não encontrado.")

        def replace_current():
            try:
                sel_start = editor.text_area.index("sel.first")
                sel_end = editor.text_area.index("sel.last")
                selected_text = editor.text_area.get(sel_start, sel_end)
                
                if selected_text == find_entry.get():
                    editor.text_area.delete(sel_start, sel_end)
                    editor.text_area.insert(sel_start, replace_entry.get())
                    find_next()
            except tk.TclError:
                find_next()

        def replace_all():
            target = find_entry.get()
            replacement = replace_entry.get()
            if not target: return
            
            text = editor.text_area
            count = 0
            idx = "1.0"
            while True:
                idx = text.search(target, idx, stopindex="end")
                if not idx: break
                
                end_idx = f"{idx}+{len(target)}c"
                text.delete(idx, end_idx)
                text.insert(idx, replacement)
                
                idx = f"{idx}+{len(replacement)}c"
                count += 1
                
            messagebox.showinfo("Substituir Tudo", f"{count} ocorrências substituídas.")

        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Buscar Próx.", command=find_next).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Substituir", command=replace_current).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Subst. Tudo", command=replace_all).pack(side=tk.LEFT, padx=2)

    def find_references_current(self, event=None):
        ed = self.get_current_editor()
        if not ed: return "break"
        
        # 1. Pega a palavra exata sob o cursor (igual fazemos no Renomear)
        idx = ed.text_area.index("insert")
        line, col = map(int, idx.split('.'))
        line_text = ed.text_area.get(f"{line}.0", f"{line}.end")
        
        word_start = col
        while word_start > 0 and (line_text[word_start-1].isalnum() or line_text[word_start-1] == '_'):
            word_start -= 1
            
        word_end = col
        while word_end < len(line_text) and (line_text[word_end].isalnum() or line_text[word_end] == '_'):
            word_end += 1
            
        word = line_text[word_start:word_end].strip()
        
        if not word or not re.match(r'^[A-Za-z_]\w*$', word):
            messagebox.showinfo("Referências", "Posicione o cursor sobre uma variável ou função válida.", parent=self.root)
            return "break"
            
        # 2. Chama a interface visual de busca
        self.show_references_dialog(word)
        return "break"

    def show_references_dialog(self, target_word):
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Referências de: '{target_word}'")
        dialog.geometry("750x350")
        dialog.transient(self.root)
        
        bg_color = "#1e1e1e" if self.theme_dark else "#ffffff"
        fg_color = "#d4d4d4" if self.theme_dark else "#000000"
        dialog.configure(bg=bg_color)
        
        top_frame = tk.Frame(dialog, bg=bg_color)
        top_frame.pack(fill='x', padx=10, pady=5)
        tk.Label(top_frame, text=f"Procurando usos de '{target_word}'...", bg=bg_color, fg=fg_color, font=("Segoe UI", 10, "bold")).pack(side='left')
        
        tree = ttk.Treeview(dialog, columns=("File", "Line", "Code"), show="headings")
        tree.heading("File", text="Arquivo")
        tree.heading("Line", text="Linha")
        tree.heading("Code", text="Código Fonte")
        tree.column("File", width=150, anchor='w')
        tree.column("Line", width=50, anchor='center')
        tree.column("Code", width=500, anchor='w')
        tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        
        # 3. Motor de Busca Inteligente
        try:
            pre = Preprocessor()
        except NameError:
            pre = None
            
        pattern = re.compile(rf'\b{target_word}\b')
        count = 0
        
        for root_dir, dirs, files in os.walk(self.workspace_root):
            for file in files:
                if file.endswith((".c", ".cariri", ".h")):
                    path = os.path.join(root_dir, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            raw_content = f.read()
                            
                        # Limpa comentários usando a função do compilador (se disponível)
                        clean_content = pre.remove_comments(raw_content) if pre else raw_content
                        
                        raw_lines = raw_content.splitlines()
                        clean_lines = clean_content.splitlines()
                        
                        for i, clean_line in enumerate(clean_lines):
                            # Limpa as strings da linha para evitar falsos positivos
                            no_string_line = re.sub(r'".*?"|\'.*?\'', '', clean_line)
                            
                            # Se achar a palavra exata na linha "limpa", registra o achado!
                            if pattern.search(no_string_line):
                                rel_path = os.path.relpath(path, self.workspace_root)
                                code_text = raw_lines[i].strip()
                                tree.insert("", "end", values=(rel_path, i+1, code_text), tags=(path,))
                                count += 1
                    except Exception:
                        pass
                        
        tk.Label(top_frame, text=f"({count} referências encontradas)", bg=bg_color, fg="#569cd6" if self.theme_dark else "blue").pack(side='left', padx=10)
        
        # 4. Ação de Clique-Duplo para pular para o arquivo
        def on_double_click(e):
            selected = tree.selection()
            if not selected: return
            item = selected[0]
            values = tree.item(item, "values")
            tags = tree.item(item, "tags")
            
            if values and tags:
                path = tags[0]
                lineno = int(values[1])
                ed = self.open_specific_file(path)
                if ed:
                    self.root.after(50, lambda: ed.highlight_error(lineno))
                dialog.destroy()
                
        tree.bind("<Double-1>", on_double_click)

    def compile_code(self):
        editor = self.get_current_editor()
        if not editor: return
        
        self.clear_logs()
        self.asm_editor.delete_text()
        self.msg_notebook.select(self.msg_tab.master) 

        raw_code = editor.get_text()
        if not raw_code.strip():
            self.log(self.msg_tab, "Código fonte vazio.")
            return

        try:
            self.status_bar.config(text="Compilando...")
            self.root.update_idletasks()
            
            start_time = time.time() 
            
            # --- FIX: Garante que o compilador rode na pasta física do arquivo atual ---
            compile_dir = os.path.dirname(editor.filename) if editor.filename else editor.workspace_dir
            if compile_dir:
                os.chdir(compile_dir)
                if hasattr(Preprocessor, 'LOCAL_INCLUDE_DIRS'):
                    Preprocessor.LOCAL_INCLUDE_DIRS = [compile_dir, "./"]

            pre = Preprocessor()
            code = pre.preprocess(raw_code)
            self.log(self.preproc_tab, pre.get_log() + "\n--- Output ---\n" + code)

            tokens = list(tokenize(code))
            self.log(self.tokens_tab, "\n".join(map(str, tokens)))

            parser = Parser(tokens)
            ast = parser.parse_program()
            self.log(self.ast_tab, format_ast(ast))

            semantic = Semantic(ast)
            semantic.analyze()
            self.log(self.semantic_tab, semantic.get_log())
            
            self.update_outline(semantic, raw_code)

            gen = CodeGen()
            asm = gen.generate(ast)
            self.log(self.code_tab, asm)

            opt_asm, opt_log = optimize_with_log(asm.splitlines(True))
            self.log(self.optimizer_tab, "\n".join(opt_log))
            
            # --- FIX: A variável agora se chama final_asm_raw ---
            final_asm_raw = "".join(opt_asm)
            
            # =================================================================
            # MOTOR DE SOURCE MAP (LIVE DISASSEMBLY)
            # =================================================================
            clean_asm_lines = []
            self.c_to_asm_map = {} # Dicionário: Linha C -> [Linhas ASM]
            self.asm_to_c_map = {} # Dicionário: Linha ASM -> Linha C
            
            for i, line in enumerate(final_asm_raw.split('\n')):
                match = re.search(r';@ln:\s*(\d+)', line)
                if match:
                    c_line = int(match.group(1))
                    
                    # Remove o carimbo invisível do texto final
                    clean_line = line.replace(match.group(0), '').rstrip()
                    
                    if c_line not in self.c_to_asm_map:
                        self.c_to_asm_map[c_line] = []
                        
                    self.c_to_asm_map[c_line].append(i + 1)
                    self.asm_to_c_map[i + 1] = c_line
                    
                    clean_asm_lines.append(clean_line)
                else:
                    clean_asm_lines.append(line)
                    
            final_asm = "\n".join(clean_asm_lines)
            # =================================================================

            self.asm_editor.set_text(final_asm)
            
            end_time = time.time()
            total_time_ms = (end_time - start_time) * 1000 
            
            self.log(self.msg_tab, f"✅ Sucesso! Geração de Assembly CARIRI concluída.", clear=True)
            self.log(self.msg_tab, f"⏱️ Tempo total de Build: {total_time_ms:.2f} ms")
            
            idx = editor.text_area.index("insert")
            line, col = idx.split('.')
            self.status_bar.config(text=f"Pronto | Compilado em {total_time_ms:.0f}ms | Ln {line}, Col {int(col)+1} | Workspace CompSim | Ctrl+Space: Autocomplete")

        except Exception as e:
            self.log(self.msg_tab, f"❌ Erro: {str(e)}", clear=True)
            self.status_bar.config(text="Erro de Compilação")

    def check_unsaved_changes(self):
        checked_files = set() # Memória de arquivos já analisados
        
        for nb, ed in self._get_all_editors():
            # Ignora se o arquivo espelhado já foi salvo/ignorado no loop anterior
            if ed.filename and ed.filename in checked_files:
                continue
                
            if ed.is_modified():
                nb.select(ed)
                self.active_notebook = nb
                ans = messagebox.askyesnocancel("Alterações", f"Deseja salvar as alterações em {os.path.basename(ed.filename) if ed.filename else 'Sem Título'}?")
                if ans is True:
                    if not self.save_c_file(): return False
                    if ed.filename: checked_files.add(ed.filename)
                elif ans is False:
                    if ed.filename: checked_files.add(ed.filename)
                    continue
                else:
                    return False
        return True

    def new_file(self):
        self.add_editor_tab()

    def open_c_file(self):
        # ATUALIZADO: O filtro da janela do sistema operacional agora aceita .h e .asm
        path = filedialog.askopenfilename(filetypes=[("Arquivos CompSim", "*.c *.cariri *.h *.asm"), ("Todos", "*.*")])
        if path:
            if getattr(self, 'active_notebook', None) is None:
                self.active_notebook = self.editor_notebook
                
            # Verifica apenas no painel ativo se o arquivo já está aberto
            for tab_id in self.active_notebook.tabs():
                ed = self.root.nametowidget(tab_id)
                if ed.filename == path:
                    self.active_notebook.select(ed)
                    return
            
            self.current_dir = os.path.dirname(path)
            os.chdir(self.current_dir)
            self.refresh_file_explorer()
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            self.add_editor_tab(path, content)
            self.clear_logs()
    
    def save_c_file(self):
        editor = self.get_current_editor()
        if not editor: return False
        
        if editor.filename:
            text_content = editor.get_text()
            with open(editor.filename, 'w', encoding='utf-8') as f:
                f.write(text_content)
            editor.reset_modified()
            self.update_tab_title(editor)
            self.update_title()
            
            # Sincroniza outras instâncias do mesmo arquivo no Split View
            for nb, ed in self._get_all_editors():
                if ed != editor and ed.filename == editor.filename:
                    ed.set_text(text_content)
                    
            return True
        else:
            path = filedialog.asksaveasfilename(defaultextension=".c", filetypes=[("C", "*.c")])
            if path:
                editor.filename = path
                self.current_dir = os.path.dirname(path)
                os.chdir(self.current_dir)
                editor.workspace_dir = self.current_dir
                
                self.refresh_file_explorer()
                return self.save_c_file()
        return False
        

    def save_asm_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".asm")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.asm_editor.get_text())

    def clear_logs(self):
        for tab in [self.msg_tab, self.preproc_tab, self.tokens_tab, self.ast_tab, 
                    self.semantic_tab, self.code_tab, self.optimizer_tab]:
            self.log(tab, "", clear=True)

    def goto_line(self):
        line = simpledialog.askinteger("Ir para", "Linha:")
        if line: self.jump_to_error(line)

    def save_workspace(self):
        workspace_file = os.path.join(self.workspace_root, ".hist")
        state = {
            "theme_dark": self.theme_dark,
            "auto_save": self.auto_save_var.get(),
            "panels": {
                "explorer": self.show_explorer.get(),
                "outline": self.show_outline.get(),
                "asm": self.show_asm.get(),
                "logs": self.show_logs.get()
            },
            "split_active": str(self.editor_notebook_2) in self.editor_split_pane.panes(),
            "active_tab_1": self.editor_notebook.index(self.editor_notebook.select()) if self.editor_notebook.tabs() else 0,
            "active_tab_2": self.editor_notebook_2.index(self.editor_notebook_2.select()) if hasattr(self, 'editor_notebook_2') and self.editor_notebook_2.tabs() else 0,
            "editors_1": [],
            "editors_2": []
        }
        
        for tab_id in self.editor_notebook.tabs():
            ed = self.root.nametowidget(tab_id)
            if ed.filename: 
                state["editors_1"].append(ed.get_state())
                
        if hasattr(self, 'editor_notebook_2'):
            for tab_id in self.editor_notebook_2.tabs():
                ed = self.root.nametowidget(tab_id)
                if ed.filename: 
                    state["editors_2"].append(ed.get_state())
                
        try:
            with open(workspace_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
        except Exception:
            pass

    def load_workspace(self):
        workspace_file = os.path.join(self.workspace_root, ".hist")
        if not os.path.exists(workspace_file):
            self.add_editor_tab() 
            return
            
        try:
            with open(workspace_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                
            # Restaura Tema e Auto-Salvar
            if state.get("theme_dark", True) != self.theme_dark:
                self.toggle_theme()
            self.auto_save_var.set(state.get("auto_save", False)) 
                
            # Lê os Painéis, mas NÃO aplica ainda
            panels = state.get("panels", {})
            self.show_explorer.set(panels.get("explorer", True))
            self.show_outline.set(panels.get("outline", True))
            self.show_asm.set(panels.get("asm", True))
            self.show_logs.set(panels.get("logs", True))
            
            editors_1 = state.get("editors_1", [])
            editors_2 = state.get("editors_2", [])
            split_active = state.get("split_active", False)
            
            self.active_notebook = self.editor_notebook
            if not editors_1:
                self.add_editor_tab()
            else:
                for ed_data in editors_1:
                    path = ed_data.get("filename")
                    if path and os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        ed = self.add_editor_tab(path, content)
                        ed.restore_state(ed_data)
                        
            # Restaura o Split View
            if split_active or editors_2:
                if str(self.editor_notebook_2) not in self.editor_split_pane.panes():
                    self.editor_split_pane.add(self.editor_notebook_2, weight=1)
                
                self.active_notebook = self.editor_notebook_2
                
                # Limpa abas vazias criadas automaticamente
                for tab_id in self.editor_notebook_2.tabs():
                    self.root.nametowidget(tab_id).destroy()
                
                for ed_data in editors_2:
                    path = ed_data.get("filename")
                    if path and os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        ed = self.add_editor_tab(path, content)
                        ed.restore_state(ed_data)

            self.active_notebook = self.editor_notebook
            
            # Salvaguarda e seleção de abas ativas
            if not self.editor_notebook.tabs():
                self.add_editor_tab()
            else:
                active_tab_1 = state.get("active_tab_1", 0)
                if active_tab_1 < len(self.editor_notebook.tabs()):
                    self.editor_notebook.select(active_tab_1)
                
                if hasattr(self, 'editor_notebook_2') and self.editor_notebook_2.tabs():
                    active_tab_2 = state.get("active_tab_2", 0)
                    if active_tab_2 < len(self.editor_notebook_2.tabs()):
                        self.editor_notebook_2.select(active_tab_2)

            # --- NOVO: Sincronizar o Explorador com o arquivo ativo restaurado ---
            editor_ativo = self.get_current_editor()
            if editor_ativo and editor_ativo.filename:
                self.current_dir = os.path.dirname(editor_ativo.filename)
                self.refresh_file_explorer()
            # ---------------------------------------------------------------------
            
            def fix_logs_layout():
                self.toggle_panels()
                self.root.update_idletasks()
                
                # Arrasta o divisor manualmente para a posição correta (65% da tela)
                if self.show_logs.get() and str(self.bottom_frame) in self.main_pane.panes():
                    total_h = self.main_pane.winfo_height()
                    if total_h > 100:
                        self.main_pane.sashpos(0, int(total_h * 0.65))
                
            self.root.after(300, fix_logs_layout)
                
        except Exception:
            if not self.editor_notebook.tabs():
                self.add_editor_tab()
                
    def on_close(self):
        if hasattr(self, '_explorer_job'):
            self.root.after_cancel(self._explorer_job) # Cancela o loop de atualização
        if self.check_unsaved_changes(): 
            self.save_workspace()
            self.root.destroy()

    def open_specific_file(self, path):
        """Abre um arquivo focando nela no painel ativo (permite o mesmo arquivo em painéis divididos)."""
        if getattr(self, 'active_notebook', None) is None:
            self.active_notebook = self.editor_notebook

        # Verifica apenas nas abas do painel ativo
        for tab_id in self.active_notebook.tabs():
            ed = self.root.nametowidget(tab_id)
            if ed.filename == path:
                self.active_notebook.select(ed)
                return ed
                
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.add_editor_tab(path, content)
        return None

    def global_search_dialog(self, event=None):
        dialog = tk.Toplevel(self.root)
        dialog.title("Busca Global no Projeto")
        dialog.geometry("700x400")
        dialog.transient(self.root)
        
        bg_color = "#1e1e1e" if self.theme_dark else "#ffffff"
        fg_color = "#d4d4d4" if self.theme_dark else "#000000"
        dialog.configure(bg=bg_color)

        top_frame = tk.Frame(dialog, bg=bg_color)
        top_frame.pack(fill='x', padx=10, pady=10)

        tk.Label(top_frame, text="Buscar por:", bg=bg_color, fg=fg_color).pack(side='left')
        search_var = tk.StringVar()
        entry = ttk.Entry(top_frame, textvariable=search_var, width=40)
        entry.pack(side='left', padx=10)
        entry.focus_set()

        use_regex = tk.BooleanVar(value=False)
        ttk.Checkbutton(top_frame, text="Usar Regex", variable=use_regex).pack(side='left', padx=5)

        tree = ttk.Treeview(dialog, columns=("File", "Line", "Match"), show="headings")
        tree.heading("File", text="Arquivo")
        tree.heading("Line", text="Linha")
        tree.heading("Match", text="Ocorrência")
        tree.column("File", width=150, anchor='w')
        tree.column("Line", width=50, anchor='center')
        tree.column("Match", width=450, anchor='w')
        tree.pack(fill='both', expand=True, padx=10, pady=(0, 10))

        def do_search(e=None):
            for item in tree.get_children():
                tree.delete(item)
            
            term = search_var.get()
            if not term: return
            
            is_regex = use_regex.get()
            if is_regex:
                try:
                    pattern = re.compile(term)
                except re.error:
                    messagebox.showerror("Erro de Regex", "Expressão Regular inválida.", parent=dialog)
                    return

            for root_dir, dirs, files in os.walk(self.workspace_root):
                for file in files:
                    if file.endswith((".c", ".cariri", ".asm", ".h")):
                        path = os.path.join(root_dir, file)
                        try:
                            with open(path, 'r', encoding='utf-8') as f:
                                for i, line in enumerate(f):
                                    text = line.strip()
                                    found = False
                                    if is_regex:
                                        if pattern.search(text): found = True
                                    else:
                                        if term in text: found = True
                                        
                                    if found:
                                        rel_path = os.path.relpath(path, self.workspace_root)
                                        tree.insert("", "end", values=(rel_path, i+1, text), tags=(path,))
                        except Exception:
                            pass

        ttk.Button(top_frame, text="Buscar", command=do_search).pack(side='left')
        entry.bind("<Return>", do_search)

        def on_double_click(e):
            selected = tree.selection()
            if not selected: return
            item = selected[0]
            values = tree.item(item, "values")
            tags = tree.item(item, "tags")
            
            if values and tags:
                path = tags[0]
                lineno = int(values[1])
                
                ed = self.open_specific_file(path)
                if ed:
                    self.root.after(50, lambda: ed.highlight_error(lineno))
                dialog.destroy()

        tree.bind("<Double-1>", on_double_click)

if __name__ == '__main__':
    root = tk.Tk()
    app = CaririIDE(root)
    root.mainloop()
