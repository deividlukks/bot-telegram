"""
Teclados customizados para o Finance Bot
"""
from typing import List, Optional

from telegram import (
    ReplyKeyboardMarkup, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    KeyboardButton
)

from config import Emojis, PaymentMethods
from models import TransactionType, InvestmentType


class Keyboards:
    """Classe para gerar teclados do bot"""
    
    @staticmethod
    def main_menu() -> ReplyKeyboardMarkup:
        """Teclado do menu principal"""
        keyboard = [
            ['💰 Finanças Pessoais', '📈 Investimentos'],
            ['💹 Trading', '📊 Relatórios'],
            ['⚙️ Configurações', '❓ Ajuda']
        ]
        return ReplyKeyboardMarkup(
            keyboard, 
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    @staticmethod
    def finance_menu() -> ReplyKeyboardMarkup:
        """Teclado do menu de finanças"""
        keyboard = [
            ['➕ Novo Lançamento', '📋 Ver Lançamentos'],
            ['📊 Resumo Financeiro', '🏷️ Categorias'],
            ['📈 Análise Detalhada', '💡 Dicas'],
            [f'{Emojis.BACK} Menu Principal']
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    @staticmethod
    def investment_menu() -> ReplyKeyboardMarkup:
        """Teclado do menu de investimentos"""
        keyboard = [
            ['📰 Notícias', '💼 Minha Carteira'],
            ['➕ Comprar', '➖ Vender'],
            ['💵 Dividendos', '🎯 Oportunidades'],
            ['📊 Análise', '🔄 Rebalancear'],
            [f'{Emojis.BACK} Menu Principal']
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    @staticmethod
    def settings_menu() -> ReplyKeyboardMarkup:
        """Teclado do menu de configurações"""
        keyboard = [
            ['👤 Perfil', '🔔 Notificações'],
            ['🏷️ Categorias', '📤 Exportar Dados'],
            ['🎯 Metas', '🌍 Timezone'],
            [f'{Emojis.BACK} Menu Principal']
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )
    
    @staticmethod
    def transaction_type() -> InlineKeyboardMarkup:
        """Teclado inline para tipo de transação"""
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{Emojis.MONEY_IN} Receita", 
                    callback_data="transaction_income"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{Emojis.MONEY_OUT} Despesa", 
                    callback_data="transaction_expense"
                )
            ],
            [
                InlineKeyboardButton(
                    f"{Emojis.ERROR} Cancelar", 
                    callback_data="cancel"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def payment_methods(
        transaction_type: TransactionType
    ) -> ReplyKeyboardMarkup:
        """Teclado para métodos de pagamento/recebimento"""
        if transaction_type == TransactionType.EXPENSE:
            methods = PaymentMethods.get_expense_methods()
        else:
            methods = PaymentMethods.get_income_methods()
        
        keyboard = [[method] for method in methods]
        keyboard.append([f'{Emojis.ERROR} Cancelar'])
        
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    
    @staticmethod
    def categories(
        categories: List,
        allow_new: bool = True
    ) -> ReplyKeyboardMarkup:
        """Teclado para seleção de categorias"""
        keyboard = []
        
        # Adicionar categorias em pares
        for i in range(0, len(categories), 2):
            row = [categories[i].name]
            if i + 1 < len(categories):
                row.append(categories[i + 1].name)
            keyboard.append(row)
        
        if allow_new:
            keyboard.append(['➕ Nova Categoria'])
        
        keyboard.append([f'{Emojis.ERROR} Cancelar'])
        
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    
    @staticmethod
    def date_selection() -> ReplyKeyboardMarkup:
        """Teclado para seleção de data"""
        keyboard = [
            ['📅 Hoje', '📅 Ontem'],
            ['📅 Esta Semana', '📅 Este Mês'],
            ['✏️ Digitar Data'],
            [f'{Emojis.ERROR} Cancelar']
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    
    @staticmethod
    def investment_types() -> ReplyKeyboardMarkup:
        """Teclado para tipos de investimento"""
        keyboard = [
            ['📊 Ações', '🏠 FIIs'],
            ['🪙 Criptomoedas', '📈 ETFs'],
            ['💰 Renda Fixa', '🔄 Outros'],
            [f'{Emojis.ERROR} Cancelar']
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    
    @staticmethod
    def yes_no(
        yes_text: str = "✅ Sim",
        no_text: str = "❌ Não"
    ) -> InlineKeyboardMarkup:
        """Teclado inline sim/não"""
        keyboard = [
            [
                InlineKeyboardButton(yes_text, callback_data="yes"),
                InlineKeyboardButton(no_text, callback_data="no")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def pagination(
        current_page: int,
        total_pages: int,
        callback_prefix: str
    ) -> InlineKeyboardMarkup:
        """Teclado inline para paginação"""
        buttons = []
        
        # Botão anterior
        if current_page > 1:
            buttons.append(
                InlineKeyboardButton(
                    f"{Emojis.PREVIOUS} Anterior",
                    callback_data=f"{callback_prefix}_page_{current_page - 1}"
                )
            )
        
        # Informação da página
        buttons.append(
            InlineKeyboardButton(
                f"{current_page}/{total_pages}",
                callback_data="noop"
            )
        )
        
        # Botão próximo
        if current_page < total_pages:
            buttons.append(
                InlineKeyboardButton(
                    f"Próximo {Emojis.NEXT}",
                    callback_data=f"{callback_prefix}_page_{current_page + 1}"
                )
            )
        
        return InlineKeyboardMarkup([buttons])
    
    @staticmethod
    def transaction_actions(
        transaction_id: int
    ) -> InlineKeyboardMarkup:
        """Teclado inline para ações em transação"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "✏️ Editar",
                    callback_data=f"edit_transaction_{transaction_id}"
                ),
                InlineKeyboardButton(
                    "🗑️ Excluir",
                    callback_data=f"delete_transaction_{transaction_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📋 Detalhes",
                    callback_data=f"details_transaction_{transaction_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def investment_actions(
        investment_id: int
    ) -> InlineKeyboardMarkup:
        """Teclado inline para ações em investimento"""
        keyboard = [
            [
                InlineKeyboardButton(
                    "➕ Comprar Mais",
                    callback_data=f"buy_more_{investment_id}"
                ),
                InlineKeyboardButton(
                    "➖ Vender",
                    callback_data=f"sell_{investment_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 Análise",
                    callback_data=f"analyze_{investment_id}"
                ),
                InlineKeyboardButton(
                    "📋 Histórico",
                    callback_data=f"history_{investment_id}"
                )
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def cancel_only() -> ReplyKeyboardMarkup:
        """Teclado apenas com botão cancelar"""
        keyboard = [[f'{Emojis.ERROR} Cancelar']]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True
        )
    
    @staticmethod
    def remove() -> ReplyKeyboardMarkup:
        """Remove o teclado customizado"""
        return ReplyKeyboardMarkup(
            [[]],
            resize_keyboard=True,
            one_time_keyboard=True
        )