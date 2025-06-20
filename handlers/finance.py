"""
Handlers para funcionalidades de finanças pessoais
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes

from config import Config, Messages, Emojis
from database import db
from keyboards import Keyboards
from models import TransactionType, Category
from services import TransactionService, CategoryService, UserService
from states import ConversationStates
from utils import (
    parse_amount, format_currency, parse_date,
    get_user_from_update, validate_amount
)

logger = logging.getLogger(__name__)


async def finance_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe o menu de finanças"""
    await update.message.reply_text(
        "*💰 Finanças Pessoais*\n\n"
        "Escolha uma opção para gerenciar suas finanças:",
        parse_mode='Markdown',
        reply_markup=Keyboards.finance_menu()
    )
    return ConversationStates.FINANCE_MENU


async def finance_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa as opções do menu de finanças"""
    if not update.message or not update.message.text:
        return ConversationStates.FINANCE_MENU
    
    text = update.message.text
    
    if text == '➕ Novo Lançamento':
        return await start_new_transaction(update, context)
    
    elif text == '📋 Ver Lançamentos':
        return await show_transactions(update, context)
    
    elif text == '📊 Resumo Financeiro':
        return await show_financial_summary(update, context)
    
    elif text == '🏷️ Categorias':
        return await show_categories(update, context)
    
    elif text == '📈 Análise Detalhada':
        return await show_detailed_analysis(update, context)
    
    elif text == '💡 Dicas':
        return await show_financial_tips(update, context)
    
    elif text == f'{Emojis.BACK} Menu Principal':
        from .main import main_menu
        return await main_menu(update, context)
    
    return ConversationStates.FINANCE_MENU


# ==================== NOVA TRANSAÇÃO ====================

async def start_new_transaction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia o processo de nova transação"""
    await update.message.reply_text(
        "*Nova Transação*\n\n"
        "Que tipo de lançamento você deseja fazer?",
        parse_mode='Markdown',
        reply_markup=Keyboards.transaction_type()
    )
    return ConversationStates.TRANSACTION_TYPE


async def transaction_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a escolha do tipo de transação"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text(Messages.CANCELLED)
        return await finance_menu(query, context)
    
    # Armazenar tipo escolhido
    if query.data == "transaction_income":
        context.user_data['transaction_type'] = TransactionType.INCOME
        type_name = "Receita"
    else:
        context.user_data['transaction_type'] = TransactionType.EXPENSE
        type_name = "Despesa"
    
    await query.edit_message_text(
        f"*Nova {type_name}*\n\n{Messages.ASK_AMOUNT}",
        parse_mode='Markdown'
    )
    
    return ConversationStates.TRANSACTION_AMOUNT


async def transaction_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa o valor da transação"""
    if not update.message or not update.message.text:
        return ConversationStates.TRANSACTION_AMOUNT
    
    # Cancelar
    if update.message.text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await finance_menu(update, context)
    
    try:
        # Tentar parsear o valor
        amount = parse_amount(update.message.text)
        
        # Validar limites
        validation_error = validate_amount(amount)
        if validation_error:
            await update.message.reply_text(validation_error)
            return ConversationStates.TRANSACTION_AMOUNT
        
        # Armazenar valor
        context.user_data['amount'] = amount
        
        # Pedir descrição
        await update.message.reply_text(
            f"Valor: {format_currency(amount)}\n\n"
            f"{Messages.ASK_DESCRIPTION}",
            reply_markup=Keyboards.cancel_only()
        )
        
        return ConversationStates.TRANSACTION_DESCRIPTION
        
    except (ValueError, InvalidOperation):
        await update.message.reply_text(Messages.ERROR_INVALID_AMOUNT)
        return ConversationStates.TRANSACTION_AMOUNT


async def transaction_description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a descrição da transação"""
    if not update.message or not update.message.text:
        return ConversationStates.TRANSACTION_DESCRIPTION
    
    # Cancelar
    if update.message.text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await finance_menu(update, context)
    
    # Validar descrição
    description = update.message.text.strip()
    if not description:
        await update.message.reply_text(Messages.ERROR_DESCRIPTION_EMPTY)
        return ConversationStates.TRANSACTION_DESCRIPTION
    
    # Armazenar descrição
    context.user_data['description'] = description[:Config.MAX_DESCRIPTION_LENGTH]
    
    # Pedir método de pagamento
    transaction_type = context.user_data['transaction_type']
    
    await update.message.reply_text(
        f"Selecione a forma de {'pagamento' if transaction_type == TransactionType.EXPENSE else 'recebimento'}:",
        reply_markup=Keyboards.payment_methods(transaction_type)
    )
    
    return ConversationStates.TRANSACTION_PAYMENT_METHOD


async def transaction_payment_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa o método de pagamento"""
    if not update.message or not update.message.text:
        return ConversationStates.TRANSACTION_PAYMENT_METHOD
    
    # Cancelar
    if update.message.text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await finance_menu(update, context)
    
    # Armazenar método
    from config import PaymentMethods
    payment_method = PaymentMethods.get_method_key(update.message.text)
    context.user_data['payment_method'] = payment_method
    
    # Pedir data
    await update.message.reply_text(
        Messages.ASK_DATE,
        reply_markup=Keyboards.date_selection()
    )
    
    return ConversationStates.TRANSACTION_DATE


async def transaction_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a data da transação"""
    if not update.message or not update.message.text:
        return ConversationStates.TRANSACTION_DATE
    
    # Cancelar
    if update.message.text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await finance_menu(update, context)
    
    try:
        # Processar data
        text = update.message.text
        
        if text == '📅 Hoje':
            date = datetime.now()
        elif text == '📅 Ontem':
            date = datetime.now() - timedelta(days=1)
        elif text == '📅 Esta Semana':
            date = datetime.now() - timedelta(days=datetime.now().weekday())
        elif text == '📅 Este Mês':
            date = datetime.now().replace(day=1)
        elif text == '✏️ Digitar Data':
            await update.message.reply_text(
                "Digite a data no formato DD/MM/AAAA:",
                reply_markup=Keyboards.cancel_only()
            )
            return ConversationStates.TRANSACTION_DATE
        else:
            # Tentar parsear data digitada
            date = parse_date(text)
            
            # Validar data futura
            if date > datetime.now():
                await update.message.reply_text(Messages.ERROR_FUTURE_DATE)
                return ConversationStates.TRANSACTION_DATE
        
        # Armazenar data
        context.user_data['date'] = date
        
        # Buscar categorias do usuário
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            transaction_type = context.user_data['transaction_type']
            
            categories = CategoryService.get_user_categories(
                session,
                user,
                category_type=transaction_type
            )
        
        if not categories:
            await update.message.reply_text(
                "❌ Nenhuma categoria encontrada. Criando categoria padrão...",
                reply_markup=Keyboards.finance_menu()
            )
            # Aqui você poderia criar uma categoria padrão
            return ConversationStates.FINANCE_MENU
        
        # Pedir categoria
        await update.message.reply_text(
            Messages.ASK_CATEGORY,
            reply_markup=Keyboards.categories(categories)
        )
        
        return ConversationStates.TRANSACTION_CATEGORY
        
    except ValueError:
        await update.message.reply_text(Messages.ERROR_INVALID_DATE)
        return ConversationStates.TRANSACTION_DATE


async def transaction_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a categoria e finaliza a transação"""
    if not update.message or not update.message.text:
        return ConversationStates.TRANSACTION_CATEGORY
    
    # Cancelar
    if update.message.text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await finance_menu(update, context)
    
    # Nova categoria
    if update.message.text == '➕ Nova Categoria':
        context.user_data['creating_category'] = True
        await update.message.reply_text(
            "Digite o nome da nova categoria:",
            reply_markup=Keyboards.cancel_only()
        )
        return ConversationStates.CATEGORY_NAME
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Buscar categoria
            category_name = update.message.text
            transaction_type = context.user_data['transaction_type']
            
            category = session.query(Category).filter(
                Category.user_id == user.id,
                Category.name == category_name,
                Category.type == transaction_type
            ).first()
            
            if not category:
                await update.message.reply_text(Messages.ERROR_CATEGORY_NOT_FOUND)
                return ConversationStates.TRANSACTION_CATEGORY
            
            # Criar transação
            transaction = TransactionService.create_transaction(
                session=session,
                user=user,
                category=category,
                amount=context.user_data['amount'],
                description=context.user_data['description'],
                payment_method=context.user_data['payment_method'],
                date=context.user_data['date'],
                transaction_type=transaction_type
            )
            
            # Mensagem de sucesso
            emoji = Emojis.MONEY_IN if transaction_type == TransactionType.INCOME else Emojis.MONEY_OUT
            
            success_message = Messages.SUCCESS_TRANSACTION.format(
                emoji=emoji,
                description=transaction.description,
                amount=transaction.amount,
                category=category.name,
                date=transaction.date.strftime('%d/%m/%Y')
            )
            
            await update.message.reply_text(
                success_message,
                parse_mode='Markdown',
                reply_markup=Keyboards.finance_menu()
            )
            
            # Limpar dados temporários
            context.user_data.clear()
            
            return ConversationStates.FINANCE_MENU
            
    except ValueError as e:
        await update.message.reply_text(f"❌ Erro: {str(e)}")
        return ConversationStates.TRANSACTION_CATEGORY
    except Exception as e:
        logger.error(f"Erro ao criar transação: {e}")
        await update.message.reply_text(Messages.ERROR_SAVE_FAILED)
        context.user_data.clear()
        return await finance_menu(update, context)


# ==================== VISUALIZAÇÕES ====================

async def show_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe as últimas transações do usuário"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Buscar transações
            transactions = TransactionService.get_user_transactions(
                session,
                user,
                limit=Config.MAX_TRANSACTIONS_PER_PAGE
            )
            
            if not transactions:
                await update.message.reply_text(
                    Messages.NO_TRANSACTIONS,
                    reply_markup=Keyboards.finance_menu()
                )
                return ConversationStates.FINANCE_MENU
            
            # Montar mensagem
            message = "*📋 Últimas Transações*\n\n"
            
            for t in transactions:
                emoji = Emojis.MONEY_IN if t.type == TransactionType.INCOME else Emojis.MONEY_OUT
                signal = "+" if t.type == TransactionType.INCOME else "-"
                
                message += f"{emoji} *{t.date.strftime('%d/%m')}* - {t.description}\n"
                message += f"   {signal}{format_currency(t.amount)} ({t.category.name})\n"
                message += f"   _{t.payment_method}_\n\n"
            
            # Adicionar resumo
            total_income = sum(t.amount for t in transactions if t.type == TransactionType.INCOME)
            total_expense = sum(t.amount for t in transactions if t.type == TransactionType.EXPENSE)
            
            message += f"*Resumo:*\n"
            message += f"Receitas: +{format_currency(total_income)}\n"
            message += f"Despesas: -{format_currency(total_expense)}\n"
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=Keyboards.finance_menu()
            )
            
    except Exception as e:
        logger.error(f"Erro ao exibir transações: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.finance_menu()
        )
    
    return ConversationStates.FINANCE_MENU


async def show_financial_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe resumo financeiro do mês atual"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Obter resumo do mês atual
            now = datetime.now()
            summary = TransactionService.get_monthly_summary(
                session,
                user,
                now.year,
                now.month
            )
            
            # Obter score de saúde financeira
            health_score, health_status = TransactionService.get_financial_health_score(
                session,
                user
            )
            
            # Determinar emoji do status
            if health_score >= 80:
                status_emoji = Emojis.GREEN
            elif health_score >= 60:
                status_emoji = Emojis.YELLOW
            else:
                status_emoji = Emojis.RED
            
            # Montar mensagem
            message = f"*📊 Resumo Financeiro - {summary['period']}*\n\n"
            
            message += f"{status_emoji} *Status:* {health_status} ({health_score}/100)\n\n"
            
            message += f"*📈 Números do Mês:*\n"
            message += f"• Receitas: +{format_currency(summary['total_income'])}\n"
            message += f"• Despesas: -{format_currency(summary['total_expenses'])}\n"
            message += f"• Saldo: {format_currency(summary['balance'])}\n"
            message += f"• Taxa de Poupança: {summary['savings_rate']:.1f}%\n"
            message += f"• Transações: {summary['transaction_count']}\n"
            
            if summary['expenses_by_category']:
                message += f"\n*💸 Principais Gastos:*\n"
                
                # Ordenar por valor
                sorted_expenses = sorted(
                    summary['expenses_by_category'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                
                for category, amount in sorted_expenses[:5]:
                    percentage = (amount / summary['total_expenses'] * 100) if summary['total_expenses'] > 0 else 0
                    message += f"• {category}: {format_currency(amount)} ({percentage:.1f}%)\n"
            
            # Adicionar dica baseada no status
            if health_score < 40:
                message += f"\n💡 *Dica:* Seus gastos estão altos. Analise suas despesas e identifique onde pode economizar."
            elif health_score < 60:
                message += f"\n💡 *Dica:* Você está no caminho certo! Tente aumentar sua taxa de poupança para 20% ou mais."
            else:
                message += f"\n💡 *Dica:* Excelente controle financeiro! Continue assim e considere investir suas economias."
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=Keyboards.finance_menu()
            )
            
    except Exception as e:
        logger.error(f"Erro ao exibir resumo: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.finance_menu()
        )
    
    return ConversationStates.FINANCE_MENU


async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe as categorias do usuário"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Buscar categorias
            income_categories = CategoryService.get_user_categories(
                session,
                user,
                category_type=TransactionType.INCOME
            )
            
            expense_categories = CategoryService.get_user_categories(
                session,
                user,
                category_type=TransactionType.EXPENSE
            )
            
            # Montar mensagem
            message = "*🏷️ Suas Categorias*\n\n"
            
            if income_categories:
                message += f"*{Emojis.MONEY_IN} Receitas:*\n"
                for cat in income_categories:
                    icon = cat.icon or ""
                    system = " _(padrão)_" if cat.is_system else ""
                    message += f"• {icon} {cat.name}{system}\n"
            
            if expense_categories:
                message += f"\n*{Emojis.MONEY_OUT} Despesas:*\n"
                for cat in expense_categories:
                    icon = cat.icon or ""
                    system = " _(padrão)_" if cat.is_system else ""
                    message += f"• {icon} {cat.name}{system}\n"
            
            message += f"\n_Total de categorias: {len(income_categories) + len(expense_categories)}/{Config.MAX_CATEGORIES_PER_USER}_"
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=Keyboards.finance_menu()
            )
            
    except Exception as e:
        logger.error(f"Erro ao exibir categorias: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.finance_menu()
        )
    
    return ConversationStates.FINANCE_MENU


async def show_detailed_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe análise detalhada das finanças"""
    # TODO: Implementar análise detalhada com gráficos
    await update.message.reply_text(
        "*📈 Análise Detalhada*\n\n"
        "_Esta funcionalidade será implementada em breve!_\n\n"
        "Aqui você poderá:\n"
        "• Ver gráficos de evolução\n"
        "• Comparar períodos\n"
        "• Analisar tendências\n"
        "• Prever gastos futuros",
        parse_mode='Markdown',
        reply_markup=Keyboards.finance_menu()
    )
    return ConversationStates.FINANCE_MENU


async def show_financial_tips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe dicas financeiras personalizadas"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Obter dados para análise
            health_score, _ = TransactionService.get_financial_health_score(session, user)
            
            # Gerar dicas baseadas no perfil
            tips = [
                "💡 *Dicas Financeiras Personalizadas*\n"
            ]
            
            if health_score < 40:
                tips.extend([
                    "\n🔴 *Atenção Urgente:*",
                    "• Revise todos os seus gastos mensais",
                    "• Identifique despesas que podem ser cortadas",
                    "• Crie um orçamento mensal e siga rigorosamente",
                    "• Evite compras por impulso",
                    "• Considere fontes adicionais de renda"
                ])
            elif health_score < 70:
                tips.extend([
                    "\n🟡 *Melhorias Recomendadas:*",
                    "• Aumente sua taxa de poupança para 20%",
                    "• Crie uma reserva de emergência (3-6 meses)",
                    "• Revise assinaturas e serviços não utilizados",
                    "• Planeje compras grandes com antecedência",
                    "• Comece a investir o valor poupado"
                ])
            else:
                tips.extend([
                    "\n🟢 *Otimizações Avançadas:*",
                    "• Diversifique seus investimentos",
                    "• Considere investimentos de longo prazo",
                    "• Otimize sua declaração de IR",
                    "• Explore renda passiva",
                    "• Planeje aposentadoria antecipada"
                ])
            
            tips.extend([
                "\n📚 *Educação Financeira:*",
                "• Leia livros sobre finanças pessoais",
                "• Acompanhe canais de educação financeira",
                "• Participe de comunidades de investidores",
                "• Mantenha-se atualizado sobre economia"
            ])
            
            await update.message.reply_text(
                "\n".join(tips),
                parse_mode='Markdown',
                reply_markup=Keyboards.finance_menu()
            )
            
    except Exception as e:
        logger.error(f"Erro ao gerar dicas: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.finance_menu()
        )
    
    return ConversationStates.FINANCE_MENU


# ==================== NOVA CATEGORIA ====================

async def category_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa o nome da nova categoria"""
    if not update.message or not update.message.text:
        return ConversationStates.CATEGORY_NAME
    
    # Cancelar
    if update.message.text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await finance_menu(update, context)
    
    try:
        category_name = update.message.text.strip()
        
        if not category_name:
            await update.message.reply_text("❌ Nome não pode estar vazio")
            return ConversationStates.CATEGORY_NAME
        
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            transaction_type = context.user_data['transaction_type']
            
            # Criar categoria
            category = CategoryService.create_category(
                session=session,
                user=user,
                name=category_name,
                category_type=transaction_type
            )
            
            # Continuar com a transação usando a nova categoria
            context.user_data['category_id'] = category.id
            
            # Criar transação
            transaction = TransactionService.create_transaction(
                session=session,
                user=user,
                category=category,
                amount=context.user_data['amount'],
                description=context.user_data['description'],
                payment_method=context.user_data['payment_method'],
                date=context.user_data['date'],
                transaction_type=transaction_type
            )
            
            # Mensagem de sucesso
            emoji = Emojis.MONEY_IN if transaction_type == TransactionType.INCOME else Emojis.MONEY_OUT
            
            success_message = (
                f"✅ Categoria '{category_name}' criada!\n\n" +
                Messages.SUCCESS_TRANSACTION.format(
                    emoji=emoji,
                    description=transaction.description,
                    amount=transaction.amount,
                    category=category.name,
                    date=transaction.date.strftime('%d/%m/%Y')
                )
            )
            
            await update.message.reply_text(
                success_message,
                parse_mode='Markdown',
                reply_markup=Keyboards.finance_menu()
            )
            
            # Limpar dados temporários
            context.user_data.clear()
            
            return ConversationStates.FINANCE_MENU
            
    except ValueError as e:
        await update.message.reply_text(f"❌ {str(e)}")
        return ConversationStates.CATEGORY_NAME
    except Exception as e:
        logger.error(f"Erro ao criar categoria: {e}")
        await update.message.reply_text(Messages.ERROR_SAVE_FAILED)
        context.user_data.clear()
        return await finance_menu(update, context)