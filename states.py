"""
Estados da conversa para o ConversationHandler
"""
from enum import IntEnum, auto


class ConversationStates(IntEnum):
    """Estados da conversa principal"""
    # Menus principais
    MAIN_MENU = auto()
    FINANCE_MENU = auto()
    INVESTMENT_MENU = auto()
    TRADING_MENU = auto()
    SETTINGS_MENU = auto()
    
    # Estados de transação
    TRANSACTION_TYPE = auto()
    TRANSACTION_AMOUNT = auto()
    TRANSACTION_DESCRIPTION = auto()
    TRANSACTION_PAYMENT_METHOD = auto()
    TRANSACTION_DATE = auto()
    TRANSACTION_CATEGORY = auto()
    TRANSACTION_CONFIRM = auto()
    
    # Estados de categoria
    CATEGORY_TYPE = auto()
    CATEGORY_NAME = auto()
    CATEGORY_ICON = auto()
    CATEGORY_CONFIRM = auto()
    
    # Estados de investimento
    INVESTMENT_ACTION = auto()
    INVESTMENT_TYPE = auto()
    INVESTMENT_TICKER = auto()
    INVESTMENT_QUANTITY = auto()
    INVESTMENT_PRICE = auto()
    INVESTMENT_DATE = auto()
    INVESTMENT_BROKER = auto()
    INVESTMENT_CONFIRM = auto()
    
    # Estados de venda
    SELL_SELECT = auto()
    SELL_QUANTITY = auto()
    SELL_PRICE = auto()
    SELL_CONFIRM = auto()
    
    # Estados de configuração
    SETTINGS_PROFILE = auto()
    SETTINGS_NOTIFICATIONS = auto()
    SETTINGS_TIMEZONE = auto()
    SETTINGS_GOALS = auto()
    
    # Estados de relatório
    REPORT_TYPE = auto()
    REPORT_PERIOD = auto()
    REPORT_FILTERS = auto()
    
    # Estados de exportação
    EXPORT_TYPE = auto()
    EXPORT_PERIOD = auto()
    EXPORT_FORMAT = auto()
    
    # Estados especiais
    WAITING_CONFIRMATION = auto()
    SHOWING_HELP = auto()
    ERROR_STATE = auto()


class CallbackActions:
    """Prefixos para callback_data"""
    # Transações
    TRANSACTION_TYPE = "transaction_"
    EDIT_TRANSACTION = "edit_transaction_"
    DELETE_TRANSACTION = "delete_transaction_"
    DETAILS_TRANSACTION = "details_transaction_"
    
    # Investimentos
    BUY_MORE = "buy_more_"
    SELL_INVESTMENT = "sell_"
    ANALYZE_INVESTMENT = "analyze_"
    HISTORY_INVESTMENT = "history_"
    
    # Categorias
    SELECT_CATEGORY = "category_"
    EDIT_CATEGORY = "edit_category_"
    DELETE_CATEGORY = "delete_category_"
    
    # Paginação
    PAGE = "_page_"
    
    # Confirmações
    CONFIRM_YES = "yes"
    CONFIRM_NO = "no"
    
    # Gerais
    CANCEL = "cancel"
    BACK = "back"
    NOOP = "noop"  # No operation


# Mapeamento de tipos de investimento
INVESTMENT_TYPE_MAP = {
    '📊 Ações': 'stock',
    '🏠 FIIs': 'fii',
    '🪙 Criptomoedas': 'crypto',
    '📈 ETFs': 'etf',
    '💰 Renda Fixa': 'fixed',
    '🔄 Outros': 'other'
}

# Mapeamento reverso
INVESTMENT_TYPE_DISPLAY = {v: k for k, v in INVESTMENT_TYPE_MAP.items()}