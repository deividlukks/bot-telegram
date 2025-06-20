"""
Handlers para funcionalidades de investimentos
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from models import InvestorProfile
from datetime import datetime
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes

from config import Config, Messages, Emojis
from database import db
from keyboards import Keyboards
from models import InvestmentType, Investment
from services import InvestmentService, UserService, TransactionService
from states import ConversationStates, INVESTMENT_TYPE_MAP
from utils import (
    parse_amount, format_currency, parse_date,
    get_user_from_update, validate_amount, is_valid_ticker,
    format_percentage, ProgressBar, EmojiHealth
)

logger = logging.getLogger(__name__)

async def investment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa callbacks do menu de investimentos"""
    query = update.callback_query
    await query.answer()
    
    # Implementação do artifact callback-handlers-py
    # ...

async def profile_test_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa resposta do teste de perfil"""
    query = update.callback_query
    await query.answer()
    
    # Implementação do artifact callback-handlers-py
    # ...

async def investment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe o menu de investimentos"""
    try:
        # Verificar se usuário tem perfil de investidor
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            if not user.investor_profile:
                await update.message.reply_text(
                    "*📈 Bem-vindo aos Investimentos!*\n\n"
                    "Antes de começar, preciso conhecer seu perfil de investidor.\n\n"
                    "Isso me ajudará a fornecer sugestões adequadas ao seu perfil de risco.\n\n"
                    "Vamos fazer um teste rápido?",
                    parse_mode='Markdown',
                    reply_markup=Keyboards.yes_no("Começar Teste", "Mais Tarde")
                )
                context.user_data['awaiting_profile_test'] = True
                return ConversationStates.INVESTMENT_MENU
        
        await update.message.reply_text(
            "*📈 Gestão de Investimentos*\n\n"
            "Gerencie sua carteira e acompanhe seus investimentos:",
            parse_mode='Markdown',
            reply_markup=Keyboards.investment_menu()
        )
        return ConversationStates.INVESTMENT_MENU
        
    except Exception as e:
        logger.error(f"Erro ao exibir menu de investimentos: {e}")
        await update.message.reply_text(Messages.ERROR_GENERIC)
        return ConversationStates.MAIN_MENU


async def investment_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa as opções do menu de investimentos"""
    if not update.message or not update.message.text:
        return ConversationStates.INVESTMENT_MENU
    
    text = update.message.text
    
    # Se está aguardando resposta do teste de perfil
    if context.user_data.get('awaiting_profile_test'):
        # Implementar teste de perfil aqui
        context.user_data.pop('awaiting_profile_test', None)
        return ConversationStates.INVESTMENT_MENU
    
    if text == '📰 Notícias':
        return await show_market_news(update, context)
    
    elif text == '💼 Minha Carteira':
        return await show_portfolio(update, context)
    
    elif text == '➕ Comprar':
        return await start_buy_investment(update, context)
    
    elif text == '➖ Vender':
        return await start_sell_investment(update, context)
    
    elif text == '💵 Dividendos':
        return await show_dividends(update, context)
    
    elif text == '🎯 Oportunidades':
        return await show_opportunities(update, context)
    
    elif text == '📊 Análise':
        return await show_portfolio_analysis(update, context)
    
    elif text == '🔄 Rebalancear':
        return await show_rebalancing(update, context)
    
    elif text == f'{Emojis.BACK} Menu Principal':
        from .main import main_menu
        return await main_menu(update, context)
    
    return ConversationStates.INVESTMENT_MENU


# ==================== COMPRA DE INVESTIMENTO ====================

async def start_buy_investment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia o processo de compra de investimento"""
    await update.message.reply_text(
        "*➕ Nova Compra de Investimento*\n\n"
        "Que tipo de ativo você deseja comprar?",
        parse_mode='Markdown',
        reply_markup=Keyboards.investment_types()
    )
    return ConversationStates.INVESTMENT_TYPE


async def investment_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa o tipo de investimento"""
    if not update.message or not update.message.text:
        return ConversationStates.INVESTMENT_TYPE
    
    text = update.message.text
    
    # Cancelar
    if text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await investment_menu(update, context)
    
    # Mapear tipo
    investment_type = INVESTMENT_TYPE_MAP.get(text)
    if not investment_type:
        await update.message.reply_text(
            "❌ Tipo de investimento inválido. Escolha uma opção do menu."
        )
        return ConversationStates.INVESTMENT_TYPE
    
    context.user_data['investment_type'] = investment_type
    
    # Pedir ticker
    examples = {
        'stock': "PETR4, VALE3, ITUB4",
        'fii': "MXRF11, HGLG11, XPLG11",
        'crypto': "BTC, ETH, ADA",
        'etf': "IVVB11, BOVA11, SMAL11",
        'fixed': "LTN, NTN-B, CDB",
        'other': "COE, LC, Debenture"
    }
    
    await update.message.reply_text(
        f"*Tipo:* {text}\n\n"
        f"Digite o código/ticker do ativo:\n"
        f"_Exemplos: {examples.get(investment_type, 'CÓDIGO')}_",
        parse_mode='Markdown',
        reply_markup=Keyboards.cancel_only()
    )
    
    return ConversationStates.INVESTMENT_TICKER


async def investment_ticker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa o ticker do investimento"""
    if not update.message or not update.message.text:
        return ConversationStates.INVESTMENT_TICKER
    
    text = update.message.text.strip()
    
    # Cancelar
    if text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await investment_menu(update, context)
    
    # Validar ticker
    ticker = text.upper()
    if not is_valid_ticker(ticker):
        await update.message.reply_text(
            "❌ Ticker inválido. Use apenas letras e números (3-10 caracteres)."
        )
        return ConversationStates.INVESTMENT_TICKER
    
    context.user_data['ticker'] = ticker
    
    # Pedir quantidade
    await update.message.reply_text(
        f"*Ativo:* {ticker}\n\n"
        "Digite a quantidade que deseja comprar:",
        parse_mode='Markdown',
        reply_markup=Keyboards.cancel_only()
    )
    
    return ConversationStates.INVESTMENT_QUANTITY


async def investment_quantity_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a quantidade do investimento"""
    if not update.message or not update.message.text:
        return ConversationStates.INVESTMENT_QUANTITY
    
    text = update.message.text
    
    # Cancelar
    if text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await investment_menu(update, context)
    
    try:
        # Parsear quantidade
        quantity = parse_amount(text)
        
        if quantity <= 0:
            await update.message.reply_text(
                "❌ A quantidade deve ser maior que zero."
            )
            return ConversationStates.INVESTMENT_QUANTITY
        
        context.user_data['quantity'] = quantity
        
        # Pedir preço
        await update.message.reply_text(
            f"*Quantidade:* {quantity:.4f}\n\n"
            "Digite o preço unitário de compra:",
            parse_mode='Markdown',
            reply_markup=Keyboards.cancel_only()
        )
        
        return ConversationStates.INVESTMENT_PRICE
        
    except (ValueError, InvalidOperation):
        await update.message.reply_text(
            "❌ Quantidade inválida. Digite apenas números."
        )
        return ConversationStates.INVESTMENT_QUANTITY


async def investment_price_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa o preço do investimento"""
    if not update.message or not update.message.text:
        return ConversationStates.INVESTMENT_PRICE
    
    text = update.message.text
    
    # Cancelar
    if text == f'{Emojis.ERROR} Cancelar':
        await update.message.reply_text(Messages.CANCELLED)
        context.user_data.clear()
        return await investment_menu(update, context)
    
    try:
        # Parsear preço
        price = parse_amount(text)
        
        if price <= 0:
            await update.message.reply_text(
                "❌ O preço deve ser maior que zero."
            )
            return ConversationStates.INVESTMENT_PRICE
        
        context.user_data['price'] = price
        
        # Calcular total
        quantity = context.user_data['quantity']
        total = quantity * price
        
        # Mostrar confirmação
        from states import INVESTMENT_TYPE_DISPLAY
        type_display = INVESTMENT_TYPE_DISPLAY.get(
            context.user_data['investment_type'],
            context.user_data['investment_type']
        )
        
        confirmation = f"""
*📋 Confirmar Compra*

*Tipo:* {type_display}
*Ativo:* {context.user_data['ticker']}
*Quantidade:* {quantity:.4f}
*Preço Unitário:* {format_currency(price)}
*Valor Total:* {format_currency(total)}

Confirma a operação?
"""
        
        await update.message.reply_text(
            confirmation,
            parse_mode='Markdown',
            reply_markup=Keyboards.yes_no()
        )
        
        return ConversationStates.INVESTMENT_CONFIRM
        
    except (ValueError, InvalidOperation):
        await update.message.reply_text(Messages.ERROR_INVALID_AMOUNT)
        return ConversationStates.INVESTMENT_PRICE


async def investment_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa a confirmação da compra"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "no":
        await query.edit_message_text(Messages.CANCELLED)
        context.user_data.clear()
        return await investment_menu(query, context)
    
    try:
        with db.get_session() as session:
            user = get_user_from_update(query, session)
            
            # Criar investimento
            investment = InvestmentService.create_investment(
                session=session,
                user=user,
                ticker=context.user_data['ticker'],
                investment_type=InvestmentType[context.user_data['investment_type'].upper()],
                quantity=context.user_data['quantity'],
                price=context.user_data['price'],
                purchase_date=datetime.now()
            )
            
            # Calcular total
            total = investment.quantity * investment.avg_price
            
            success_message = Messages.SUCCESS_INVESTMENT.format(
                ticker=investment.ticker,
                type=investment.type.value,
                quantity=investment.quantity,
                price=investment.avg_price,
                total=total
            )
            
            await query.edit_message_text(
                success_message,
                parse_mode='Markdown'
            )
            
            # Enviar menu
            await query.message.reply_text(
                "O que deseja fazer agora?",
                reply_markup=Keyboards.investment_menu()
            )
            
            context.user_data.clear()
            return ConversationStates.INVESTMENT_MENU
            
    except Exception as e:
        logger.error(f"Erro ao criar investimento: {e}")
        await query.edit_message_text(Messages.ERROR_SAVE_FAILED)
        context.user_data.clear()
        
        await query.message.reply_text(
            "Voltando ao menu...",
            reply_markup=Keyboards.investment_menu()
        )
        return ConversationStates.INVESTMENT_MENU


# ==================== VENDA DE INVESTIMENTO ====================

async def start_sell_investment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia o processo de venda de investimento"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Buscar investimentos ativos
            investments = session.query(Investment).filter(
                Investment.user_id == user.id,
                Investment.is_active == True
            ).all()
            
            if not investments:
                await update.message.reply_text(
                    "❌ Você não possui investimentos para vender.\n\n"
                    "Use '➕ Comprar' para adicionar ativos à sua carteira.",
                    reply_markup=Keyboards.investment_menu()
                )
                return ConversationStates.INVESTMENT_MENU
            
            # Montar lista de investimentos
            keyboard = []
            for inv in investments:
                button_text = f"{inv.ticker} ({inv.current_quantity:.4f})"
                keyboard.append([button_text])
            
            keyboard.append([f'{Emojis.ERROR} Cancelar'])
            
            await update.message.reply_text(
                "*➖ Vender Investimento*\n\n"
                "Selecione o ativo que deseja vender:",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            
            # Armazenar investimentos para referência
            context.user_data['available_investments'] = {
                inv.ticker: inv.id for inv in investments
            }
            
            return ConversationStates.SELL_SELECT
            
    except Exception as e:
        logger.error(f"Erro ao listar investimentos: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.investment_menu()
        )
        return ConversationStates.INVESTMENT_MENU


# ==================== VISUALIZAÇÕES ====================

async def show_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe a carteira de investimentos"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Obter resumo da carteira
            portfolio = InvestmentService.get_portfolio_summary(session, user)
            
            if not portfolio['investments']:
                await update.message.reply_text(
                    "*💼 Minha Carteira*\n\n"
                    "Você ainda não possui investimentos.\n\n"
                    "Use '➕ Comprar' para começar a investir!",
                    parse_mode='Markdown',
                    reply_markup=Keyboards.investment_menu()
                )
                return ConversationStates.INVESTMENT_MENU
            
            # Montar mensagem
            message = "*💼 Minha Carteira*\n\n"
            
            # Resumo geral
            profit_emoji = EmojiHealth.get_balance_emoji(portfolio['total_profit'])
            
            message += f"*📊 Resumo Geral:*\n"
            message += f"• Total Investido: {format_currency(portfolio['total_invested'])}\n"
            message += f"• Valor Atual: {format_currency(portfolio['total_current'])}\n"
            message += f"• Lucro/Prejuízo: {profit_emoji} {format_currency(portfolio['total_profit'])}\n"
            message += f"• Rentabilidade: {format_percentage(portfolio['profit_percentage'])}\n\n"
            
            # Distribuição por tipo
            if portfolio['by_type']:
                message += "*🎯 Distribuição:*\n"
                for inv_type, data in portfolio['by_type'].items():
                    message += f"• {inv_type}: {format_currency(data['total_invested'])} ({data['percentage']:.1f}%)\n"
                message += "\n"
            
            # Listar investimentos
            message += "*📈 Ativos:*\n"
            for inv in portfolio['investments']:
                # Simular preço atual (em produção, buscar de API)
                import random
                variation = random.uniform(-5, 5) / 100
                current_price = float(inv.avg_price) * (1 + variation)
                current_value = float(inv.current_quantity) * current_price
                invested_value = float(inv.current_quantity) * float(inv.avg_price)
                
                profit = current_value - invested_value
                profit_pct = (profit / invested_value * 100) if invested_value > 0 else 0
                
                emoji = "🟢" if profit >= 0 else "🔴"
                
                message += f"\n*{inv.ticker}*\n"
                message += f"  Qtd: {inv.current_quantity:.4f} | PM: {format_currency(inv.avg_price)}\n"
                message += f"  Atual: {format_currency(current_value)} {emoji} ({profit_pct:+.2f}%)\n"
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=Keyboards.investment_menu()
            )
            
    except Exception as e:
        logger.error(f"Erro ao exibir carteira: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.investment_menu()
        )
    
    return ConversationStates.INVESTMENT_MENU


async def show_market_news(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe notícias do mercado"""
    # Simulação de notícias - em produção, buscar de API real
    news = """
*📰 Notícias do Mercado*

*Hoje, {}*

📈 *Ibovespa fecha em alta de 1,2%*
O principal índice da bolsa brasileira encerrou aos 118.523 pontos.

💵 *Dólar recua 0,8% a R$ 5,45*
Moeda americana teve queda após dados positivos da economia.

🏦 *Selic mantida em 11,75%*
Copom decidiu manter taxa básica de juros inalterada.

📊 *Inflação mensal fica em 0,4%*
IPCA veio dentro das expectativas do mercado.

💰 *Bitcoin sobe 3% e volta aos US$ 45.000*
Criptomoeda se recupera após correção recente.

🏢 *Petrobras anuncia dividendos de R$ 2,87 por ação*
Empresa distribui R$ 37,5 bilhões aos acionistas.

_Última atualização: {} (horário de Brasília)_
""".format(
        datetime.now().strftime('%d/%m/%Y'),
        datetime.now().strftime('%H:%M')
    )
    
    await update.message.reply_text(
        news,
        parse_mode='Markdown',
        reply_markup=Keyboards.investment_menu()
    )
    
    return ConversationStates.INVESTMENT_MENU


async def show_dividends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe calendário de dividendos"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Buscar investimentos que pagam dividendos
            investments = session.query(Investment).filter(
                Investment.user_id == user.id,
                Investment.is_active == True,
                Investment.type.in_([InvestmentType.STOCK, InvestmentType.FII])
            ).all()
            
            if not investments:
                await update.message.reply_text(
                    "*💵 Próximos Dividendos*\n\n"
                    "Você não possui ativos que pagam dividendos.\n\n"
                    "Invista em ações ou FIIs para receber dividendos!",
                    parse_mode='Markdown',
                    reply_markup=Keyboards.investment_menu()
                )
                return ConversationStates.INVESTMENT_MENU
            
            # Simular dividendos (em produção, buscar de API)
            message = "*💵 Próximos Dividendos*\n\n"
            total_dividends = Decimal('0')
            
            from datetime import timedelta
            
            for inv in investments:
                # Simular data e valor
                dividend_date = datetime.now() + timedelta(days=random.randint(5, 30))
                dividend_per_share = float(inv.avg_price) * random.uniform(0.002, 0.01)
                dividend_total = float(inv.current_quantity) * dividend_per_share
                total_dividends += Decimal(str(dividend_total))
                
                message += f"*{inv.ticker}*\n"
                message += f"  Data: {dividend_date.strftime('%d/%m/%Y')}\n"
                message += f"  Valor/cota: R$ {dividend_per_share:.4f}\n"
                message += f"  Total: {format_currency(dividend_total)}\n\n"
            
            message += f"*Total Previsto:* {format_currency(total_dividends)}"
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=Keyboards.investment_menu()
            )
            
    except Exception as e:
        logger.error(f"Erro ao exibir dividendos: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.investment_menu()
        )
    
    return ConversationStates.INVESTMENT_MENU


async def show_opportunities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe oportunidades de investimento"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Determinar perfil
            profile_messages = {
                'conservative': "conservador (baixo risco)",
                'moderate': "moderado (risco equilibrado)",
                'aggressive': "agressivo (alto risco)"
            }
            
            profile_desc = profile_messages.get(
                user.investor_profile.value,
                "moderado"
            )
            
            # Simular oportunidades baseadas no perfil
            opportunities = {
                'conservative': [
                    ("Tesouro Selic 2029", "Renda Fixa", "Rentabilidade: Selic + 0,15%", "🟢 Baixo Risco"),
                    ("CDB Banco Top 120% CDI", "Renda Fixa", "Vencimento em 2 anos", "🟢 Baixo Risco"),
                    ("MXRF11", "FII", "Dividend Yield: 0,85% a.m.", "🟡 Risco Moderado")
                ],
                'moderate': [
                    ("PETR4", "Ação", "P/L: 3,5 | DY: 15%", "🟡 Subvalorizada"),
                    ("IVVB11", "ETF", "S&P 500 em reais", "🟢 Diversificado"),
                    ("HGLG11", "FII", "Dividend Yield: 0,90% a.m.", "🟡 Boa Liquidez")
                ],
                'aggressive': [
                    ("MGLU3", "Ação", "Potencial de recuperação", "🔴 Alto Risco/Retorno"),
                    ("BTC", "Cripto", "Correção de -20% do topo", "🔴 Alta Volatilidade"),
                    ("HASH11", "ETF", "Tecnologia e Cripto", "🔴 Setor Volátil")
                ]
            }
            
            message = f"*🎯 Oportunidades de Investimento*\n\n"
            message += f"_Baseado no seu perfil {profile_desc}_\n\n"
            
            user_opportunities = opportunities.get(
                user.investor_profile.value,
                opportunities['moderate']
            )
            
            for i, (asset, type_, info, risk) in enumerate(user_opportunities, 1):
                message += f"{i}. *{asset}* ({type_})\n"
                message += f"   {info}\n"
                message += f"   {risk}\n\n"
            
            message += "_⚠️ Lembre-se: Toda decisão de investimento deve ser baseada em sua própria análise._"
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=Keyboards.investment_menu()
            )
            
    except Exception as e:
        logger.error(f"Erro ao exibir oportunidades: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.investment_menu()
        )
    
    return ConversationStates.INVESTMENT_MENU


async def show_portfolio_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe análise detalhada da carteira"""
    try:
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            portfolio = InvestmentService.get_portfolio_summary(session, user)
            
            if not portfolio['investments']:
                await update.message.reply_text(
                    "❌ Você precisa ter investimentos para ver a análise.",
                    reply_markup=Keyboards.investment_menu()
                )
                return ConversationStates.INVESTMENT_MENU
            
            # Análise de diversificação
            message = "*📊 Análise da Carteira*\n\n"
            
            # Score de diversificação
            num_assets = len(portfolio['investments'])
            num_types = len(portfolio['by_type'])
            
            diversification_score = min(100, (num_assets * 10) + (num_types * 20))
            div_emoji = EmojiHealth.get_score_emoji(diversification_score)
            
            message += f"*🎯 Diversificação:* {div_emoji} {diversification_score}/100\n"
            message += f"• {num_assets} ativos em {num_types} categorias\n\n"
            
            # Análise por tipo
            message += "*📈 Alocação Recomendada vs Atual:*\n"
            
            # Recomendações por perfil
            recommendations = {
                'conservative': {'fixed': 70, 'fii': 20, 'stock': 10},
                'moderate': {'fixed': 40, 'stock': 35, 'fii': 15, 'etf': 10},
                'aggressive': {'stock': 50, 'crypto': 20, 'etf': 20, 'fii': 10}
            }
            
            user_rec = recommendations.get(
                user.investor_profile.value,
                recommendations['moderate']
            )
            
            for asset_type, recommended_pct in user_rec.items():
                current_pct = portfolio['by_type'].get(asset_type, {}).get('percentage', 0)
                
                # Barra de progresso
                progress = ProgressBar.create(current_pct, recommended_pct, width=5)
                
                message += f"\n*{asset_type.upper()}*\n"
                message += f"Recomendado: {recommended_pct}%\n"
                message += f"Atual: {progress}\n"
            
            # Sugestões
            message += "\n*💡 Sugestões:*\n"
            
            # Analisar desvios
            for asset_type, recommended_pct in user_rec.items():
                current_pct = float(portfolio['by_type'].get(asset_type, {}).get('percentage', 0))
                diff = current_pct - recommended_pct
                
                if diff < -10:
                    message += f"• Aumentar posição em {asset_type.upper()}\n"
                elif diff > 10:
                    message += f"• Reduzir posição em {asset_type.upper()}\n"
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=Keyboards.investment_menu()
            )
            
    except Exception as e:
        logger.error(f"Erro na análise: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.investment_menu()
        )
    
    return ConversationStates.INVESTMENT_MENU


async def show_rebalancing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe sugestões de rebalanceamento"""
    await update.message.reply_text(
        "*🔄 Rebalanceamento de Carteira*\n\n"
        "_Esta funcionalidade será implementada em breve!_\n\n"
        "Aqui você poderá:\n"
        "• Ver sugestões de rebalanceamento\n"
        "• Calcular aportes otimizados\n"
        "• Manter sua alocação ideal\n"
        "• Reduzir riscos da carteira",
        parse_mode='Markdown',
        reply_markup=Keyboards.investment_menu()
    )
    return ConversationStates.INVESTMENT_MENU


# Importar ReplyKeyboardMarkup que estava faltando
from telegram import ReplyKeyboardMarkup
import random