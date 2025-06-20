"""
Handlers para configurações do usuário
"""
import logging
from datetime import datetime
from decimal import Decimal
import pytz

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import Config, Messages, Emojis
from database import db
from keyboards import Keyboards
from models import User, Category, TransactionType, InvestorProfile
from services import UserService, CategoryService
from states import ConversationStates
from utils import (
    get_user_from_update, format_currency, parse_amount,
    validate_amount, escape_markdown
)

logger = logging.getLogger(__name__)


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe o menu de configurações"""
    await update.message.reply_text(
        "*⚙️ Configurações*\n\n"
        "Personalize sua experiência:",
        parse_mode='Markdown',
        reply_markup=Keyboards.settings_menu()
    )
    return ConversationStates.SETTINGS_MENU


async def settings_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa as opções do menu de configurações"""
    if not update.message or not update.message.text:
        return ConversationStates.SETTINGS_MENU
    
    text = update.message.text
    
    if text == '👤 Perfil':
        return await show_profile(update, context)
    
    elif text == '🔔 Notificações':
        return await show_notifications_settings(update, context)
    
    elif text == '🏷️ Categorias':
        return await manage_categories(update, context)
    
    elif text == '📤 Exportar Dados':
        return await export_data(update, context)
    
    elif text == '🎯 Metas':
        return await show_goals(update, context)
    
    elif text == '🌍 Timezone':
        return await show_timezone_settings(update, context)
    
    elif text == f'{Emojis.BACK} Menu Principal':
        from .main import main_menu
        return await main_menu(update, context)
    
    return ConversationStates.SETTINGS_MENU


# ==================== PERFIL ====================

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe o perfil do usuário"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Estatísticas do usuário
            from services import TransactionService, InvestmentService
            
            # Contar transações
            transaction_count = session.query(Transaction).filter(
                Transaction.user_id == user.id
            ).count()
            
            # Contar investimentos
            investment_count = session.query(Investment).filter(
                Investment.user_id == user.id,
                Investment.is_active == True
            ).count()
            
            # Data de cadastro
            days_since_join = (datetime.now() - user.created_at).days
            
            # Perfil de investidor
            profile_names = {
                InvestorProfile.CONSERVATIVE: "Conservador 🛡️",
                InvestorProfile.MODERATE: "Moderado ⚖️",
                InvestorProfile.AGGRESSIVE: "Agressivo 🚀"
            }
            
            message = f"""
*👤 Seu Perfil*

*Informações Pessoais:*
• Nome: {escape_markdown(user.first_name or 'Não informado')}
• Username: @{escape_markdown(user.username or 'não definido')}
• ID Telegram: `{user.telegram_id}`

*Perfil Financeiro:*
• Tipo de Investidor: {profile_names.get(user.investor_profile, 'Não definido')}
• Renda Mensal: {format_currency(user.monthly_income) if user.monthly_income else 'Não informada'}
• Meta de Poupança: {format_currency(user.savings_goal) if user.savings_goal else 'Não definida'}

*Estatísticas:*
• Membro há: {days_since_join} dias
• Transações: {transaction_count}
• Investimentos Ativos: {investment_count}
• Timezone: {user.timezone}

*Configurações:*
• Notificações: {'✅ Ativadas' if user.notifications_enabled else '❌ Desativadas'}
• Última atualização: {user.updated_at.strftime('%d/%m/%Y %H:%M')}
"""
            
            # Criar teclado inline para ações
            keyboard = [
                [InlineKeyboardButton("✏️ Editar Perfil", callback_data="edit_profile")],
                [InlineKeyboardButton("🎯 Alterar Perfil de Investidor", callback_data="change_investor_profile")],
                [InlineKeyboardButton("💰 Definir Renda Mensal", callback_data="set_income")],
                [InlineKeyboardButton("🎯 Definir Meta de Poupança", callback_data="set_savings_goal")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_settings")]
            ]
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.SETTINGS_PROFILE
            
    except Exception as e:
        logger.error(f"Erro ao exibir perfil: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.settings_menu()
        )
        return ConversationStates.SETTINGS_MENU


# ==================== NOTIFICAÇÕES ====================

async def show_notifications_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe configurações de notificações"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            status = "✅ Ativadas" if user.notifications_enabled else "❌ Desativadas"
            
            message = f"""
*🔔 Configurações de Notificações*

*Status Atual:* {status}

*Tipos de Notificação:*
• 💵 Alertas de dividendos
• 📈 Oportunidades de investimento
• 💰 Lembretes de lançamentos
• 📊 Resumos semanais/mensais
• 🎯 Metas atingidas
• ⚠️ Alertas de gastos excessivos

*Horário de Envio:*
• Resumos: 08:00 (manhã)
• Alertas: Em tempo real
"""
            
            # Criar teclado inline
            keyboard = []
            
            if user.notifications_enabled:
                keyboard.append([
                    InlineKeyboardButton(
                        "❌ Desativar Notificações",
                        callback_data="notifications_disable"
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        "✅ Ativar Notificações",
                        callback_data="notifications_enable"
                    )
                ])
            
            keyboard.extend([
                [InlineKeyboardButton("⏰ Configurar Horários", callback_data="notifications_schedule")],
                [InlineKeyboardButton("📋 Escolher Tipos", callback_data="notifications_types")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_settings")]
            ])
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.SETTINGS_NOTIFICATIONS
            
    except Exception as e:
        logger.error(f"Erro nas configurações de notificações: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.settings_menu()
        )
        return ConversationStates.SETTINGS_MENU


# ==================== CATEGORIAS ====================

async def manage_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gerencia categorias personalizadas"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Buscar categorias
            categories = CategoryService.get_user_categories(session, user)
            
            # Separar por tipo
            income_cats = [c for c in categories if c.type == TransactionType.INCOME]
            expense_cats = [c for c in categories if c.type == TransactionType.EXPENSE]
            
            # Contar personalizadas
            custom_count = sum(1 for c in categories if not c.is_system)
            
            message = f"""
*🏷️ Gerenciar Categorias*

Total: {len(categories)} categorias ({custom_count} personalizadas)
Limite: {Config.MAX_CATEGORIES_PER_USER}

*💵 Categorias de Receita ({len(income_cats)}):*
"""
            
            for cat in income_cats:
                icon = cat.icon or ""
                custom = " 🔧" if not cat.is_system else ""
                active = "✅" if cat.is_active else "❌"
                message += f"• {active} {icon} {cat.name}{custom}\n"
            
            message += f"\n*💸 Categorias de Despesa ({len(expense_cats)}):*\n"
            
            for cat in expense_cats:
                icon = cat.icon or ""
                custom = " 🔧" if not cat.is_system else ""
                active = "✅" if cat.is_active else "❌"
                message += f"• {active} {icon} {cat.name}{custom}\n"
            
            message += "\n_🔧 = Categoria personalizada_"
            
            # Criar teclado
            keyboard = [
                [InlineKeyboardButton("➕ Nova Categoria", callback_data="category_new")],
                [InlineKeyboardButton("✏️ Editar Categoria", callback_data="category_edit")],
                [InlineKeyboardButton("🗑️ Excluir Categoria", callback_data="category_delete")],
                [InlineKeyboardButton("🔄 Restaurar Padrões", callback_data="category_restore")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_settings")]
            ]
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.SETTINGS_MENU  # Por enquanto
            
    except Exception as e:
        logger.error(f"Erro ao gerenciar categorias: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.settings_menu()
        )
        return ConversationStates.SETTINGS_MENU


# ==================== EXPORTAR DADOS ====================

async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exporta dados do usuário"""
    await update.message.reply_text(
        "*📤 Exportar Dados*\n\n"
        "Escolha o formato de exportação:",
        parse_mode='Markdown'
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Excel (.xlsx)", callback_data="export_excel")],
        [InlineKeyboardButton("📄 PDF", callback_data="export_pdf")],
        [InlineKeyboardButton("💾 CSV", callback_data="export_csv")],
        [InlineKeyboardButton("📋 JSON", callback_data="export_json")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_settings")]
    ]
    
    await update.message.reply_text(
        "Selecione o formato desejado:\n\n"
        "_Seus dados serão processados e enviados em instantes._",
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationStates.SETTINGS_MENU


# ==================== METAS ====================

async def show_goals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe e gerencia metas financeiras"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Por enquanto, vamos simular algumas metas
            message = """
*🎯 Suas Metas Financeiras*

*Meta de Poupança Mensal:*
"""
            
            if user.savings_goal:
                # Calcular progresso do mês atual
                from services import TransactionService
                now = datetime.now()
                summary = TransactionService.get_monthly_summary(
                    session, user, now.year, now.month
                )
                
                savings = summary['balance']
                progress = (savings / user.savings_goal * 100) if user.savings_goal > 0 else 0
                progress_bar = ProgressBar.create(savings, user.savings_goal)
                
                message += f"Meta: {format_currency(user.savings_goal)}\n"
                message += f"Economizado: {format_currency(savings)}\n"
                message += f"Progresso: {progress_bar}\n\n"
            else:
                message += "Não definida\n\n"
            
            message += """
*Outras Metas:*
• 🏠 Comprar Casa: R$ 300.000 (em 5 anos)
• 🚗 Trocar Carro: R$ 80.000 (em 2 anos)
• ✈️ Viagem dos Sonhos: R$ 15.000 (em 1 ano)
• 💰 Reserva de Emergência: R$ 30.000

_Em breve você poderá criar e acompanhar metas personalizadas!_
"""
            
            keyboard = [
                [InlineKeyboardButton("💰 Definir Meta de Poupança", callback_data="set_savings_goal")],
                [InlineKeyboardButton("➕ Criar Nova Meta", callback_data="goal_new")],
                [InlineKeyboardButton("📊 Ver Progresso", callback_data="goal_progress")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_settings")]
            ]
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.SETTINGS_GOALS
            
    except Exception as e:
        logger.error(f"Erro ao exibir metas: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.settings_menu()
        )
        return ConversationStates.SETTINGS_MENU


# ==================== TIMEZONE ====================

async def show_timezone_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe configurações de timezone"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Obter hora atual no timezone do usuário
            user_tz = pytz.timezone(user.timezone)
            current_time = datetime.now(user_tz)
            
            message = f"""
*🌍 Configuração de Fuso Horário*

*Timezone Atual:* {user.timezone}
*Hora Local:* {current_time.strftime('%H:%M:%S')}
*Data:* {current_time.strftime('%d/%m/%Y')}

Este horário é usado para:
• Envio de notificações
• Cálculo de períodos (dia/semana/mês)
• Agendamento de alertas
• Relatórios diários

Selecione seu fuso horário:
"""
            
            # Principais timezones do Brasil
            brazil_timezones = [
                ("America/Sao_Paulo", "Brasília (GMT-3)"),
                ("America/Manaus", "Manaus (GMT-4)"),
                ("America/Rio_Branco", "Rio Branco (GMT-5)"),
                ("America/Noronha", "Fernando de Noronha (GMT-2)")
            ]
            
            keyboard = []
            for tz, name in brazil_timezones:
                if tz == user.timezone:
                    name = f"✅ {name}"
                keyboard.append([InlineKeyboardButton(name, callback_data=f"tz_{tz}")])
            
            keyboard.extend([
                [InlineKeyboardButton("🌎 Outros Fusos", callback_data="tz_others")],
                [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_settings")]
            ])
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationStates.SETTINGS_TIMEZONE
            
    except Exception as e:
        logger.error(f"Erro nas configurações de timezone: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.settings_menu()
        )
        return ConversationStates.SETTINGS_MENU


# ==================== CALLBACKS DE CONFIGURAÇÕES ====================

async def settings_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa callbacks do menu de configurações"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Voltar ao menu de configurações
    if data == "back_to_settings":
        await query.message.edit_text(
            "*⚙️ Configurações*\n\n"
            "Personalize sua experiência:",
            parse_mode='Markdown',
            reply_markup=Keyboards.settings_menu()
        )
        return ConversationStates.SETTINGS_MENU
    
    # Notificações
    elif data == "notifications_enable":
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            user.notifications_enabled = True
            session.commit()
        
        await query.answer("✅ Notificações ativadas!")
        return await show_notifications_settings(query, context)
    
    elif data == "notifications_disable":
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            user.notifications_enabled = False
            session.commit()
        
        await query.answer("❌ Notificações desativadas!")
        return await show_notifications_settings(query, context)
    
    # Perfil de investidor
    elif data == "change_investor_profile":
        keyboard = [
            [InlineKeyboardButton("🛡️ Conservador", callback_data="profile_conservative")],
            [InlineKeyboardButton("⚖️ Moderado", callback_data="profile_moderate")],
            [InlineKeyboardButton("🚀 Agressivo", callback_data="profile_aggressive")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="back_to_profile")]
        ]
        
        await query.message.edit_text(
            "*🎯 Escolha seu Perfil de Investidor*\n\n"
            "*🛡️ Conservador:* Prioriza segurança e preservação de capital\n"
            "*⚖️ Moderado:* Busca equilíbrio entre segurança e rentabilidade\n"
            "*🚀 Agressivo:* Aceita mais riscos em busca de maiores retornos",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationStates.SETTINGS_PROFILE
    
    elif data.startswith("profile_"):
        profile_map = {
            "profile_conservative": InvestorProfile.CONSERVATIVE,
            "profile_moderate": InvestorProfile.MODERATE,
            "profile_aggressive": InvestorProfile.AGGRESSIVE
        }
        
        new_profile = profile_map.get(data)
        if new_profile:
            with db.get_session() as session:
                user = get_user_from_update(query, session)
                user.investor_profile = new_profile
                session.commit()
            
            await query.answer("✅ Perfil atualizado!")
            return await show_profile(query, context)
    
    # Timezone
    elif data.startswith("tz_"):
        timezone = data.replace("tz_", "")
        if timezone in pytz.all_timezones:
            with db.get_session() as session:
                user = get_user_from_update(query, session)
                user.timezone = timezone
                session.commit()
            
            await query.answer("✅ Fuso horário atualizado!")
            return await show_timezone_settings(query, context)
    
    return ConversationStates.SETTINGS_MENU


# Importar modelos necessários
from models import Transaction, Investment
from utils import ProgressBar