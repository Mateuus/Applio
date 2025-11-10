#!/usr/bin/env python3
"""
Script para criar alias python_multipart -> multipart
Necessário porque python-multipart instala como 'multipart' mas Gradio espera 'python_multipart'
"""

import os
import sys
from pathlib import Path

def create_multipart_alias():
    """Cria alias python_multipart para compatibilidade"""
    # Encontrar site-packages
    site_packages = None
    for path in sys.path:
        if 'site-packages' in path and '.venv' in path:
            site_packages = Path(path)
            break
    
    if not site_packages:
        print("❌ Não foi possível encontrar site-packages do venv")
        return False
    
    # Verificar se multipart está instalado
    multipart_path = site_packages / 'multipart'
    if not multipart_path.exists():
        print("❌ Módulo multipart não encontrado. Instale python-multipart primeiro.")
        return False
    
    # Criar diretório python_multipart
    python_multipart_dir = site_packages / 'python_multipart'
    python_multipart_dir.mkdir(exist_ok=True)
    
    # Criar __init__.py com alias
    init_file = python_multipart_dir / '__init__.py'
    init_content = '''# Alias para compatibilidade com python_multipart
# python-multipart instala como 'multipart' mas Gradio espera 'python_multipart'
import sys
from multipart import multipart as multipart_module
sys.modules['python_multipart'] = sys.modules['multipart']
sys.modules['python_multipart.multipart'] = multipart_module
'''
    
    with open(init_file, 'w') as f:
        f.write(init_content)
    
    print(f"✅ Alias python_multipart criado em {python_multipart_dir}")
    return True

if __name__ == '__main__':
    if create_multipart_alias():
        print("✅ Alias criado com sucesso!")
        sys.exit(0)
    else:
        print("❌ Falha ao criar alias")
        sys.exit(1)

