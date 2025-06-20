"""
Configurações e constantes do Finance Bot
Versão melhorada com validações e melhor organização
"""
import os
from decimal import Decimal
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dotenv import load_dotenv
import logging

# Carregar variáveis de ambiente
load_dotenv()

# Diretório base do projeto
BASE_DIR = Path(__file__).resolve().parent

logger = logging.getLogger(__name__)


class Config:
    """Configurações da aplicação com validações aprimoradas"""
    
    # Bot
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    BOT_USERNAME: str = os.getenv('BOT_USERNAME', '@finance_bot')
    
    # Database
    DATABASE_URL: str = os.getenv(
        'DATABASE_URL', 
        f'sqlite:///{BASE_DIR}/data/finance_bot.db'
    )
    DATABASE_ECHO: bool = os.getenv('DATABASE_ECHO', 'false').lower() == 'true'
    DATABASE_POOL_SIZE: int = int(os.getenv('DATABASE_POOL_SIZE', '5'))
    DATABASE_MAX_OVERFLOW: int = int(os.getenv('DATABASE_MAX_OVERFLOW', '10'))
    DATABASE_POOL_TIMEOUT: int = int(os.getenv('DATABASE_POOL_TIMEOUT', '30'))
    
    # Ambiente
    ENVIRONMENT: str = os.getenv('ENVIRONMENT', 'development')
    DEBUG: bool = ENVIRONMENT == 'development'
    
    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: Optional[str] = os.getenv('LOG_FILE')
    LOG_FORMAT: str = os.getenv(
        'LOG_FORMAT', 
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    LOG_MAX_BYTES: int = int(os.getenv('LOG_MAX_BYTES', '10485760'))  # 10MB
    LOG_BACKUP_COUNT: int = int(os.getenv('LOG_BACKUP_COUNT', '5'))
    
    # Timezone
    DEFAULT_TIMEZONE: str = os.getenv('TIMEZONE', 'America/Sao_Paulo')
    
    # Redis (para cache e sessões)
    REDIS_URL: Optional[str] = os.getenv('REDIS_URL')
    REDIS_PASSWORD: Optional[str] = os.getenv('REDIS_PASSWORD')
    REDIS_DB: int = int(os.getenv('REDIS_DB', '0'))
    
    # APIs externas (opcional)
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    OPENAI_MAX_TOKENS: int = int(os.getenv('OPENAI_MAX_TOKENS', '1000'))
    
    ALPHA_VANTAGE_KEY: Optional[str] = os.getenv('ALPHA_VANTAGE_KEY')
    COINMARKETCAP_KEY: Optional[str] = os.getenv('COINMARKETCAP_KEY')
    
    # B3 API (para dados do mercado brasileiro)
    B3_API_KEY: Optional[str] = os.getenv('B3_API_KEY')
    
    # Webhook (para produção)
    WEBHOOK_URL: Optional[str] = os.getenv('WEBHOOK_URL')
    WEBHOOK_PORT: int = int(os.getenv('WEBHOOK_PORT', '8443'))
    WEBHOOK_LISTEN: str = os.getenv('WEBHOOK_LISTEN', '0.0.0.0')
    
    # Security
    SECRET_KEY: str = os.getenv('SECRET_KEY', 'change-me-in-production')
    ALLOWED_USERS: List[int] = [
        int(user_id) for user_id in os.getenv('ALLOWED_USERS', '').split(',')
        if user_id.strip().isdigit()
    ]
    
    # Limites e validações
    MAX_TRANSACTION_AMOUNT: Decimal = Decimal(os.getenv('MAX_TRANSACTION_AMOUNT', '1000000.00'))
    MIN_TRANSACTION_AMOUNT: Decimal = Decimal(os.getenv('MIN_TRANSACTION_AMOUNT', '0.01'))
    MAX_DESCRIPTION_LENGTH: int = int(os.getenv('MAX_DESCRIPTION_LENGTH', '255'))
    MAX_TRANSACTIONS_PER_PAGE: int = int(os.getenv('MAX_TRANSACTIONS_PER_PAGE', '20'))
    MAX_CATEGORIES_PER_USER: int = int(os.getenv('MAX_CATEGORIES_PER_USER', '50'))
    MAX_INVESTMENTS_PER_USER: int = int(os.getenv('MAX_INVESTMENTS_PER_USER', '100'))
    
    # Rate limiting
    RATE_LIMIT_MESSAGES: int = int(os.getenv('RATE_LIMIT_MESSAGES', '30'))
    RATE_LIMIT_WINDOW: int = int(os.getenv('RATE_LIMIT_WINDOW', '60'))  # seconds
    
    # Cache settings
    CACHE_TTL_SHORT: int = int(os.getenv('CACHE_TTL_SHORT', '300'))  # 5 minutes
    CACHE_TTL_MEDIUM: int = int(os.getenv('CACHE_TTL_MEDIUM', '1800'))  # 30 minutes
    CACHE_TTL_LONG: int = int(os.getenv('CACHE_TTL_LONG', '3600'))  # 1 hour
    
    # Feature flags
    AI_ENABLED: bool = bool(OPENAI_API_KEY)
    MARKET_DATA_ENABLED: bool = bool(ALPHA_VANTAGE_KEY or COINMARKETCAP_KEY or B3_API_KEY)
    NOTIFICATIONS_ENABLED: bool = os.getenv('NOTIFICATIONS_ENABLED', 'true').lower() == 'true'
    ANALYTICS_ENABLED: bool = os.getenv('ANALYTICS_ENABLED', 'true').lower() == 'true'
    CACHE_ENABLED: bool = bool(REDIS_URL)
    WEBHOOK_ENABLED: bool = bool(WEBHOOK_URL)
    
    # Backup settings
    BACKUP_ENABLED: bool = os.getenv('BACKUP_ENABLED', 'true').lower() == 'true'
    BACKUP_INTERVAL_HOURS: int = int(os.getenv('BACKUP_INTERVAL_HOURS', '24'))
    BACKUP_RETENTION_DAYS: int = int(os.getenv('BACKUP_RETENTION_DAYS', '30'))
    BACKUP_PATH: str = os.getenv('BACKUP_PATH', str(BASE_DIR / 'backups'))
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv('SENTRY_DSN')
    METRICS_ENABLED: bool = os.getenv('METRICS_ENABLED', 'false').lower() == 'true'
    
    @classmethod
    def validate(cls) -> None:
        """Valida as configurações essenciais"""
        errors = []
        
        # Validações obrigatórias
        if not cls.BOT_TOKEN:
            errors.append(
                "BOT_TOKEN não configurado. "
                "Configure a variável de ambiente BOT_TOKEN ou crie um arquivo .env"
            )
        
        # Validar limites de valor
        if cls.MIN_TRANSACTION_AMOUNT <= 0:
            errors.append("MIN_TRANSACTION_AMOUNT deve ser maior que zero")
        
        if cls.MAX_TRANSACTION_AMOUNT <= cls.MIN_TRANSACTION_AMOUNT:
            errors.append("MAX_TRANSACTION_AMOUNT deve ser maior que MIN_TRANSACTION_AMOUNT")
        
        # Validar limites de página
        if cls.MAX_TRANSACTIONS_PER_PAGE <= 0 or cls.MAX_TRANSACTIONS_PER_PAGE > 100:
            errors.append("MAX_TRANSACTIONS_PER_PAGE deve estar entre 1 e 100")
        
        # Validar rate limiting
        if cls.RATE_LIMIT_MESSAGES <= 0:
            errors.append("RATE_LIMIT_MESSAGES deve ser maior que zero")
        
        if cls.RATE_LIMIT_WINDOW <= 0:
            errors.append("RATE_LIMIT_WINDOW deve ser maior que zero")
        
        # Validar configurações de cache
        if cls.CACHE_TTL_SHORT <= 0:
            errors.append("CACHE_TTL_SHORT deve ser maior que zero")
        
        # Validar OpenAI
        if cls.AI_ENABLED and cls.OPENAI_MAX_TOKENS <= 0:
            errors.append("OPENAI_MAX_TOKENS deve ser maior que zero")
        
        # Validar webhook em produção
        if cls.ENVIRONMENT == 'production' and cls.WEBHOOK_ENABLED:
            if not cls.WEBHOOK_URL:
                errors.append("WEBHOOK_URL é obrigatório em produção")
            
            if cls.WEBHOOK_PORT <= 0 or cls.WEBHOOK_PORT > 65535:
                errors.append("WEBHOOK_PORT deve estar entre 1 e 65535")
        
        # Validar secret key em produção
        if cls.ENVIRONMENT == 'production' and cls.SECRET_KEY == 'change-me-in-production':
            errors.append("SECRET_KEY deve ser alterado em produção")
        
        # Se há erros, parar a aplicação
        if errors:
            error_msg = "Erros de configuração encontrados:\n" + "\n".join(f"- {error}" for error in errors)
            raise ValueError(error_msg)
        
        # Criar diretórios necessários
        cls._create_directories()
        
        logger.info("Configurações validadas com sucesso!")
    
    @classmethod
    def _create_directories(cls) -> None:
        """Cria diretórios necessários"""
        directories = [
            BASE_DIR / 'data',
            BASE_DIR / 'logs',
            cls.BACKUP_PATH
        ]
        
        if cls.LOG_FILE:
            directories.append(Path(cls.LOG_FILE).parent)
        
        for directory in directories:
            Path(directory).mkdir(exist_ok=True, parents=True)
    
    @classmethod
    def get_database_config(cls) -> Dict[str, any]:
        """Retorna configurações do banco de dados"""
        config = {
            'url': cls.DATABASE_URL,
            'echo': cls.DATABASE_ECHO,
        }
        
        # Configurações específicas para PostgreSQL
        if not cls.DATABASE_URL.startswith('sqlite'):
            config.update({
                'pool_size': cls.DATABASE_POOL_SIZE,
                'max_overflow': cls.DATABASE_MAX_OVERFLOW,
                'pool_timeout': cls.DATABASE_POOL_TIMEOUT,
                'pool_pre_ping': True,
            })
        
        return config
    
    @classmethod
    def get_redis_config(cls) -> Optional[Dict[str, any]]:
        """Retorna configurações do Redis"""
        if not cls.REDIS_URL:
            return None
        
        return {
            'url': cls.REDIS_URL,
            'password': cls.REDIS_PASSWORD,
            'db': cls.REDIS_DB,
            'decode_responses': True,
            'socket_connect_timeout': 5,
            'socket_timeout': 5,
            'retry_on_timeout': True,
        }
    
    @classmethod
    def is_user_allowed(cls, user_id: int) -> bool:
        """Verifica se o usuário tem permissão de uso"""
        # Se não há lista de usuários permitidos, todos podem usar
        if not cls.ALLOWED_USERS:
            return True
        
        return user_id in cls.ALLOWED_USERS


class Messages:
    """Mensagens do bot com melhor organização"""
    
    # Boas-vindas
    WELCOME = """
🎯 *Bem-vindo ao Finance Bot!*

Olá {name}! 

Sou seu assistente financeiro pessoal. Posso ajudá-lo a:

💰 Controlar suas finanças pessoais
📈 Gerenciar seus investimentos  
💹 Identificar oportunidades de trading
📊 Gerar relatórios e análises
🤖 Fornecer insights com IA

Escolha uma opção abaixo para começar:
"""
    
    WELCOME_RETURNING = """
🎯 *Bem-vindo de volta, {name}!*

Que bom ter você aqui novamente! 

Última atividade: {last_activity}
Transações este mês: {transactions_count}
Saldo atual: {current_balance}

O que vamos fazer hoje?
"""
    
    # Erros aprimorados
    ERROR_GENERIC = "❌ Ocorreu um erro inesperado. Tente novamente ou use /start para reiniciar."
    ERROR_INVALID_AMOUNT = "❌ Valor inválido. Digite apenas números (ex: 150.50 ou 150,50)"
    ERROR_AMOUNT_TOO_HIGH = "❌ Valor muito alto. O limite máximo é {limit}"
    ERROR_AMOUNT_TOO_LOW = "❌ Valor muito baixo. O mínimo é {limit}"
    ERROR_INVALID_DATE = "❌ Data inválida. Use o formato DD/MM/AAAA (ex: 25/12/2024)"
    ERROR_FUTURE_DATE = "❌ Data não pode ser no futuro"
    ERROR_DESCRIPTION_EMPTY = "❌ Descrição não pode estar vazia"
    ERROR_DESCRIPTION_TOO_LONG = "❌ Descrição muito longa. Máximo de {max_length} caracteres"
    ERROR_CATEGORY_NOT_FOUND = "❌ Categoria não encontrada. Selecione uma categoria válida"
    ERROR_CATEGORY_LIMIT = "❌ Limite de categorias atingido ({limit}). Exclua categorias não utilizadas"
    ERROR_SAVE_FAILED = "❌ Erro ao salvar dados. Tente novamente em alguns instantes"
    ERROR_USER_NOT_AUTHORIZED = "❌ Você não tem permissão para usar este bot"
    ERROR_RATE_LIMITED = "❌ Muitas mensagens em pouco tempo. Aguarde {seconds} segundos"
    ERROR_INVESTMENT_NOT_FOUND = "❌ Investimento não encontrado"
    ERROR_INSUFFICIENT_QUANTITY = "❌ Quantidade insuficiente para venda"
    ERROR_INVALID_TICKER = "❌ Ticker inválido. Use apenas letras e números (ex: PETR4, MXRF11)"
    ERROR_DATABASE_CONNECTION = "❌ Problema de conexão com banco de dados. Tente novamente"
    ERROR_API_UNAVAILABLE = "❌ Serviço temporariamente indisponível. Tente novamente mais tarde"
    
    # Sucessos aprimorados
    SUCCESS_TRANSACTION = """
✅ *Lançamento registrado com sucesso!*

{emoji} *{description}*
💰 Valor: {amount}
🏷️ Categoria: {category}
📅 Data: {date}
💳 Forma: {payment_method}

Saldo atualizado: {new_balance}
"""
    
    SUCCESS_INVESTMENT = """
✅ *Investimento registrado!*

📊 *{ticker}* ({type})
📈 Quantidade: {quantity:.4f}
💰 Preço Médio: {price}
💵 Valor Total: {total}
📅 Data: {date}

Carteira atualizada! 🎯
"""
    
    SUCCESS_CATEGORY_CREATED = """
✅ *Categoria criada!*

🏷️ Nome: {name}
📂 Tipo: {type}
{icon} Ícone: {icon_name}

Agora você pode usar esta categoria em seus lançamentos.
"""
    
    SUCCESS_BACKUP_CREATED = "✅ Backup criado com sucesso em {timestamp}"
    SUCCESS_DATA_EXPORTED = "✅ Dados exportados! Arquivo enviado via chat"
    
    # Confirmações aprimoradas
    CONFIRM_DELETE_TRANSACTION = "⚠️ Tem certeza que deseja excluir a transação '{description}' de {amount}?"
    CONFIRM_DELETE_INVESTMENT = "⚠️ Tem certeza que deseja excluir o investimento {ticker}?"
    CONFIRM_DELETE_CATEGORY = "⚠️ Tem certeza que deseja excluir a categoria '{name}'? Todas as transações desta categoria serão mantidas mas ficarão sem categoria."
    CONFIRM_SELL_INVESTMENT = "⚠️ Confirma a venda de {quantity:.4f} unidades de {ticker} por {price} cada?"
    
    CANCELLED = "❌ Operação cancelada"
    PROCESSING = "🔄 Processando..."
    
    # Instruções aprimoradas
    ASK_AMOUNT = "💰 Digite o valor (ex: 150.50 ou 1.234,56):"
    ASK_DESCRIPTION = "📝 Digite uma descrição clara (máx. {max_length} caracteres):"
    ASK_DATE = "📅 Escolha a data ou digite no formato DD/MM/AAAA:"
    ASK_CATEGORY = "🏷️ Selecione a categoria ou crie uma nova:"
    ASK_TICKER = "📊 Digite o ticker do ativo (ex: PETR4, MXRF11, BTC, IVVB11):"
    ASK_QUANTITY = "📊 Digite a quantidade de cotas/ações:"
    ASK_PRICE = "💰 Digite o preço unitário de compra:"
    ASK_INVESTMENT_TYPE = "📈 Selecione o tipo de investimento:"
    ASK_PAYMENT_METHOD = "💳 Como foi o pagamento/recebimento?"
    
    # Relatórios
    NO_DATA = "📊 Ainda não há dados para exibir. Comece registrando algumas transações!"
    NO_TRANSACTIONS = """
📊 *Nenhuma transação encontrada*

Que tal começar registrando sua primeira transação?
Use o botão "➕ Novo Lançamento" para começar.
"""
    NO_INVESTMENTS = """
📈 *Carteira vazia*

Sua carteira de investimentos está vazia.
Use "➕ Comprar" para adicionar seu primeiro investimento.
"""
    NO_CATEGORIES = "🏷️ Nenhuma categoria encontrada"
    
    # Status e feedback
    LOADING_DATA = "📊 Carregando seus dados..."
    GENERATING_REPORT = "📈 Gerando relatório..."
    FETCHING_MARKET_DATA = "📊 Buscando dados do mercado..."
    SAVING_DATA = "💾 Salvando informações..."
    
    # Ajuda contextual
    HELP_AMOUNT_FORMAT = """
💡 *Formatos aceitos para valores:*
• 150 (cento e cinquenta reais)
• 150.50 ou 150,50 (cento e cinquenta reais e cinquenta centavos)
• 1.234,56 ou 1,234.56 (mil duzentos e trinta e quatro reais)
• R$ 1.500 (mil e quinhentos reais)
"""
    
    HELP_DATE_FORMAT = """
📅 *Formatos aceitos para datas:*
• DD/MM/AAAA (25/12/2024)
• DD-MM-AAAA (25-12-2024)
• DD.MM.AAAA (25.12.2024)
• Use os botões rápidos para datas comuns
"""


class Emojis:
    """Emojis utilizados no bot com melhor categorização"""
    
    # Financeiro
    MONEY_IN = "💵"
    MONEY_OUT = "💸"
    WALLET = "💰"
    CHART_UP = "📈"
    CHART_DOWN = "📉"
    REPORT = "📊"
    SAVINGS = "🏦"
    CREDIT_CARD = "💳"
    CASH = "💵"
    PIX = "📱"
    BANK_TRANSFER = "🏦"
    
    # Status
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    PROCESSING = "🔄"
    WAITING = "⏳"
    
    # Investimentos
    STOCK = "📊"
    CRYPTO = "🪙"
    REAL_ESTATE = "🏠"
    ETF = "📈"
    FIXED_INCOME = "💰"
    DIVIDEND = "💵"
    
    # Navegação
    BACK = "🔙"
    NEXT = "➡️"
    PREVIOUS = "⬅️"
    HOME = "🏠"
    MENU = "📋"
    
    # Indicadores de saúde
    GREEN = "🟢"
    YELLOW = "🟡"
    RED = "🔴"
    BLUE = "🔵"
    
    # Categorias padrão
    SALARY = "💼"
    FOOD = "🍽️"
    TRANSPORT = "🚗"
    HOUSING = "🏠"
    HEALTH = "🏥"
    EDUCATION = "📚"
    ENTERTAINMENT = "🎮"
    SHOPPING = "🛍️"
    BILLS = "📄"
    OTHER = "🔄"
    
    # Ações
    ADD = "➕"
    REMOVE = "➖"
    EDIT = "✏️"
    DELETE = "🗑️"
    VIEW = "👁️"
    SEARCH = "🔍"
    FILTER = "🔽"
    SORT = "↕️"
    
    # Alertas e notificações
    BELL = "🔔"
    BELL_OFF = "🔕"
    REMINDER = "⏰"
    ALERT = "🚨"


class PaymentMethods:
    """Métodos de pagamento/recebimento com melhor estrutura"""
    
    EXPENSE_METHODS = [
        ("credit_card", "💳 Cartão de Crédito"),
        ("debit_card", "💳 Cartão de Débito"),
        ("cash", "💵 Dinheiro"),
        ("pix", "📱 PIX"),
        ("bank_slip", "📄 Boleto"),
        ("bank_transfer", "🏦 Transferência"),
        ("financing", "🏦 Financiamento"),
        ("installment", "📅 Parcelado"),
    ]
    
    INCOME_METHODS = [
        ("salary", "💼 Salário"),
        ("pix", "📱 PIX"),
        ("bank_transfer", "🏦 Transferência"),
        ("cash", "💵 Dinheiro"),
        ("investment", "📈 Investimentos"),
        ("freelance", "💻 Freelance"),
        ("sale", "🛒 Venda"),
        ("bonus", "🎁 Bônus"),
        ("other", "💰 Outros"),
    ]
    
    @classmethod
    def get_expense_methods(cls) -> List[str]:
        """Retorna lista de métodos para despesas"""
        return [method[1] for method in cls.EXPENSE_METHODS]
    
    @classmethod
    def get_income_methods(cls) -> List[str]:
        """Retorna lista de métodos para receitas"""
        return [method[1] for method in cls.INCOME_METHODS]
    
    @classmethod
    def get_all_methods(cls) -> Dict[str, str]:
        """Retorna dicionário com todos os métodos"""
        all_methods = dict(cls.EXPENSE_METHODS + cls.INCOME_METHODS)
        return all_methods
    
    @classmethod
    def get_method_key(cls, display_name: str) -> str:
        """Retorna a chave do método baseado no nome de exibição"""
        all_methods = cls.EXPENSE_METHODS + cls.INCOME_METHODS
        for key, name in all_methods:
            if name == display_name:
                return key
        
        # Fallback: remove emoji e converte
        clean_name = display_name.split(' ', 1)[-1].lower().replace(' ', '_')
        return clean_name
    
    @classmethod
    def get_method_display(cls, key: str) -> str:
        """Retorna o nome de exibição baseado na chave"""
        all_methods = dict(cls.EXPENSE_METHODS + cls.INCOME_METHODS)
        return all_methods.get(key, key.replace('_', ' ').title())


class InvestmentTypes:
    """Tipos de investimentos com informações detalhadas"""
    
    TYPES = {
        'stock': {
            'name': 'Ações',
            'emoji': '📊',
            'description': 'Ações de empresas listadas na bolsa',
            'risk_level': 'Alto',
            'examples': ['PETR4', 'VALE3', 'ITUB4', 'BBDC4']
        },
        'fii': {
            'name': 'Fundos Imobiliários',
            'emoji': '🏠',
            'description': 'Cotas de fundos de investimento imobiliário',
            'risk_level': 'Médio',
            'examples': ['MXRF11', 'HGLG11', 'XPLG11', 'KNRI11']
        },
        'crypto': {
            'name': 'Criptomoedas',
            'emoji': '🪙',
            'description': 'Moedas digitais e tokens',
            'risk_level': 'Muito Alto',
            'examples': ['BTC', 'ETH', 'ADA', 'DOT']
        },
        'etf': {
            'name': 'ETFs',
            'emoji': '📈',
            'description': 'Fundos de índice negociados em bolsa',
            'risk_level': 'Médio',
            'examples': ['IVVB11', 'BOVA11', 'SMAL11', 'HASH11']
        },
        'fixed': {
            'name': 'Renda Fixa',
            'emoji': '💰',
            'description': 'Títulos de renda fixa e CDBs',
            'risk_level': 'Baixo',
            'examples': ['Tesouro Selic', 'CDB', 'LCI', 'LCA']
        },
        'other': {
            'name': 'Outros',
            'emoji': '🔄',
            'description': 'Outros tipos de investimento',
            'risk_level': 'Variável',
            'examples': ['COE', 'Debêntures', 'Commodities']
        }
    }
    
    @classmethod
    def get_type_info(cls, type_key: str) -> Dict[str, str]:
        """Retorna informações detalhadas de um tipo"""
        return cls.TYPES.get(type_key, cls.TYPES['other'])
    
    @classmethod
    def get_display_name(cls, type_key: str) -> str:
        """Retorna nome de exibição com emoji"""
        info = cls.get_type_info(type_key)
        return f"{info['emoji']} {info['name']}"
    
    @classmethod
    def get_all_types(cls) -> List[Tuple[str, str]]:
        """Retorna lista de todos os tipos para teclados"""
        return [(key, cls.get_display_name(key)) for key in cls.TYPES.keys()]


# Configurações de categorias padrão melhoradas
DEFAULT_CATEGORIES = {
    "income": [
        ("Salário", "💼", "Salário mensal e benefícios"),
        ("Freelance", "💻", "Trabalhos freelance e consultoria"),
        ("Investimentos", "📈", "Rendimentos de investimentos"),
        ("Vendas", "🛒", "Vendas de produtos e serviços"),
        ("Bônus", "🎁", "Bônus, comissões e gratificações"),
        ("Aluguel", "🏠", "Renda de aluguéis"),
        ("Outros", "💰", "Outras fontes de receita"),
    ],
    "expense": [
        ("Alimentação", "🍽️", "Supermercado, restaurantes e delivery"),
        ("Transporte", "🚗", "Combustível, transporte público e viagens"),
        ("Moradia", "🏠", "Aluguel, condomínio e manutenção"),
        ("Saúde", "🏥", "Plano de saúde, medicamentos e consultas"),
        ("Educação", "📚", "Cursos, livros e material escolar"),
        ("Lazer", "🎮", "Entretenimento, cinema e atividades"),
        ("Compras", "🛍️", "Roupas, eletrônicos e compras diversas"),
        ("Contas", "📄", "Água, luz, internet e telefone"),
        ("Impostos", "📋", "IPTU, IPVA e outros impostos"),
        ("Seguros", "🛡️", "Seguro auto, residencial e vida"),
        ("Pets", "🐕", "Veterinário, ração e cuidados com pets"),
        ("Beleza", "💄", "Salão, cosméticos e cuidados pessoais"),
        ("Doações", "❤️", "Doações e caridade"),
        ("Outros", "💸", "Outras despesas não categorizadas"),
    ]
}


class CacheKeys:
    """Chaves para cache Redis"""
    
    USER_DATA = "user_data:{user_id}"
    USER_TRANSACTIONS = "user_transactions:{user_id}:{page}"
    USER_INVESTMENTS = "user_investments:{user_id}"
    USER_CATEGORIES = "user_categories:{user_id}:{type}"
    MONTHLY_SUMMARY = "monthly_summary:{user_id}:{year}:{month}"
    MARKET_DATA = "market_data:{ticker}"
    EXCHANGE_RATES = "exchange_rates"
    
    @classmethod
    def format_key(cls, key_template: str, **kwargs) -> str:
        """Formata uma chave de cache com parâmetros"""
        return key_template.format(**kwargs)


class ValidationRules:
    """Regras de validação para diferentes campos"""
    
    @staticmethod
    def validate_amount(amount: str) -> Tuple[bool, Optional[str], Optional[Decimal]]:
        """
        Valida um valor monetário
        Retorna: (is_valid, error_message, parsed_amount)
        """
        try:
            # Remove espaços e caracteres especiais
            clean_amount = amount.strip().replace('R$', '').replace('r$', '')
            
            # Trata separadores de milhares e decimais
            if ',' in clean_amount and '.' in clean_amount:
                if clean_amount.rindex(',') > clean_amount.rindex('.'):
                    clean_amount = clean_amount.replace('.', '').replace(',', '.')
                else:
                    clean_amount = clean_amount.replace(',', '')
            elif ',' in clean_amount:
                clean_amount = clean_amount.replace(',', '.')
            
            # Remove caracteres não numéricos (exceto ponto)
            import re
            clean_amount = re.sub(r'[^\d.]', '', clean_amount)
            
            if not clean_amount:
                return False, Messages.ERROR_INVALID_AMOUNT, None
            
            parsed_amount = Decimal(clean_amount)
            
            # Validar limites
            if parsed_amount < Config.MIN_TRANSACTION_AMOUNT:
                return False, Messages.ERROR_AMOUNT_TOO_LOW.format(
                    limit=Config.MIN_TRANSACTION_AMOUNT
                ), None
            
            if parsed_amount > Config.MAX_TRANSACTION_AMOUNT:
                return False, Messages.ERROR_AMOUNT_TOO_HIGH.format(
                    limit=Config.MAX_TRANSACTION_AMOUNT
                ), None
            
            return True, None, parsed_amount
            
        except (ValueError, TypeError):
            return False, Messages.ERROR_INVALID_AMOUNT, None
    
    @staticmethod
    def validate_description(description: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Valida uma descrição
        Retorna: (is_valid, error_message, cleaned_description)
        """
        if not description or not description.strip():
            return False, Messages.ERROR_DESCRIPTION_EMPTY, None
        
        cleaned = description.strip()
        
        if len(cleaned) > Config.MAX_DESCRIPTION_LENGTH:
            return False, Messages.ERROR_DESCRIPTION_TOO_LONG.format(
                max_length=Config.MAX_DESCRIPTION_LENGTH
            ), None
        
        return True, None, cleaned
    
    @staticmethod
    def validate_ticker(ticker: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Valida um ticker de investimento
        Retorna: (is_valid, error_message, cleaned_ticker)
        """
        if not ticker or not ticker.strip():
            return False, Messages.ERROR_INVALID_TICKER, None
        
        cleaned = ticker.strip().upper()
        
        # Ticker deve ter entre 3 e 10 caracteres alfanuméricos
        import re
        if not re.match(r'^[A-Z0-9]{3,10}$', cleaned):
            return False, Messages.ERROR_INVALID_TICKER, None
        
        return True, None, cleaned
    
    @staticmethod
    def validate_date(date_str: str) -> Tuple[bool, Optional[str], Optional[datetime]]:
        """
        Valida uma data
        Retorna: (is_valid, error_message, parsed_date)
        """
        from datetime import datetime
        
        if not date_str or not date_str.strip():
            return False, Messages.ERROR_INVALID_DATE, None
        
        # Normalizar separadores
        normalized = date_str.strip().replace('-', '/').replace('.', '/')
        
        # Formatos aceitos
        formats = ['%d/%m/%Y', '%d/%m/%y', '%Y/%m/%d', '%d/%m']
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(normalized, fmt)
                
                # Se não tem ano, usar o atual
                if fmt == '%d/%m':
                    parsed_date = parsed_date.replace(year=datetime.now().year)
                
                # Validar data futura
                if parsed_date > datetime.now():
                    return False, Messages.ERROR_FUTURE_DATE, None
                
                return True, None, parsed_date
                
            except ValueError:
                continue
        
        return False, Messages.ERROR_INVALID_DATE, None


class Formatters:
    """Formatadores para exibição de dados"""
    
    @staticmethod
    def currency(amount: Decimal, show_symbol: bool = True) -> str:
        """Formata valor monetário"""
        formatted = f"{amount:,.2f}"
        formatted = formatted.replace(',', '_').replace('.', ',').replace('_', '.')
        
        if show_symbol:
            return f"R$ {formatted}"
        return formatted
    
    @staticmethod
    def percentage(value: Decimal, decimals: int = 1) -> str:
        """Formata percentual"""
        return f"{value:.{decimals}f}%"
    
    @staticmethod
    def date(date: datetime, format_str: str = '%d/%m/%Y') -> str:
        """Formata data"""
        return date.strftime(format_str)
    
    @staticmethod
    def datetime(dt: datetime, format_str: str = '%d/%m/%Y %H:%M') -> str:
        """Formata data e hora"""
        return dt.strftime(format_str)
    
    @staticmethod
    def large_number(number: float, decimals: int = 1) -> str:
        """Formata números grandes (K, M, B)"""
        if number >= 1_000_000_000:
            return f"{number/1_000_000_000:.{decimals}f}B"
        elif number >= 1_000_000:
            return f"{number/1_000_000:.{decimals}f}M"
        elif number >= 1_000:
            return f"{number/1_000:.{decimals}f}K"
        else:
            return f"{number:.{decimals}f}"
    
    @staticmethod
    def truncate_text(text: str, max_length: int, suffix: str = '...') -> str:
        """Trunca texto se necessário"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escapa caracteres especiais do Markdown"""
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        for char in escape_chars:
            text = text.replace(char, f'\\{char}')
        
        return text


class HealthIndicators:
    """Indicadores de saúde financeira"""
    
    SCORE_RANGES = {
        (90, 100): {"status": "Excelente", "emoji": "🟢", "color": "green"},
        (80, 89): {"status": "Muito Bom", "emoji": "🟢", "color": "green"},
        (70, 79): {"status": "Bom", "emoji": "🟡", "color": "yellow"},
        (60, 69): {"status": "Regular", "emoji": "🟡", "color": "yellow"},
        (40, 59): {"status": "Ruim", "emoji": "🟠", "color": "orange"},
        (0, 39): {"status": "Crítico", "emoji": "🔴", "color": "red"},
    }
    
    @classmethod
    def get_health_info(cls, score: int) -> Dict[str, str]:
        """Retorna informações baseadas no score de saúde"""
        for (min_score, max_score), info in cls.SCORE_RANGES.items():
            if min_score <= score <= max_score:
                return info
        
        return cls.SCORE_RANGES[(0, 39)]
    
    @classmethod
    def get_recommendations(cls, score: int, user_data: Dict = None) -> List[str]:
        """Retorna recomendações baseadas no score"""
        recommendations = []
        
        if score < 40:
            recommendations.extend([
                "🚨 Revise urgentemente todos os seus gastos",
                "📊 Crie um orçamento detalhado e siga rigorosamente",
                "✂️ Corte gastos desnecessários imediatamente",
                "💰 Busque fontes extras de renda",
                "📚 Estude sobre educação financeira"
            ])
        elif score < 60:
            recommendations.extend([
                "📈 Aumente sua taxa de poupança para pelo menos 20%",
                "🏦 Crie uma reserva de emergência",
                "📱 Cancele assinaturas não utilizadas",
                "🎯 Estabeleça metas financeiras claras",
                "📊 Monitore seus gastos semanalmente"
            ])
        elif score < 80:
            recommendations.extend([
                "📈 Comece a investir suas economias",
                "🎯 Diversifique seus investimentos",
                "📚 Aprenda sobre diferentes tipos de investimento",
                "💰 Otimize sua declaração de IR",
                "🔄 Revise periodicamente sua estratégia"
            ])
        else:
            recommendations.extend([
                "🚀 Explore investimentos mais sofisticados",
                "🌍 Considere investimentos internacionais",
                "🏠 Planeje investimentos em imóveis",
                "👥 Considere mentoria para outros",
                "🎯 Planeje aposentadoria antecipada"
            ])
        
        return recommendations


class NotificationTemplates:
    """Templates para notificações"""
    
    DAILY_SUMMARY = """
📊 *Resumo do Dia* - {date}

💰 Saldo atual: {balance}
📈 Receitas: +{income}
📉 Despesas: -{expenses}
🎯 Meta mensal: {goal_progress}%

{health_indicator} Status: {health_status}
"""
    
    WEEKLY_SUMMARY = """
📊 *Resumo Semanal* - {week_range}

💰 Saldo da semana: {balance}
📈 Total de receitas: +{income}
📉 Total de despesas: -{expenses}
📊 Transações: {transaction_count}

🎯 Progresso da meta: {goal_progress}%
📈 Comparado à semana anterior: {comparison}
"""
    
    MONTHLY_SUMMARY = """
📊 *Resumo Mensal* - {month}/{year}

💰 Saldo do mês: {balance}
📈 Receitas: +{income}
📉 Despesas: -{expenses}
💾 Taxa de poupança: {savings_rate}%

🏆 Categoria com mais gastos: {top_category}
🎯 Meta atingida: {goal_achieved}

{health_indicator} Score de saúde: {health_score}/100
"""
    
    DIVIDEND_ALERT = """
💵 *Dividendo Recebido!*

📊 Ativo: {ticker}
💰 Valor: {amount}
📅 Data: {date}
🎯 Yield: {yield_percentage}%

💡 Que tal reinvestir este valor?
"""
    
    GOAL_ACHIEVED = """
🎉 *Meta Atingida!*

🎯 Meta: {goal_name}
💰 Valor: {amount}
📅 Prazo: {deadline}

Parabéns! Você conseguiu! 🎊
"""
    
    EXPENSE_ALERT = """
⚠️ *Alerta de Gastos*

📈 Seus gastos em {category} estão {percentage}% acima da média
💰 Valor atual: {current_amount}
📊 Média histórica: {average_amount}

💡 Revise seus gastos nesta categoria
"""


# Constantes para temas e cores
class Themes:
    """Temas visuais para diferentes contextos"""
    
    SUCCESS = {"emoji": "✅", "color": "#28a745"}
    ERROR = {"emoji": "❌", "color": "#dc3545"}
    WARNING = {"emoji": "⚠️", "color": "#ffc107"}
    INFO = {"emoji": "ℹ️", "color": "#17a2b8"}
    
    INCOME = {"emoji": "💵", "color": "#28a745"}
    EXPENSE = {"emoji": "💸", "color": "#dc3545"}
    INVESTMENT = {"emoji": "📈", "color": "#007bff"}


# Validação final de configuração
def validate_environment():
    """Valida o ambiente antes de iniciar o bot"""
    try:
        Config.validate()
        logger.info("✅ Configuração validada com sucesso!")
        return True
    except ValueError as e:
        logger.error(f"❌ Erro de configuração: {e}")
        return False