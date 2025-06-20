"""
Módulo de serviços expandido - Versão Simplificada e Corrigida
"""

# Importar apenas os novos serviços da pasta services/
# Os serviços originais continuam sendo importados diretamente de services.py

try:
    from .report_service import (
        ReportService, 
        ReportFormatter, 
        PeriodUtils,
        generate_monthly_report,
        get_quick_insights,
        clear_user_cache,
        get_formatted_monthly_report
    )
    print("✅ Serviços de relatório importados com sucesso")
except ImportError as e:
    print(f"⚠️ Erro ao importar serviços de relatório: {e}")
    # Se não conseguir importar, definir como None
    ReportService = None
    ReportFormatter = None
    PeriodUtils = None
    generate_monthly_report = None
    get_quick_insights = None
    clear_user_cache = None
    get_formatted_monthly_report = None

# Remover import do user_service por enquanto para evitar conflitos
# try:
#     from .user_service import UserService as AdvancedUserService
# except ImportError:
#     AdvancedUserService = None

__all__ = [
    'ReportService',
    'ReportFormatter', 
    'PeriodUtils',
    'generate_monthly_report',
    'get_quick_insights',
    'clear_user_cache',
    'get_formatted_monthly_report'
]