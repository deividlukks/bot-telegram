#!/usr/bin/env python3
"""
Script para configurar o banco de dados
"""
import sys
from pathlib import Path

# 1. ADICIONE ESTA LINHA PARA IMPORTAR A FUNÇÃO text
from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent))

from database import init_database, db
from models import DEFAULT_CATEGORIES

def main():
    print("🔧 Configurando banco de dados...")
    
    try:
        # Criar tabelas
        init_database()
        print("✅ Tabelas criadas com sucesso!")
        
        # Verificar conexão
        with db.get_session() as session:
            # 2. ENVOLVA O COMANDO SQL COM a FUNÇÃO text()
            result = session.execute(text("SELECT 1"))
            if result.scalar() == 1:
                print("✅ Conexão com banco testada!")
        
        print("\n🎉 Banco de dados configurado com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()