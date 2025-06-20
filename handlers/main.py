"""
Handlers principais do bot
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes

from config import Messages, Emojis
from database import db
from keyboards import Keyboards
from services import UserService
from states import ConversationStates
from utils import get_user_from_update

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handler do comando /start"""
    try:
        # Obter ou criar usuário
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
        # Mensagem de boas-vindas
        welcome_message = Messages.WELCOME.format(
            name=update.effective_user.first_name or "Usuário"
        )
        
        await update.message.reply_text(
            welcome_message,
            parse_mode='Markdown',
            reply_markup=Keyboards.main_menu()
        )
        
        return ConversationStates.MAIN_MENU
        
    except Exception as e:
        logger.error(f"Erro no comando start: {e}")
        await update.message.reply_text(Messages.ERROR_GENERIC)
        return ConversationStates.MAIN_MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exibe o menu principal"""
    await update.message.reply_text(
        "Menu Principal:",
        reply_markup=Keyboards.main_menu()
    )
    return ConversationStates.MAIN_MENU


async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processa as opções do menu principal"""
    if not update.message or not update.message.text:
        return ConversationStates.MAIN_MENU
    
    text = update.message.text
    
    # Importar handlers específicos
    from .finance import finance_menu
    from .investment import investment_menu
    from .settings import settings_menu
    
    if text == '💰 Finanças Pessoais' or text == '/financas':
        return await finance_menu(update, context)
    
    elif text == '📈 Investimentos' or text == '/investimentos':
        return await investment_menu(update, context)
    
    elif text == '💹 Trading':
        await update.message.reply_text(
            "*💹 Módulo Trading*\n\n"
            "🔍 Análise Técnica em Tempo Real\n"
            "📊 Sinais de Day Trade\n"
            "💱 Forex e Criptomoedas\n\n"
            "_Este módulo será implementado em breve!_\n\n"
            "Fique atento às atualizações! 🚀",
            parse_mode='Markdown',
            reply_markup=Keyboards.main_menu()
        )
        return ConversationStates.MAIN_MENU
    
    elif text == '📊 Relatórios' or text == '/relatorios':
        return await generate_reports(update, context)
    
    elif text == '⚙️ Configurações' or text == '/configuracoes':
        return await settings_menu(update, context)
    
    elif text == '❓ Ajuda':
        return await help_command(update, context)
    
        # Se não reconheceu o comando, não faz nada ou envia uma mensagem de ajuda
    await update.message.reply_text(
        "Opção inválida. Por favor, use os botões do menu."
    )
    return ConversationStates.MAIN_MENU # Mantém o estado atual


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Comando de ajuda"""
    help_text = """
*🤖 Finance Bot - Central de Ajuda*

*📌 Comandos Principais:*
/start - Reiniciar o bot
/help - Esta mensagem de ajuda
/cancel - Cancelar operação atual
/financas - Ir para menu de finanças
/investimentos - Ir para menu de investimentos
/relatorios - Gerar relatórios
/configuracoes - Abrir configurações

*💰 Módulo de Finanças:*
• Registre receitas e despesas
• Categorize seus gastos
• Acompanhe seu saldo mensal
• Receba análises de saúde financeira
• Visualize relatórios detalhados

*📈 Módulo de Investimentos:*
• Registre compra e venda de ativos
• Acompanhe sua carteira
• Receba alertas de dividendos
• Análise de performance
• Sugestões baseadas em seu perfil

*💡 Dicas de Uso:*
• Use os botões do menu para navegar
• Valores podem usar vírgula ou ponto
• Datas devem estar no formato DD/MM/AAAA
• Você pode cancelar qualquer operação com /cancel

*🔧 Problemas Comuns:*
• *Valor inválido*: Use apenas números (ex: 150,50)
• *Data inválida*: Use DD/MM/AAAA
• *Bot travado*: Use /cancel ou /start

*📞 Suporte:*
Em caso de problemas, entre em contato:
@seu_usuario_suporte

*📚 Recursos Adicionais:*
• [Guia de Finanças Pessoais](https://exemplo.com/guia)
• [Canal de Dicas](https://t.me/canal_exemplo)
• [Grupo de Discussão](https://t.me/grupo_exemplo)
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown',
        disable_web_page_preview=True,
        reply_markup=Keyboards.main_menu()
    )
    
    return ConversationStates.MAIN_MENU


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela a operação atual e volta ao menu principal"""
    # Limpar dados do contexto
    context.user_data.clear()
    
    await update.message.reply_text(
        f"{Emojis.WARNING} Operação cancelada.\n\nVoltando ao menu principal...",
        reply_markup=Keyboards.main_menu()
    )
    
    return ConversationStates.MAIN_MENU


async def generate_reports(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Gera relatórios financeiros"""
    try:
        await update.message.reply_text(
            "📊 *Gerando seus relatórios...*",
            parse_mode='Markdown'
        )
        
        with db.get_session() as session:
            user = get_user_from_update(update, session)
            
            # Importar serviços necessários
            from services import TransactionService, InvestmentService
            from datetime import datetime
            
            # Obter dados do mês atual
            now = datetime.now()
            
            # Resumo financeiro
            financial_summary = TransactionService.get_monthly_summary(
                session, user, now.year, now.month
            )
            
            # Resumo de investimentos
            portfolio_summary = InvestmentService.get_portfolio_summary(
                session, user
            )
            
            # Score de saúde
            health_score, health_status = TransactionService.get_financial_health_score(
                session, user
            )
        
        # Montar relatório
        report = f"""
*📊 Relatório Completo - {now.strftime('%B/%Y')}*

*💰 Resumo Financeiro:*
• Receitas: {format_currency(financial_summary['total_income'])}
• Despesas: {format_currency(financial_summary['total_expenses'])}
• Saldo: {format_currency(financial_summary['balance'])}
• Taxa de Poupança: {financial_summary['savings_rate']:.1f}%

*🏥 Saúde Financeira:*
• Score: {health_score}/100
• Status: {health_status}

*📈 Carteira de Investimentos:*
• Total Investido: {format_currency(portfolio_summary['total_invested'])}
• Valor Atual: {format_currency(portfolio_summary['total_current'])}
• Rentabilidade: {portfolio_summary['profit_percentage']:.1f}%
"""
        
        # Adicionar breakdown por tipo de investimento
        if portfolio_summary['by_type']:
            report += "\n*Distribuição por Tipo:*\n"
            for inv_type, data in portfolio_summary['by_type'].items():
                report += f"• {inv_type}: {format_currency(data['total_invested'])} ({data['percentage']:.1f}%)\n"
        
        # TODO: Aqui você poderia gerar gráficos e enviá-los como imagens
        
        await update.message.reply_text(
            report,
            parse_mode='Markdown',
            reply_markup=Keyboards.main_menu()
        )
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatórios: {e}")
        await update.message.reply_text(
            Messages.ERROR_GENERIC,
            reply_markup=Keyboards.main_menu()
        )
    
    return ConversationStates.MAIN_MENU


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler global de erros"""
    logger.error(f"Exceção durante processamento: {context.error}", exc_info=context.error)
    
    # Tentar notificar o usuário
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                f"{Emojis.ERROR} Ocorreu um erro inesperado.\n\n"
                "Por favor, tente novamente ou use /start para reiniciar.",
                reply_markup=Keyboards.main_menu()
            )
    except Exception:
        # Se falhar ao notificar, apenas logar
        pass


# Importar format_currency que estava faltando
from utils import format_currency