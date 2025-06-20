"""
Finance Bot - Bot de Finanças Pessoais para Telegram
Sistema principal melhorado com recursos avançados
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional
import traceback

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

from config import Config
from database import init_database, db
from utils import app_cache

# Importar serviços
from services import UserService, TransactionService
try:
    from services.report_service import get_formatted_monthly_report, clear_user_cache
except ImportError:
    # Fallback se não conseguir importar
    def get_formatted_monthly_report(session, user, year=None, month=None):
        return "📊 Relatório não disponível"
    
    def clear_user_cache(user_id):
        pass

# Importar handlers
from handlers.main import (
    start_command, main_menu_handler,
    help_command, cancel_command
)
from handlers.finance import (
    finance_menu_handler,
    transaction_type_callback, transaction_amount_handler,
    transaction_description_handler, transaction_payment_method_handler,
    transaction_date_handler, transaction_category_handler,
    category_name_handler
)
from handlers.investment import (
    investment_menu_handler,
    investment_type_handler, investment_ticker_handler,
    investment_quantity_handler, investment_price_handler,
    investment_confirm_handler
)
from handlers.settings import (
    settings_menu_handler,
    settings_callback_handler
)

# Importar callbacks se disponível
try:
    from handlers.callbacks import CallbackRouter
except ImportError:
    # Fallback se não tiver callbacks
    class CallbackRouter:
        @staticmethod
        async def route_callback(update, context):
            query = update.callback_query
            if query:
                await query.answer("Callback não implementado")
            return

from states import ConversationStates, CallbackActions


# Configurar logging avançado
def setup_logging():
    """Configura sistema de logging avançado"""
    
    # Criar formatador personalizado
    class ColoredFormatter(logging.Formatter):
        """Formatador com cores para diferentes níveis"""
        
        COLORS = {
            'DEBUG': '\033[36m',    # Cyan
            'INFO': '\033[32m',     # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',    # Red
            'CRITICAL': '\033[35m', # Magenta
        }
        RESET = '\033[0m'
        
        def format(self, record):
            if hasattr(record, 'levelname'):
                color = self.COLORS.get(record.levelname, '')
                record.levelname = f"{color}{record.levelname}{self.RESET}"
            return super().format(record)
    
    # Configurar logger raiz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # Remover handlers existentes
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Handler para console
    console_handler = logging.StreamHandler(sys.stdout)
    if sys.stdout.isatty():  # Se é um terminal, usar cores
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Handler para arquivo (se configurado)
    if Config.LOG_FILE:
        try:
            log_file_path = Path(Config.LOG_FILE)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(Config.LOG_FILE, encoding='utf-8')
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logging.error(f"Erro ao configurar log em arquivo: {e}")
    
    # Configurar loggers específicos
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


class BotApplication:
    """Classe principal do bot com recursos avançados"""
    
    def __init__(self):
        self.application: Optional[Application] = None
        self.is_running = False
        self.shutdown_event = asyncio.Event()
    
    async def initialize(self) -> None:
        """Inicializa o bot e todos os componentes"""
        try:
            logger.info("🚀 Inicializando Finance Bot...")
            
            # Validar configurações
            Config.validate()
            logger.info("✅ Configurações validadas")
            
            # Inicializar banco de dados
            init_database()
            logger.info("✅ Banco de dados inicializado")
            
            # Criar aplicação do bot
            self.application = self._create_application()
            logger.info("✅ Aplicação do bot criada")
            
            # Configurar comandos do bot
            await self._setup_bot_commands()
            logger.info("✅ Comandos do bot configurados")
            
            # Configurar handlers de sistema
            self._setup_system_handlers()
            logger.info("✅ Sistema inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização: {e}")
            logger.error(traceback.format_exc())
            raise
    
    def _create_application(self) -> Application:
        """Cria e configura a aplicação do bot"""
        
        # Configurações avançadas do bot
        app_builder = Application.builder()
        app_builder.token(Config.BOT_TOKEN)
        app_builder.concurrent_updates(True)  # Permitir updates concorrentes
        app_builder.connection_pool_size(10)  # Pool de conexões
        app_builder.read_timeout(30)
        app_builder.write_timeout(30)
        app_builder.connect_timeout(30)
        app_builder.pool_timeout(20)
        
        application = app_builder.build()
        
        # Configurar conversation handler principal
        conv_handler = self._create_conversation_handler()
        application.add_handler(conv_handler)
        
        # Handlers de comandos globais
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("cancel", cancel_command))
        
        # Handlers especiais
        application.add_handler(CommandHandler("status", self._status_command))
        application.add_handler(CommandHandler("clear_cache", self._clear_cache_command))
        
        # Handler principal de callbacks
        application.add_handler(CallbackQueryHandler(CallbackRouter.route_callback))
        
        # Handler de erro global
        application.add_error_handler(self._advanced_error_handler)
        
        # Configurar callbacks do ciclo de vida
        application.post_init = self._post_init
        application.post_shutdown = self._post_shutdown
        
        return application
    
    def _create_conversation_handler(self) -> ConversationHandler:
        """Cria o conversation handler principal"""
        
        return ConversationHandler(
            entry_points=[
                CommandHandler("start", start_command),
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)
            ],
            states={
                # Menus principais
                ConversationStates.MAIN_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler)
                ],
                
                # Menu de finanças
                ConversationStates.FINANCE_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, finance_menu_handler)
                ],
                
                # Fluxo de transação
                ConversationStates.TRANSACTION_TYPE: [
                    CallbackQueryHandler(
                        transaction_type_callback,
                        pattern=f"^(transaction_|{CallbackActions.CANCEL}).*"
                    )
                ],
                ConversationStates.TRANSACTION_AMOUNT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_amount_handler)
                ],
                ConversationStates.TRANSACTION_DESCRIPTION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_description_handler)
                ],
                ConversationStates.TRANSACTION_PAYMENT_METHOD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_payment_method_handler)
                ],
                ConversationStates.TRANSACTION_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_date_handler)
                ],
                ConversationStates.TRANSACTION_CATEGORY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, transaction_category_handler)
                ],
                ConversationStates.CATEGORY_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, category_name_handler)
                ],
                
                # Menu de investimentos
                ConversationStates.INVESTMENT_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, investment_menu_handler)
                ],
                
                # Fluxo de investimento
                ConversationStates.INVESTMENT_TYPE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, investment_type_handler)
                ],
                ConversationStates.INVESTMENT_TICKER: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, investment_ticker_handler)
                ],
                ConversationStates.INVESTMENT_QUANTITY: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, investment_quantity_handler)
                ],
                ConversationStates.INVESTMENT_PRICE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, investment_price_handler)
                ],
                ConversationStates.INVESTMENT_CONFIRM: [
                    CallbackQueryHandler(investment_confirm_handler)
                ],
                
                # Menu de configurações
                ConversationStates.SETTINGS_MENU: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, settings_menu_handler),
                    CallbackQueryHandler(settings_callback_handler)
                ],
                
                # Estados especiais
                ConversationStates.WAITING_CONFIRMATION: [
                    CallbackQueryHandler(CallbackRouter.route_callback)
                ],
                ConversationStates.SHOWING_HELP: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler),
                    CallbackQueryHandler(CallbackRouter.route_callback)
                ],
            },
            fallbacks=[
                CommandHandler("cancel", cancel_command),
                CommandHandler("start", start_command),
                CommandHandler("help", help_command),
                MessageHandler(filters.COMMAND, self._unknown_command)
            ],
            allow_reentry=True,
            name="main_conversation",
            persistent=False,
            per_chat=True,
            per_user=True,
            per_message=False,
            conversation_timeout=1800,  # 30 minutos
            block=False  # Não bloquear processamento
        )
    
    async def _setup_bot_commands(self) -> None:
        """Configura comandos do bot no Telegram"""
        commands = [
            BotCommand("start", "Iniciar o bot"),
            BotCommand("help", "Obter ajuda"),
            BotCommand("cancel", "Cancelar operação atual"),
            BotCommand("status", "Status do bot"),
            BotCommand("clear_cache", "Limpar cache (admin)"),
        ]
        
        await self.application.bot.set_my_commands(commands)
        logger.info("✅ Comandos do bot configurados")
    
    def _setup_system_handlers(self) -> None:
        """Configura handlers de sistema"""
        
        # Handler para sinais do sistema
        def signal_handler(signum, frame):
            logger.info(f"Sinal {signum} recebido. Iniciando shutdown...")
            self.shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    async def _post_init(self, application: Application) -> None:
        """Executado após inicialização do bot"""
        try:
            bot_info = await application.bot.get_me()
            logger.info(f"🤖 Bot inicializado: @{bot_info.username} (ID: {bot_info.id})")
            
            # Verificar se o bot tem as permissões necessárias
            await self._check_bot_permissions()
            
            # Limpar cache antigo
            app_cache.clear()
            
            logger.info("🎉 Finance Bot está pronto para uso!")
            
        except Exception as e:
            logger.error(f"Erro no post_init: {e}")
    
    async def _post_shutdown(self, application: Application) -> None:
        """Executado antes do shutdown"""
        try:
            logger.info("🛑 Iniciando shutdown do bot...")
            
            # Limpar caches
            app_cache.clear()
            clear_user_cache(-1)  # Limpar todos os caches
            
            # Fechar conexões do banco
            db.cleanup()
            
            logger.info("✅ Shutdown concluído com sucesso")
            
        except Exception as e:
            logger.error(f"Erro no shutdown: {e}")
    
    async def _check_bot_permissions(self) -> None:
        """Verifica se o bot tem as permissões necessárias"""
        try:
            # Teste básico de envio de mensagem
            # Em produção, você poderia enviar para um grupo de admin
            pass
        except Exception as e:
            logger.warning(f"Aviso sobre permissões: {e}")
    
    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando de status do bot"""
        try:
            with db.get_session() as session:
                # Estatísticas básicas
                from models import User, Transaction, Investment
                
                user_count = session.query(User).count()
                transaction_count = session.query(Transaction).count()
                investment_count = session.query(Investment).count()
            
            uptime = "Em execução"  # Calcular uptime real se necessário
            
            status_message = f"""
🤖 *Status do Finance Bot*

📊 *Estatísticas:*
• Usuários: {user_count:,}
• Transações: {transaction_count:,}
• Investimentos: {investment_count:,}

⚙️ *Sistema:*
• Uptime: {uptime}
• Cache: {len(app_cache.cache)} itens
• Versão: 2.0.0

🔧 *Configurações:*
• Ambiente: {Config.ENVIRONMENT}
• Debug: {Config.DEBUG}
• Log Level: {Config.LOG_LEVEL}
"""
            
            await update.message.reply_text(
                status_message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Erro no comando status: {e}")
            await update.message.reply_text("❌ Erro ao obter status")
    
    async def _clear_cache_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Comando para limpar cache (admin only)"""
        try:
            # Verificação básica de admin (melhorar em produção)
            user_id = update.effective_user.id
            
            # Lista de admins (configurar em produção)
            admin_ids = [123456789]  # Substituir por IDs reais
            
            if user_id not in admin_ids:
                await update.message.reply_text("❌ Comando apenas para administradores")
                return
            
            # Limpar caches
            items_cleared = len(app_cache.cache)
            app_cache.clear()
            clear_user_cache(user_id)
            
            await update.message.reply_text(
                f"✅ Cache limpo! {items_cleared} itens removidos."
            )
            
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            await update.message.reply_text("❌ Erro ao limpar cache")
    
    async def _unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Handler para comandos desconhecidos"""
        command = update.message.text
        logger.warning(f"Comando desconhecido: {command} do usuário {update.effective_user.id}")
        
        await update.message.reply_text(
            f"❓ Comando `{command}` não reconhecido.\n\n"
            "Use /help para ver comandos disponíveis.",
            parse_mode='Markdown'
        )
        
        return ConversationStates.MAIN_MENU
    
    async def _advanced_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler avançado de erros"""
        try:
            error = context.error
            logger.error(f"Erro no bot: {error}")
            logger.error(traceback.format_exc())
            
            # Tentar notificar o usuário se possível
            if isinstance(update, Update) and update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "❌ Ocorreu um erro inesperado.\n\n"
                        "Por favor, tente novamente ou use /start para reiniciar."
                    )
                except Exception as notify_error:
                    logger.error(f"Erro ao notificar usuário: {notify_error}")
            
            # Em desenvolvimento, re-raise para debugging
            if Config.DEBUG:
                raise error
                
        except Exception as handler_error:
            logger.critical(f"Erro no error handler: {handler_error}")
    
    async def run(self) -> None:
        """Executa o bot"""
        try:
            await self.initialize()
            
            logger.info("🚀 Finance Bot iniciando...")
            print(f"""
╔═══════════════════════════════════════╗
║           FINANCE BOT v2.0            ║
║                                       ║
║  🤖 Bot iniciado com sucesso!         ║
║  📱 Pressione Ctrl+C para parar       ║
║  🔧 Ambiente: {Config.ENVIRONMENT:<19} ║
║  📊 Debug: {str(Config.DEBUG):<22} ║
╚═══════════════════════════════════════╝
""")
            
            self.is_running = True
            
            # Iniciar bot com polling
            await self.application.initialize()
            await self.application.start()
            
            # Executar polling até receber sinal de shutdown
            await self.application.updater.start_polling(
                allowed_updates=None,
                drop_pending_updates=True
            )
            
            # Aguardar sinal de shutdown
            await self.shutdown_event.wait()
            
        except KeyboardInterrupt:
            logger.info("👋 Shutdown solicitado pelo usuário")
        except Exception as e:
            logger.error(f"❌ Erro crítico: {e}")
            logger.error(traceback.format_exc())
        finally:
            await self._shutdown()
    
    async def _shutdown(self) -> None:
        """Processo de shutdown do bot"""
        try:
            if self.is_running:
                logger.info("🛑 Parando o bot...")
                self.is_running = False
                
                if self.application:
                    await self.application.updater.stop()
                    await self.application.stop()
                    await self.application.shutdown()
                
                logger.info("✅ Bot parado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro no shutdown: {e}")


async def main():
    """Função principal"""
    try:
        # Configurar logging
        setup_logging()
        
        # Criar e executar aplicação do bot
        bot_app = BotApplication()
        await bot_app.run()
        
    except KeyboardInterrupt:
        logger.info("👋 Shutdown solicitado pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro crítico na inicialização: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        logger.info("🏁 Finance Bot finalizado")


if __name__ == '__main__':
    try:
        # Verificar versão do Python
        if sys.version_info < (3, 8):
            print("❌ Python 3.8+ é necessário")
            sys.exit(1)
        
        # Executar bot
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n👋 Bot interrompido pelo usuário")
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
        sys.exit(1)