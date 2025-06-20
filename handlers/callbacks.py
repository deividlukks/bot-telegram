"""
Handlers para callbacks inline do Finance Bot
Centraliza todos os handlers de callback_query para melhor organização
"""
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import Config, Messages, Emojis
from database import db
from keyboards import Keyboards
from models import User, Transaction, Investment, Category, InvestorProfile
from services import UserService, TransactionService, InvestmentService, CategoryService
from states import ConversationStates, CallbackActions
from utils import (
    get_user_from_update, format_currency, parse_amount,
    escape_markdown, format_percentage
)

logger = logging.getLogger(__name__)


class CallbackRouter:
    """Roteador para callbacks baseado em prefixos"""
    
    @staticmethod
    async def route_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """
        Roteia callbacks para os handlers apropriados baseado no prefixo
        """
        query = update.callback_query
        if not query or not query.data:
            return ConversationStates.MAIN_MENU
        
        await query.answer()
        data = query.data
        
        # Mapear prefixos para handlers
        routes = {
            # Transações
            CallbackActions.TRANSACTION_TYPE: transaction_type_callback,
            CallbackActions.EDIT_TRANSACTION: edit_transaction_callback,
            CallbackActions.DELETE_TRANSACTION: delete_transaction_callback,
            CallbackActions.DETAILS_TRANSACTION: transaction_details_callback,
            
            # Investimentos
            CallbackActions.BUY_MORE: buy_more_investment_callback,
            CallbackActions.SELL_INVESTMENT: sell_investment_callback,
            CallbackActions.ANALYZE_INVESTMENT: analyze_investment_callback,
            CallbackActions.HISTORY_INVESTMENT: investment_history_callback,
            
            # Categorias
            CallbackActions.SELECT_CATEGORY: select_category_callback,
            CallbackActions.EDIT_CATEGORY: edit_category_callback,
            CallbackActions.DELETE_CATEGORY: delete_category_callback,
            
            # Configurações
            "settings_": settings_callback,
            "profile_": profile_callback,
            "notifications_": notifications_callback,
            "export_": export_callback,
            "tz_": timezone_callback,
            
            # Paginação
            "_page_": pagination_callback,
            
            # Confirmações gerais
            CallbackActions.CONFIRM_YES: confirm_yes_callback,
            CallbackActions.CONFIRM_NO: confirm_no_callback,
            
            # Ações especiais
            CallbackActions.CANCEL: cancel_callback,
            CallbackActions.BACK: back_callback,
            CallbackActions.NOOP: noop_callback
        }
        
        # Encontrar o handler apropriado
        for prefix, handler in routes.items():
            if data.startswith(prefix):
                try:
                    return await handler(update, context)
                except Exception as e:
                    logger.error(f"Erro no callback {data}: {e}")
                    await query.edit_message_text(
                        Messages.ERROR_GENERIC,
                        reply_markup=Keyboards.main_menu()
                    )
                    return ConversationStates.MAIN_MENU
        
        # Callback não reconhecido
        logger.warning(f"Callback não reconhecido: {data}")
        await query.edit_message_text(
            "❌ Ação não reconhecida.",
            reply_markup=Keyboards.main_menu()
        )
        return ConversationStates.MAIN_MENU


# ==================== CALLBACKS DE TRANSAÇÃO ====================

async def transaction_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa seleção do tipo de transação"""
    query = update.callback_query
    data = query.data
    
    if data == "transaction_income":
        from models import TransactionType
        context.user_data['transaction_type'] = TransactionType.INCOME
        type_name = "Receita"
    elif data == "transaction_expense":
        from models import TransactionType
        context.user_data['transaction_type'] = TransactionType.EXPENSE
        type_name = "Despesa"
    else:
        await query.edit_message_text(Messages.CANCELLED)
        return ConversationStates.FINANCE_MENU
    
    await query.edit_message_text(
        f"*Nova {type_name}*\n\n{Messages.ASK_AMOUNT}",
        parse_mode='Markdown'
    )
    
    return ConversationStates.TRANSACTION_AMOUNT


async def edit_transaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia edição de transação"""
    query = update.callback_query
    transaction_id = int(query.data.split('_')[2])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user.id
            ).first()
            
            if not transaction:
                await query.edit_message_text("❌ Transação não encontrada.")
                return ConversationStates.FINANCE_MENU
            
            # Armazenar ID da transação para edição
            context.user_data['editing_transaction_id'] = transaction_id
            context.user_data['transaction_type'] = transaction.type
            
            # Mostrar dados atuais
            message = f"""
*✏️ Editando Transação*

*Dados Atuais:*
• Valor: {format_currency(transaction.amount)}
• Descrição: {transaction.description}
• Categoria: {transaction.category.name}
• Data: {transaction.date.strftime('%d/%m/%Y')}
• Método: {transaction.payment_method}

Digite o novo valor (ou pressione cancelar):
"""
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
                ]])
            )
            
            return ConversationStates.TRANSACTION_AMOUNT
            
    except Exception as e:
        logger.error(f"Erro ao editar transação: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
        return ConversationStates.FINANCE_MENU


async def delete_transaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma exclusão de transação"""
    query = update.callback_query
    transaction_id = int(query.data.split('_')[2])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user.id
            ).first()
            
            if not transaction:
                await query.edit_message_text("❌ Transação não encontrada.")
                return ConversationStates.FINANCE_MENU
            
            # Confirmar exclusão
            keyboard = [
                [
                    InlineKeyboardButton("✅ Sim, excluir", callback_data=f"confirm_delete_transaction_{transaction_id}"),
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
                ]
            ]
            
            message = f"""
*🗑️ Confirmar Exclusão*

Deseja realmente excluir esta transação?

• {transaction.description}
• {format_currency(transaction.amount)}
• {transaction.date.strftime('%d/%m/%Y')}

Esta ação não pode ser desfeita.
"""
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.WAITING_CONFIRMATION
            
    except Exception as e:
        logger.error(f"Erro ao excluir transação: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
        return ConversationStates.FINANCE_MENU


async def transaction_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mostra detalhes completos da transação"""
    query = update.callback_query
    transaction_id = int(query.data.split('_')[2])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user.id
            ).first()
            
            if not transaction:
                await query.edit_message_text("❌ Transação não encontrada.")
                return ConversationStates.FINANCE_MENU
            
            # Emoji baseado no tipo
            emoji = Emojis.MONEY_IN if transaction.type.value == 'income' else Emojis.MONEY_OUT
            signal = "+" if transaction.type.value == 'income' else "-"
            
            message = f"""
*📋 Detalhes da Transação*

{emoji} *{transaction.description}*

*💰 Valor:* {signal}{format_currency(transaction.amount)}
*🏷️ Categoria:* {transaction.category.name}
*📅 Data:* {transaction.date.strftime('%d/%m/%Y às %H:%M')}
*💳 Método:* {transaction.payment_method}
*📝 Tipo:* {'Receita' if transaction.type.value == 'income' else 'Despesa'}

*📊 Informações Técnicas:*
• ID: {transaction.id}
• Criado em: {transaction.created_at.strftime('%d/%m/%Y %H:%M')}
• Atualizado em: {transaction.updated_at.strftime('%d/%m/%Y %H:%M')}
"""
            
            if transaction.notes:
                message += f"\n*📝 Observações:*\n{transaction.notes}"
            
            if transaction.tags:
                message += f"\n*🏷️ Tags:* {transaction.tags}"
            
            keyboard = [
                [
                    InlineKeyboardButton("✏️ Editar", callback_data=f"edit_transaction_{transaction_id}"),
                    InlineKeyboardButton("🗑️ Excluir", callback_data=f"delete_transaction_{transaction_id}")
                ],
                [InlineKeyboardButton("🔙 Voltar", callback_data="back")]
            ]
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.FINANCE_MENU
            
    except Exception as e:
        logger.error(f"Erro ao mostrar detalhes: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
        return ConversationStates.FINANCE_MENU


# ==================== CALLBACKS DE INVESTIMENTO ====================

async def buy_more_investment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia compra adicional de investimento existente"""
    query = update.callback_query
    investment_id = int(query.data.split('_')[2])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            investment = session.query(Investment).filter(
                Investment.id == investment_id,
                Investment.user_id == user.id
            ).first()
            
            if not investment:
                await query.edit_message_text("❌ Investimento não encontrado.")
                return ConversationStates.INVESTMENT_MENU
            
            # Armazenar dados do investimento
            context.user_data['buying_more_investment_id'] = investment_id
            context.user_data['ticker'] = investment.ticker
            context.user_data['investment_type'] = investment.type.value
            
            message = f"""
*➕ Comprar Mais {investment.ticker}*

*Posição Atual:*
• Quantidade: {investment.current_quantity:.4f}
• Preço Médio: {format_currency(investment.avg_price)}
• Total Investido: {format_currency(investment.total_invested)}

Digite a quantidade adicional que deseja comprar:
"""
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
                ]])
            )
            
            return ConversationStates.INVESTMENT_QUANTITY
            
    except Exception as e:
        logger.error(f"Erro ao comprar mais investimento: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
        return ConversationStates.INVESTMENT_MENU


async def sell_investment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia venda de investimento"""
    query = update.callback_query
    investment_id = int(query.data.split('_')[1])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            investment = session.query(Investment).filter(
                Investment.id == investment_id,
                Investment.user_id == user.id
            ).first()
            
            if not investment or not investment.is_active:
                await query.edit_message_text("❌ Investimento não encontrado ou já vendido.")
                return ConversationStates.INVESTMENT_MENU
            
            # Armazenar dados para venda
            context.user_data['selling_investment_id'] = investment_id
            
            message = f"""
*➖ Vender {investment.ticker}*

*Posição Atual:*
• Quantidade Disponível: {investment.current_quantity:.4f}
• Preço Médio de Compra: {format_currency(investment.avg_price)}
• Total Investido: {format_currency(investment.total_invested)}

Digite a quantidade que deseja vender:
_(Max: {investment.current_quantity:.4f})_
"""
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Cancelar", callback_data="cancel")
                ]])
            )
            
            return ConversationStates.SELL_QUANTITY
            
    except Exception as e:
        logger.error(f"Erro ao vender investimento: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
        return ConversationStates.INVESTMENT_MENU


async def analyze_investment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mostra análise detalhada do investimento"""
    query = update.callback_query
    investment_id = int(query.data.split('_')[1])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            investment = session.query(Investment).filter(
                Investment.id == investment_id,
                Investment.user_id == user.id
            ).first()
            
            if not investment:
                await query.edit_message_text("❌ Investimento não encontrado.")
                return ConversationStates.INVESTMENT_MENU
            
            # Simular preço atual (em produção, buscar de API)
            import random
            variation = random.uniform(-10, 15) / 100
            current_price = float(investment.avg_price) * (1 + variation)
            current_value = float(investment.current_quantity) * current_price
            
            profit = current_value - float(investment.total_invested)
            profit_pct = (profit / float(investment.total_invested) * 100) if investment.total_invested > 0 else 0
            
            # Emoji baseado no resultado
            if profit >= 0:
                profit_emoji = "📈"
                status = "Lucro"
            else:
                profit_emoji = "📉"
                status = "Prejuízo"
            
            # Calcular dias investido
            days_invested = (datetime.now() - investment.purchase_date).days
            
            message = f"""
*📊 Análise - {investment.ticker}*

*💰 Performance Financeira:*
• Valor Investido: {format_currency(investment.total_invested)}
• Valor Atual: {format_currency(current_value)}
• {status}: {profit_emoji} {format_currency(abs(profit))} ({profit_pct:+.2f}%)

*📈 Detalhes da Posição:*
• Quantidade: {investment.current_quantity:.4f}
• Preço Médio: {format_currency(investment.avg_price)}
• Preço Atual: {format_currency(current_price)}

*⏰ Tempo de Investimento:*
• Data de Compra: {investment.purchase_date.strftime('%d/%m/%Y')}
• Dias Investido: {days_invested}
• Tipo: {investment.type.value.upper()}

*📊 Indicadores:*
• Variação desde compra: {profit_pct:+.2f}%
• Rentabilidade anual: {(profit_pct / max(days_invested/365, 0.1)):+.2f}%
"""
            
            if investment.broker:
                message += f"• Corretora: {investment.broker}"
            
            keyboard = [
                [
                    InlineKeyboardButton("➕ Comprar Mais", callback_data=f"buy_more_{investment_id}"),
                    InlineKeyboardButton("➖ Vender", callback_data=f"sell_{investment_id}")
                ],
                [
                    InlineKeyboardButton("📋 Histórico", callback_data=f"history_{investment_id}"),
                    InlineKeyboardButton("🔙 Voltar", callback_data="back")
                ]
            ]
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.INVESTMENT_MENU
            
    except Exception as e:
        logger.error(f"Erro na análise: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
        return ConversationStates.INVESTMENT_MENU


async def investment_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Mostra histórico de transações do investimento"""
    query = update.callback_query
    investment_id = int(query.data.split('_')[1])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            investment = session.query(Investment).filter(
                Investment.id == investment_id,
                Investment.user_id == user.id
            ).first()
            
            if not investment:
                await query.edit_message_text("❌ Investimento não encontrado.")
                return ConversationStates.INVESTMENT_MENU
            
            # Simular histórico (em produção, ter tabela de histórico)
            message = f"""
*📋 Histórico - {investment.ticker}*

*🔄 Transações:*

*Compra Inicial:*
• Data: {investment.purchase_date.strftime('%d/%m/%Y')}
• Quantidade: {investment.quantity:.4f}
• Preço: {format_currency(investment.avg_price)}
• Total: {format_currency(investment.quantity * investment.avg_price)}

"""
            
            # Se teve vendas
            if investment.sale_quantity and investment.sale_quantity > 0:
                message += f"""
*Venda Parcial:*
• Data: {investment.sale_date.strftime('%d/%m/%Y') if investment.sale_date else 'N/A'}
• Quantidade: {investment.sale_quantity:.4f}
• Preço: {format_currency(investment.sale_price or 0)}
• Total: {format_currency((investment.sale_quantity or 0) * (investment.sale_price or 0))}

"""
            
            message += f"""
*📊 Resumo Atual:*
• Quantidade Atual: {investment.current_quantity:.4f}
• Status: {'Ativo' if investment.is_active else 'Inativo'}
• Total de Operações: {1 + (1 if investment.sale_quantity else 0)}
"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Análise", callback_data=f"analyze_{investment_id}")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="back")]
            ]
            
            await query.edit_message_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.INVESTMENT_MENU
            
    except Exception as e:
        logger.error(f"Erro no histórico: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
        return ConversationStates.INVESTMENT_MENU


# ==================== CALLBACKS DE CATEGORIA ====================

async def select_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa seleção de categoria"""
    query = update.callback_query
    category_id = int(query.data.split('_')[1])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            category = session.query(Category).filter(
                Category.id == category_id,
                Category.user_id == user.id
            ).first()
            
            if not category:
                await query.edit_message_text("❌ Categoria não encontrada.")
                return ConversationStates.FINANCE_MENU
            
            # Armazenar categoria selecionada
            context.user_data['selected_category_id'] = category_id
            
            # Continuar com o fluxo da transação
            # Aqui deveria integrar com o fluxo de criação de transação
            
            await query.edit_message_text(
                f"✅ Categoria '{category.name}' selecionada!\n\n"
                "Continuando com a transação...",
                parse_mode='Markdown'
            )
            
            return ConversationStates.TRANSACTION_CONFIRM
            
    except Exception as e:
        logger.error(f"Erro ao selecionar categoria: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
        return ConversationStates.FINANCE_MENU


# ==================== CALLBACKS DE CONFIGURAÇÕES ====================

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa callbacks de configurações"""
    query = update.callback_query
    action = query.data.replace('settings_', '')
    
    if action == "profile":
        from handlers.settings import show_profile
        return await show_profile(query, context)
    elif action == "notifications":
        from handlers.settings import show_notifications_settings
        return await show_notifications_settings(query, context)
    # Adicionar outros handlers conforme necessário
    
    return ConversationStates.SETTINGS_MENU


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa callbacks de perfil"""
    query = update.callback_query
    action = query.data.replace('profile_', '')
    
    if action in ['conservative', 'moderate', 'aggressive']:
        try:
            with db.get_session() as session:
                user = get_user_from_update(query, session)
                
                # Mapear perfil
                profile_map = {
                    'conservative': InvestorProfile.CONSERVATIVE,
                    'moderate': InvestorProfile.MODERATE,
                    'aggressive': InvestorProfile.AGGRESSIVE
                }
                
                user.investor_profile = profile_map[action]
                session.commit()
                
                await query.edit_message_text(
                    f"✅ Perfil de investidor atualizado para: {action.title()}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar ao Perfil", callback_data="back_to_profile")
                    ]])
                )
                
        except Exception as e:
            logger.error(f"Erro ao atualizar perfil: {e}")
            await query.edit_message_text(Messages.ERROR_GENERIC)
    
    return ConversationStates.SETTINGS_PROFILE


async def notifications_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa callbacks de notificações"""
    query = update.callback_query
    action = query.data.replace('notifications_', '')
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            
            if action == "enable":
                user.notifications_enabled = True
                session.commit()
                await query.answer("✅ Notificações ativadas!")
            elif action == "disable":
                user.notifications_enabled = False
                session.commit()
                await query.answer("❌ Notificações desativadas!")
            
            # Voltar para configurações de notificações
            from handlers.settings import show_notifications_settings
            return await show_notifications_settings(query, context)
            
    except Exception as e:
        logger.error(f"Erro nas notificações: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
    
    return ConversationStates.SETTINGS_NOTIFICATIONS


# ==================== CALLBACKS GENÉRICOS ====================

async def confirm_yes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa confirmação positiva"""
    # Implementar lógica baseada no contexto
    return ConversationStates.MAIN_MENU


async def confirm_no_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa confirmação negativa"""
    query = update.callback_query
    await query.edit_message_text(Messages.CANCELLED)
    return ConversationStates.MAIN_MENU


async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa cancelamento"""
    query = update.callback_query
    await query.edit_message_text(Messages.CANCELLED)
    context.user_data.clear()
    return ConversationStates.MAIN_MENU


async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa volta para menu anterior"""
    # Implementar lógica de navegação baseada no estado atual
    return ConversationStates.MAIN_MENU


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback que não faz nada (placeholder para botões informativos)"""
    query = update.callback_query
    await query.answer("ℹ️ Este é apenas um botão informativo")
    return ConversationStates.MAIN_MENU


async def pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa navegação de páginas"""
    query = update.callback_query
    data = query.data
    
    # Extrair informações da paginação
    parts = data.split('_page_')
    if len(parts) != 2:
        return ConversationStates.MAIN_MENU
    
    prefix = parts[0]
    page = int(parts[1])
    
    # Armazenar página atual
    context.user_data['current_page'] = page
    
    # Redirecionar para o handler apropriado baseado no prefixo
    if prefix == "transactions":
        from handlers.finance import show_transactions
        return await show_transactions(query, context)
    elif prefix == "investments":
        from handlers.investment import show_portfolio
        return await show_portfolio(query, context)
    
    return ConversationStates.MAIN_MENU


async def export_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa callbacks de exportação"""
    query = update.callback_query
    export_type = query.data.replace('export_', '')
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            
            # Simular exportação
            await query.edit_message_text(
                f"📤 *Exportando dados em formato {export_type.upper()}...*\n\n"
                "⏳ Processando suas transações e investimentos...\n\n"
                "_Esta funcionalidade será implementada em breve!_\n\n"
                "Quando estiver pronta, você receberá um arquivo com:\n"
                "• Todas suas transações\n"
                "• Histórico de investimentos\n"
                "• Relatórios e análises\n"
                "• Configurações de categorias",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Voltar", callback_data="back_to_settings")
                ]])
            )
            
    except Exception as e:
        logger.error(f"Erro na exportação: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
    
    return ConversationStates.SETTINGS_MENU


async def timezone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa mudança de timezone"""
    query = update.callback_query
    timezone = query.data.replace('tz_', '')
    
    try:
        import pytz
        if timezone in pytz.all_timezones:
            with db.get_session() as session:
                user = get_user_from_update(query, session)
                user.timezone = timezone
                session.commit()
                
                # Obter nome amigável do timezone
                tz_names = {
                    'America/Sao_Paulo': 'Brasília (GMT-3)',
                    'America/Manaus': 'Manaus (GMT-4)',
                    'America/Rio_Branco': 'Rio Branco (GMT-5)',
                    'America/Noronha': 'Fernando de Noronha (GMT-2)'
                }
                
                tz_name = tz_names.get(timezone, timezone)
                
                await query.edit_message_text(
                    f"✅ Fuso horário atualizado para: {tz_name}",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 Voltar", callback_data="back_to_settings")
                    ]])
                )
        else:
            await query.edit_message_text("❌ Fuso horário inválido.")
            
    except Exception as e:
        logger.error(f"Erro ao atualizar timezone: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
    
    return ConversationStates.SETTINGS_TIMEZONE


# ==================== CALLBACKS ESPECÍFICOS PARA CONFIRMAÇÕES ====================

async def confirm_delete_transaction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma e executa exclusão de transação"""
    query = update.callback_query
    transaction_id = int(query.data.split('_')[3])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.user_id == user.id
            ).first()
            
            if not transaction:
                await query.edit_message_text("❌ Transação não encontrada.")
                return ConversationStates.FINANCE_MENU
            
            # Guardar dados para mensagem de confirmação
            description = transaction.description
            amount = transaction.amount
            
            # Excluir transação
            session.delete(transaction)
            session.commit()
            
            await query.edit_message_text(
                f"✅ *Transação excluída com sucesso!*\n\n"
                f"• {description}\n"
                f"• {format_currency(amount)}\n\n"
                "A transação foi removida permanentemente.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Voltar", callback_data="back")
                ]])
            )
            
    except Exception as e:
        logger.error(f"Erro ao excluir transação: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
    
    return ConversationStates.FINANCE_MENU


async def confirm_delete_investment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirma e executa exclusão de investimento"""
    query = update.callback_query
    investment_id = int(query.data.split('_')[3])
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            investment = session.query(Investment).filter(
                Investment.id == investment_id,
                Investment.user_id == user.id
            ).first()
            
            if not investment:
                await query.edit_message_text("❌ Investimento não encontrado.")
                return ConversationStates.INVESTMENT_MENU
            
            # Guardar dados para mensagem
            ticker = investment.ticker
            quantity = investment.current_quantity
            
            # Marcar como inativo ao invés de excluir (histórico)
            investment.is_active = False
            session.commit()
            
            await query.edit_message_text(
                f"✅ *Investimento removido da carteira!*\n\n"
                f"• {ticker}\n"
                f"• Quantidade: {quantity:.4f}\n\n"
                "O histórico foi mantido para consultas futuras.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Voltar", callback_data="back")
                ]])
            )
            
    except Exception as e:
        logger.error(f"Erro ao excluir investimento: {e}")
        await query.edit_message_text(Messages.ERROR_GENERIC)
    
    return ConversationStates.INVESTMENT_MENU


# ==================== SISTEMA DE HELP CONTEXTUAL ====================

async def help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sistema de ajuda contextual baseado no callback"""
    query = update.callback_query
    help_topic = query.data.replace('help_', '')
    
    help_texts = {
        'transactions': """
*💰 Ajuda - Transações*

*Como adicionar uma transação:*
1. Vá em 'Finanças Pessoais'
2. Escolha '➕ Novo Lançamento'
3. Selecione Receita ou Despesa
4. Digite o valor (use vírgula ou ponto)
5. Adicione uma descrição
6. Escolha forma de pagamento
7. Selecione a data
8. Escolha ou crie uma categoria

*Dicas importantes:*
• Valores podem ser digitados como: 150,50 ou 150.50
• Datas no formato DD/MM/AAAA
• Use categorias para organizar seus gastos
• Adicione descrições detalhadas
""",
        'investments': """
*📈 Ajuda - Investimentos*

*Como registrar um investimento:*
1. Vá em 'Investimentos'
2. Escolha '➕ Comprar'
3. Selecione o tipo de ativo
4. Digite o ticker (ex: PETR4, BTC)
5. Informe quantidade comprada
6. Digite o preço unitário
7. Confirme a operação

*Tipos suportados:*
• 📊 Ações (PETR4, VALE3)
• 🏠 FIIs (MXRF11, HGLG11)
• 🪙 Criptomoedas (BTC, ETH)
• 📈 ETFs (IVVB11, BOVA11)
• 💰 Renda Fixa (LTN, CDB)

*Dicas:*
• Use tickers corretos da B3
• Para crypto, use símbolos padrão
• Mantenha histórico atualizado
""",
        'categories': """
*🏷️ Ajuda - Categorias*

*Categorias padrão:*
O bot já vem com categorias pré-definidas para facilitar o uso.

*Como criar categoria personalizada:*
1. Durante uma transação, escolha '➕ Nova Categoria'
2. Digite o nome da categoria
3. Ela será criada automaticamente

*Limites:*
• Máximo de 50 categorias por usuário
• Categorias são separadas por tipo (receita/despesa)
• Nomes devem ser únicos

*Dicas:*
• Use nomes claros e específicos
• Evite muitas categorias similares
• Organize por tipo de gasto
""",
        'reports': """
*📊 Ajuda - Relatórios*

*Relatórios disponíveis:*
• Resumo mensal atual
• Análise de saúde financeira
• Distribuição por categorias
• Performance de investimentos

*Como interpretar a saúde financeira:*
• 🟢 80-100: Excelente controle
• 🟡 60-79: Boa situação
• 🟠 40-59: Situação regular
• 🔴 0-39: Precisa melhorar

*Métricas importantes:*
• Taxa de poupança (ideal: 20%+)
• Equilíbrio receita/despesa
• Consistência mensal
• Diversificação de investimentos
"""
    }
    
    help_text = help_texts.get(help_topic, "❌ Tópico de ajuda não encontrado.")
    
    await query.edit_message_text(
        help_text,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Voltar", callback_data="back"),
            InlineKeyboardButton("❓ Mais Ajuda", callback_data="help_main")
        ]])
    )
    
    return ConversationStates.SHOWING_HELP


# ==================== EXPORTAÇÃO DE HANDLERS ====================

def get_callback_handlers():
    """
    Retorna dicionário com todos os handlers de callback
    Para uso no main.py ao configurar a aplicação
    """
    return {
        # Handler principal que roteia todos os callbacks
        'main_router': CallbackRouter.route_callback,
        
        # Handlers específicos (se necessário acesso direto)
        'transaction_type': transaction_type_callback,
        'edit_transaction': edit_transaction_callback,
        'delete_transaction': delete_transaction_callback,
        'transaction_details': transaction_details_callback,
        'buy_more_investment': buy_more_investment_callback,
        'sell_investment': sell_investment_callback,
        'analyze_investment': analyze_investment_callback,
        'investment_history': investment_history_callback,
        'confirm_delete_transaction': confirm_delete_transaction_callback,
        'confirm_delete_investment': confirm_delete_investment_callback,
        'help': help_callback,
    }


# ==================== UTILITÁRIOS PARA CALLBACKS ====================

def create_pagination_keyboard(
    items: list,
    current_page: int,
    items_per_page: int,
    callback_prefix: str,
    action_buttons: list = None
) -> InlineKeyboardMarkup:
    """
    Cria teclado com paginação para listas grandes
    """
    total_pages = (len(items) + items_per_page - 1) // items_per_page
    
    # Botões dos itens da página atual
    start_idx = (current_page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_items = items[start_idx:end_idx]
    
    keyboard = []
    
    # Adicionar botões dos itens (2 por linha)
    for i in range(0, len(current_items), 2):
        row = [InlineKeyboardButton(
            current_items[i]['text'],
            callback_data=current_items[i]['callback']
        )]
        
        if i + 1 < len(current_items):
            row.append(InlineKeyboardButton(
                current_items[i + 1]['text'],
                callback_data=current_items[i + 1]['callback']
            ))
        
        keyboard.append(row)
    
    # Adicionar botões de ação se fornecidos
    if action_buttons:
        for action_row in action_buttons:
            keyboard.append(action_row)
    
    # Adicionar navegação se necessário
    if total_pages > 1:
        nav_row = []
        
        if current_page > 1:
            nav_row.append(InlineKeyboardButton(
                "⬅️ Anterior",
                callback_data=f"{callback_prefix}_page_{current_page - 1}"
            ))
        
        nav_row.append(InlineKeyboardButton(
            f"{current_page}/{total_pages}",
            callback_data="noop"
        ))
        
        if current_page < total_pages:
            nav_row.append(InlineKeyboardButton(
                "Próximo ➡️",
                callback_data=f"{callback_prefix}_page_{current_page + 1}"
            ))
        
        keyboard.append(nav_row)
    
    return InlineKeyboardMarkup(keyboard)


def format_callback_data(action: str, item_id: int, extra: str = None) -> str:
    """
    Formata callback_data de forma consistente
    Garante que não exceda o limite de 64 bytes do Telegram
    """
    if extra:
        callback = f"{action}_{item_id}_{extra}"
    else:
        callback = f"{action}_{item_id}"
    
    # Telegram tem limite de 64 bytes para callback_data
    if len(callback.encode('utf-8')) > 64:
        # Truncar se necessário
        callback = callback[:60] + "..."
    
    return callback