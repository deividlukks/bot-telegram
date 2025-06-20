"""
Módulo de handlers do Finance Bot
"""

# Importar todos os handlers para facilitar o acesso
from .main import (
    start_command,
    main_menu,
    main_menu_handler,
    help_command,
    cancel_command,
    error_handler
)

from .finance import (
    finance_menu,
    finance_menu_handler,
    start_new_transaction,
    transaction_type_callback,
    transaction_amount_handler,
    transaction_description_handler,
    transaction_payment_method_handler,
    transaction_date_handler,
    transaction_category_handler,
    category_name_handler,
    show_transactions,
    show_financial_summary,
    show_categories,
    show_detailed_analysis,
    show_financial_tips
)

from .investment import (
    investment_menu,
    investment_menu_handler,
    start_buy_investment,
    investment_type_handler,
    investment_ticker_handler,
    investment_quantity_handler,
    investment_price_handler,
    investment_confirm_handler,
    start_sell_investment,
    show_portfolio,
    show_market_news,
    show_dividends,
    show_opportunities,
    show_portfolio_analysis,
    show_rebalancing
)

from .settings import (
    settings_menu,
    settings_menu_handler,
    show_profile,
    show_notifications_settings,
    manage_categories,
    export_data,
    show_goals,
    show_timezone_settings,
    settings_callback_handler
)

__all__ = [
    # Main handlers
    'start_command',
    'main_menu',
    'main_menu_handler',
    'help_command',
    'cancel_command',
    'error_handler',
    
    # Finance handlers
    'finance_menu',
    'finance_menu_handler',
    'start_new_transaction',
    'transaction_type_callback',
    'transaction_amount_handler',
    'transaction_description_handler',
    'transaction_payment_method_handler',
    'transaction_date_handler',
    'transaction_category_handler',
    'category_name_handler',
    'show_transactions',
    'show_financial_summary',
    'show_categories',
    'show_detailed_analysis',
    'show_financial_tips',
    
    # Investment handlers
    'investment_menu',
    'investment_menu_handler',
    'start_buy_investment',
    'investment_type_handler',
    'investment_ticker_handler',
    'investment_quantity_handler',
    'investment_price_handler',
    'investment_confirm_handler',
    'start_sell_investment',
    'show_portfolio',
    'show_market_news',
    'show_dividends',
    'show_opportunities',
    'show_portfolio_analysis',
    'show_rebalancing',
    
    # Settings handlers
    'settings_menu',
    'settings_menu_handler',
    'show_profile',
    'show_notifications_settings',
    'manage_categories',
    'export_data',
    'show_goals',
    'show_timezone_settings',
    'settings_callback_handler'
]