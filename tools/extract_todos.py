#!/usr/bin/env python3
import os
import re
from pathlib import Path

def should_ignore(path, ignore_patterns):
    """Verifica se o caminho deve ser ignorado"""
    path_str = str(path)
    
    # Padrões para ignorar
    patterns = [
        r'\.venv',
        r'\.git',
        r'__pycache__',
        r'\.terraform',
        r'extract_todos\.py',
        r'INFRA_TODO\.md',
        r'node_modules',
        r'\.vscode',
        r'\.idea'
    ]
    
    patterns.extend(ignore_patterns)
    
    for pattern in patterns:
        if re.search(pattern, path_str):
            return True
    return False

def extract_todos(root_dir, additional_ignore=None):
    if additional_ignore is None:
        additional_ignore = []
        
    todo_pattern = re.compile(r'(TODO|FIXME|HACK|NOTE|OPTIMIZE|XXX):?\s*(.+)')
    todos = []
    
    for file_path in Path(root_dir).rglob('*'):
        if should_ignore(file_path, additional_ignore):
            continue
            
        if file_path.is_file() and file_path.suffix in [
            '.tf', '.yml', '.yaml', '.json', '.py', '.sh', '.md', 
            '.txt', '.tfvars', '.hcl', '.conf', '.config'
        ]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        match = todo_pattern.search(line)
                        if match:
                            todos.append({
                                'type': match.group(1),
                                'description': match.group(2).strip(),
                                'file': str(file_path.relative_to(root_dir)),
                                'line': i
                            })
            except (UnicodeDecodeError, PermissionError) as e:
                print(f"Aviso: Não foi possível ler {file_path}: {e}")
            except Exception as e:
                print(f"Erro ao ler {file_path}: {e}")
    
    return todos

def generate_markdown(todos, output_file='INFRA_TODO.md'):
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Lista de Afazeres - Infraestrutura\n\n")
        f.write("> Lista gerada automaticamente a partir de comentários no código\n\n")
        
        # Agrupar por tipo
        for todo_type in ['TODO', 'FIXME', 'HACK', 'NOTE', 'OPTIMIZE', 'XXX']:
            type_todos = [t for t in todos if t['type'] == todo_type]
            if type_todos:
                f.write(f"## {todo_type} ({len(type_todos)})\n\n")
                for todo in type_todos:
                    f.write(f"- [ ] **{todo['description']}**\n")
                    f.write(f"  - `{todo['file']}:{todo['line']}`\n\n")
        
        # Estatísticas
        f.write("## 📊 Estatísticas\n\n")
        f.write(f"**Total de itens:** {len(todos)}\n\n")
        for todo_type in ['TODO', 'FIXME', 'HACK', 'NOTE', 'OPTIMIZE', 'XXX']:
            count = len([t for t in todos if t['type'] == todo_type])
            if count > 0:
                f.write(f"- **{todo_type}:** {count}\n")

if __name__ == "__main__":
    print("Extraindo TODOs da infraestrutura...")
    
    # Padrões adicionais para ignorar (personalizável)
    additional_ignore = [
        r'\.env',
        r'secret',
        r'password',
        # adicione outros padrões conforme necessário
    ]
    
    todos = extract_todos('.', additional_ignore)
    generate_markdown(todos)
    print(f"✅ Encontrados {len(todos)} itens. Lista salva em INFRA_TODO.md")