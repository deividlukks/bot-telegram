"""
Funções utilitárias completas e corrigidas para o Finance Bot
Inclui validações robustas, formatação avançada, segurança e performance
"""
import re
import logging
import hashlib
import secrets
import time
import json
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, Union, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from collections import defaultdict

from telegram import Update
from sqlalchemy.orm import Session

from config import Config, Messages
from models import User
from services import UserService

logger = logging.getLogger(__name__)


# ==================== CLASSES DE UTILIDADE ====================

class ValidationResult:
    """Resultado de validação com contexto"""
    def __init__(self, is_valid: bool, value: Any = None, error_message: str = None):
        self.is_valid = is_valid
        self.value = value
        self.error_message = error_message

    def __bool__(self):
        return self.is_valid


@dataclass
class FinancialMetrics:
    """Métricas financeiras calculadas"""
    total_income: Decimal
    total_expenses: Decimal
    balance: Decimal
    savings_rate: Decimal
    health_score: int
    trend: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_income': self.total_income,
            'total_expenses': self.total_expenses,
            'balance': self.balance,
            'savings_rate': self.savings_rate,
            'health_score': self.health_score,
            'trend': self.trend
        }


class TrendDirection(Enum):
    """Direções de tendência"""
    UP = "📈"
    DOWN = "📉"
    STABLE = "➡️"
    VOLATILE = "📊"


class RiskLevel(Enum):
    """Níveis de risco"""
    LOW = ("🟢", "Baixo")
    MEDIUM = ("🟡", "Médio")
    HIGH = ("🟠", "Alto")
    VERY_HIGH = ("🔴", "Muito Alto")


# ==================== RATE LIMITING ====================

# Armazenamento de requests por usuário
user_requests = defaultdict(list)

def rate_limit(max_requests: int = 30, window_seconds: int = 60):
    """
    Decorator para rate limiting
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context, *args, **kwargs):
            user_id = update.effective_user.id
            now = time.time()
            
            # Limpar requests antigos
            user_requests[user_id] = [
                req_time for req_time in user_requests[user_id]
                if now - req_time < window_seconds
            ]
            
            if len(user_requests[user_id]) >= max_requests:
                await update.message.reply_text(
                    "⚠️ Muitas requisições. Aguarde um momento antes de tentar novamente."
                )
                return
            
            user_requests[user_id].append(now)
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


# ==================== VALIDADORES AVANÇADOS ====================

class AmountValidator:
    """Validador avançado para valores monetários"""
    
    @staticmethod
    def parse_and_validate(
        text: str, 
        min_amount: Decimal = None, 
        max_amount: Decimal = None
    ) -> ValidationResult:
        """
        Valida e parseia valor monetário com contexto completo
        """
        try:
            if not text or not text.strip():
                return ValidationResult(False, None, "Valor não pode estar vazio")
            
            # Sanitizar entrada
            text = sanitize_user_input(text)
            
            # Remover símbolos de moeda e espaços
            cleaned = re.sub(r'[R$\s]', '', text.strip())
            
            if not cleaned:
                return ValidationResult(False, None, "Valor não pode estar vazio")
            
            # Detectar formato brasileiro vs americano
            if ',' in cleaned and '.' in cleaned:
                # Formato brasileiro: 1.234,56
                if cleaned.rindex(',') > cleaned.rindex('.'):
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                # Formato americano: 1,234.56
                else:
                    cleaned = cleaned.replace(',', '')
            elif ',' in cleaned:
                # Verificar se vírgula é separador decimal
                comma_parts = cleaned.split(',')
                if len(comma_parts) == 2 and len(comma_parts[1]) <= 2:
                    cleaned = cleaned.replace(',', '.')
                else:
                    # Vírgula como separador de milhares
                    cleaned = cleaned.replace(',', '')
            
            # Remover caracteres não numéricos (exceto ponto decimal)
            cleaned = re.sub(r'[^\d.]', '', cleaned)
            
            if not cleaned or cleaned == '.':
                return ValidationResult(False, None, "Formato de valor inválido")
            
            # Verificar múltiplos pontos
            if cleaned.count('.') > 1:
                return ValidationResult(False, None, "Formato de valor inválido")
            
            # Converter para Decimal
            amount = Decimal(cleaned).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            # Validar limites básicos
            if amount <= 0:
                return ValidationResult(False, None, "Valor deve ser maior que zero")
            
            # Validar overflow
            if amount > Decimal('999999999.99'):
                return ValidationResult(False, None, "Valor muito grande")
            
            # Validar limites personalizados
            min_limit = min_amount or Config.MIN_TRANSACTION_AMOUNT
            max_limit = max_amount or Config.MAX_TRANSACTION_AMOUNT
            
            if amount < min_limit:
                return ValidationResult(
                    False, None, 
                    f"Valor mínimo é {format_currency(min_limit)}"
                )
            
            if amount > max_limit:
                return ValidationResult(
                    False, None, 
                    f"Valor máximo é {format_currency(max_limit)}"
                )
            
            return ValidationResult(True, amount)
            
        except (ValueError, InvalidOperation, OverflowError) as e:
            logger.debug(f"Erro ao validar valor '{text}': {e}")
            return ValidationResult(False, None, "Formato de valor inválido")


class DateValidator:
    """Validador avançado para datas"""
    
    @staticmethod
    def parse_and_validate(text: str, allow_future: bool = False) -> ValidationResult:
        """
        Valida e parseia data com múltiplos formatos
        """
        if not text or not text.strip():
            return ValidationResult(False, None, "Data não pode estar vazia")
        
        text = sanitize_user_input(text.strip())
        
        # Formatos especiais
        today = datetime.now().date()
        
        text_lower = text.lower()
        if text_lower in ['hoje', 'today']:
            return ValidationResult(True, datetime.now())
        elif text_lower in ['ontem', 'yesterday']:
            return ValidationResult(True, datetime.now() - timedelta(days=1))
        elif text_lower in ['anteontem']:
            return ValidationResult(True, datetime.now() - timedelta(days=2))
        
        # Normalizar separadores
        text = re.sub(r'[-/.]', '/', text)
        
        # Formatos suportados
        formats = [
            '%d/%m/%Y',     # 31/12/2023
            '%d/%m/%y',     # 31/12/23
            '%Y/%m/%d',     # 2023/12/31
            '%d/%m',        # 31/12 (ano atual)
            '%m/%d/%Y',     # 12/31/2023 (formato americano)
            '%Y-%m-%d',     # 2023-12-31 (ISO)
        ]
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(text, fmt)
                
                # Se não tem ano, usar o atual
                if fmt == '%d/%m':
                    parsed_date = parsed_date.replace(year=today.year)
                
                # Validar data futura
                if not allow_future and parsed_date.date() > today:
                    return ValidationResult(
                        False, None, 
                        "Data não pode ser no futuro"
                    )
                
                # Validar data muito antiga (mais de 10 anos)
                ten_years_ago = today.replace(year=today.year - 10)
                if parsed_date.date() < ten_years_ago:
                    return ValidationResult(
                        False, None, 
                        "Data não pode ser anterior a 10 anos"
                    )
                
                # Validar ano com 2 dígitos
                if fmt == '%d/%m/%y' and parsed_date.year < 2000:
                    parsed_date = parsed_date.replace(year=parsed_date.year + 100)
                
                return ValidationResult(True, parsed_date)
                
            except ValueError:
                continue
        
        return ValidationResult(False, None, "Formato de data inválido. Use DD/MM/AAAA")


class TickerValidator:
    """Validador para tickers de investimento"""
    
    @staticmethod
    def validate_ticker(ticker: str, investment_type: str = None) -> ValidationResult:
        """
        Valida ticker baseado no tipo de investimento
        """
        if not ticker or not ticker.strip():
            return ValidationResult(False, None, "Ticker não pode estar vazio")
        
        ticker = sanitize_user_input(ticker.strip().upper())
        
        # Padrões por tipo de investimento
        patterns = {
            'stock': r'^[A-Z]{4}[0-9]{1,2}$',          # PETR4, VALE3, MGLU3
            'fii': r'^[A-Z]{4}[0-9]{2}$',              # MXRF11, HGLG11
            'etf': r'^[A-Z]{4}[0-9]{2}$',              # IVVB11, BOVA11
            'crypto': r'^[A-Z]{2,10}$',                # BTC, ETH, ADA
            'fixed': r'^[A-Z]{2,10}(-[A-Z])?$',       # LTN, NTN-B, CDB
            'other': r'^[A-Z0-9]{2,10}$'              # COE, LC
        }
        
        # Validação geral (2-10 caracteres alfanuméricos)
        if not re.match(r'^[A-Z0-9-]{2,10}$', ticker):
            return ValidationResult(
                False, None, 
                "Ticker deve ter 2-10 caracteres (letras, números e hífen)"
            )
        
        # Validação específica por tipo
        if investment_type and investment_type in patterns:
            pattern = patterns[investment_type]
            if not re.match(pattern, ticker):
                type_examples = {
                    'stock': 'PETR4, VALE3, ITUB4',
                    'fii': 'MXRF11, HGLG11, XPLG11',
                    'etf': 'IVVB11, BOVA11, SMAL11',
                    'crypto': 'BTC, ETH, ADA',
                    'fixed': 'LTN, NTN-B, CDB',
                    'other': 'COE, LC, DEB'
                }
                examples = type_examples.get(investment_type, ticker)
                return ValidationResult(
                    False, None, 
                    f"Formato inválido para {investment_type}. Exemplos: {examples}"
                )
        
        return ValidationResult(True, ticker)


class TextValidator:
    """Validador para campos de texto"""
    
    @staticmethod
    def validate_description(
        text: str, 
        min_length: int = 1, 
        max_length: int = None
    ) -> ValidationResult:
        """Valida descrição de transação"""
        if not text or not text.strip():
            return ValidationResult(False, None, "Descrição não pode estar vazia")
        
        text = sanitize_user_input(text.strip())
        max_len = max_length or Config.MAX_DESCRIPTION_LENGTH
        
        if len(text) < min_length:
            return ValidationResult(
                False, None, 
                f"Descrição deve ter pelo menos {min_length} caracteres"
            )
        
        if len(text) > max_len:
            return ValidationResult(
                False, None, 
                f"Descrição não pode ter mais que {max_len} caracteres"
            )
        
        # Verificar caracteres especiais maliciosos
        if re.search(r'[<>{}]', text):
            return ValidationResult(
                False, None, 
                "Descrição contém caracteres não permitidos"
            )
        
        return ValidationResult(True, text)
    
    @staticmethod
    def validate_category_name(name: str) -> ValidationResult:
        """Valida nome de categoria"""
        if not name or not name.strip():
            return ValidationResult(False, None, "Nome da categoria não pode estar vazio")
        
        name = sanitize_user_input(name.strip())
        
        if len(name) < 2:
            return ValidationResult(False, None, "Nome deve ter pelo menos 2 caracteres")
        
        if len(name) > 50:
            return ValidationResult(False, None, "Nome não pode ter mais que 50 caracteres")
        
        # Apenas letras, números, espaços e alguns símbolos
        if not re.match(r'^[a-zA-ZÀ-ÿ0-9\s\-_.()]+$', name):
            return ValidationResult(
                False, None, 
                "Nome pode conter apenas letras, números, espaços e símbolos básicos"
            )
        
        return ValidationResult(True, name)


# ==================== FUNÇÕES DE SANITIZAÇÃO ====================

def sanitize_user_input(text: str) -> str:
    """
    Remove caracteres potencialmente perigosos da entrada do usuário
    """
    if not text:
        return ""
    
    # Remove caracteres de controle (exceto \n, \r, \t)
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    
    # Limita tamanho máximo
    text = text[:1000]
    
    # Remove espaços excessivos
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


# ==================== FORMATADORES AVANÇADOS ====================

def format_currency(
    amount: Union[Decimal, float, int], 
    symbol: str = "R$", 
    show_cents: bool = True
) -> str:
    """
    Formata valor para moeda brasileira com opções avançadas
    """
    if amount is None:
        return f"{symbol} 0,00"
    
    if isinstance(amount, (float, int)):
        amount = Decimal(str(amount))
    
    # Arredondar para 2 casas decimais
    amount = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Converter para string com formatação
    if show_cents:
        formatted = f"{amount:,.2f}"
    else:
        # Mostrar apenas reais se for valor inteiro
        if amount % 1 == 0:
            formatted = f"{int(amount):,}"
        else:
            formatted = f"{amount:,.2f}"
    
    # Trocar separadores para formato brasileiro
    formatted = formatted.replace(',', '_temp_').replace('.', ',').replace('_temp_', '.')
    
    return f"{symbol} {formatted}"


def format_percentage(
    value: Union[Decimal, float], 
    decimals: int = 1,
    show_sign: bool = False
) -> str:
    """
    Formata valor como percentual com opções
    """
    if value is None:
        return "0%"
    
    if isinstance(value, float):
        value = Decimal(str(value))
    
    sign = "+" if show_sign and value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"


def format_large_number(number: Union[int, float, Decimal], precision: int = 1) -> str:
    """
    Formata números grandes com sufixos (K, M, B)
    """
    if number is None:
        return "0"
    
    if isinstance(number, Decimal):
        number = float(number)
    
    abs_number = abs(number)
    sign = "-" if number < 0 else ""
    
    if abs_number >= 1_000_000_000:
        return f"{sign}{abs_number/1_000_000_000:.{precision}f}B"
    elif abs_number >= 1_000_000:
        return f"{sign}{abs_number/1_000_000:.{precision}f}M"
    elif abs_number >= 1_000:
        return f"{sign}{abs_number/1_000:.{precision}f}K"
    else:
        return f"{sign}{abs_number:.{precision}f}"


def format_time_ago(dt: datetime) -> str:
    """
    Formata tempo relativo (ex: 'há 2 dias')
    """
    if not dt:
        return "Nunca"
    
    now = datetime.now()
    
    # Garantir que dt tem timezone info ou remover de ambos
    if dt.tzinfo is None and now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    elif dt.tzinfo is not None and now.tzinfo is None:
        dt = dt.replace(tzinfo=None)
    
    diff = now - dt
    
    if diff.days > 0:
        if diff.days == 1:
            return "há 1 dia"
        elif diff.days < 7:
            return f"há {diff.days} dias"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"há {weeks} semana{'s' if weeks > 1 else ''}"
        elif diff.days < 365:
            months = diff.days // 30
            return f"há {months} mês/meses"
        else:
            years = diff.days // 365
            return f"há {years} ano{'s' if years > 1 else ''}"
    
    seconds = diff.seconds
    if seconds < 60:
        return "agora mesmo"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"há {minutes} minuto{'s' if minutes > 1 else ''}"
    else:
        hours = seconds // 3600
        return f"há {hours} hora{'s' if hours > 1 else ''}"


def format_date_range(start: datetime, end: datetime) -> str:
    """
    Formata intervalo de datas de forma inteligente
    """
    if not start or not end:
        return "Data inválida"
    
    if start.year == end.year:
        if start.month == end.month:
            if start.day == end.day:
                return start.strftime('%d/%m/%Y')
            else:
                return f"{start.day}-{end.day}/{start.month}/{start.year}"
        else:
            return f"{start.strftime('%d/%m')} - {end.strftime('%d/%m/%Y')}"
    else:
        return f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"


def format_date(date: datetime, format: str = '%d/%m/%Y') -> str:
    """
    Formata data para exibição
    """
    if not date:
        return "Data inválida"
    return date.strftime(format)


def format_datetime(dt: datetime, format: str = '%d/%m/%Y %H:%M') -> str:
    """
    Formata data e hora para exibição
    """
    if not dt:
        return "Data/hora inválida"
    return dt.strftime(format)


# ==================== UTILITÁRIOS DE TEXTO ====================

def escape_markdown(text: str) -> str:
    """
    Escapa caracteres especiais do Markdown do Telegram (v1)
    """
    if not text:
        return ""
    
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def escape_markdown_v2(text: str) -> str:
    """
    Escapa caracteres especiais para Telegram MarkdownV2
    """
    if not text:
        return ""
    
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text


def truncate_string(text: str, max_length: int, suffix: str = '...') -> str:
    """
    Trunca string preservando palavras quando possível
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Tentar truncar na última palavra completa
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.7:  # Se a última palavra não está muito longe
        return truncated[:last_space] + suffix
    else:
        return truncated + suffix


def clean_input(text: str) -> str:
    """
    Limpa entrada do usuário removendo caracteres problemáticos
    """
    if not text:
        return ""
    
    # Remover caracteres de controle exceto quebras de linha
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Normalizar espaços em branco
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def extract_numbers(text: str) -> List[Decimal]:
    """
    Extrai todos os números válidos de um texto
    """
    if not text:
        return []
    
    numbers = []
    # Padrão para números com formato brasileiro ou americano
    pattern = r'\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?'
    
    matches = re.findall(pattern, text)
    
    for match in matches:
        try:
            # Tentar converter usando validador
            result = AmountValidator.parse_and_validate(match)
            if result.is_valid:
                numbers.append(result.value)
        except:
            continue
    
    return numbers


# ==================== UTILITÁRIOS DE CÁLCULO ====================

def calculate_percentage(part: Decimal, whole: Decimal) -> Decimal:
    """
    Calcula percentual de part em relação a whole
    Retorna 0 se whole for 0
    """
    if not part or not whole or whole == 0:
        return Decimal('0')
    
    return (part / whole) * 100


def calculate_trend(values: List[Union[Decimal, float]]) -> str:
    """
    Calcula tendência baseada em lista de valores
    Retorna emoji indicando tendência
    """
    if not values or len(values) < 2:
        return "➡️"
    
    # Converter para float para cálculos
    float_values = [float(v) for v in values if v is not None]
    
    if len(float_values) < 2:
        return "➡️"
    
    # Calcular média das primeiras e segundas metades
    mid = len(float_values) // 2
    first_half = sum(float_values[:mid]) / mid
    second_half = sum(float_values[mid:]) / len(float_values[mid:])
    
    # Determinar tendência
    if first_half == 0:
        return "📈" if second_half > 0 else "➡️"
    
    diff_percent = ((second_half - first_half) / first_half * 100)
    
    if diff_percent > 10:
        return "📈"  # Crescimento
    elif diff_percent < -10:
        return "📉"  # Queda
    else:
        return "➡️"  # Estável


# ==================== UTILITÁRIOS DE ID E HASH ====================

def generate_transaction_id() -> str:
    """
    Gera um ID único para transação (para uso em callbacks)
    """
    return secrets.token_urlsafe(8)


def generate_short_id(length: int = 8) -> str:
    """
    Gera ID curto para uso em callbacks
    """
    return secrets.token_urlsafe(length)[:length]


def hash_sensitive_data(data: str, salt: str = None) -> str:
    """
    Hash seguro para dados sensíveis
    """
    if not data:
        return ""
    
    if salt is None:
        salt = secrets.token_hex(16)
    
    return hashlib.pbkdf2_hmac(
        'sha256',
        data.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()


def parse_callback_data(callback_data: str) -> Tuple[str, Optional[str]]:
    """
    Parseia callback_data no formato "action_id"
    Retorna (action, id) ou (action, None)
    """
    if not callback_data:
        return "", None
    
    parts = callback_data.split('_', 1)
    
    if len(parts) == 2:
        return parts[0], parts[1]
    
    return parts[0], None


# ==================== CLASSES DE PROGRESSO E SAÚDE ====================

class ProgressBar:
    """Classe para criar barras de progresso visuais"""
    
    @staticmethod
    def create(
        current: Union[Decimal, float], 
        total: Union[Decimal, float], 
        width: int = 10,
        filled: str = "█",
        empty: str = "░"
    ) -> str:
        """
        Cria uma barra de progresso visual
        Ex: ████████░░ 80%
        """
        if not current or not total or total == 0:
            percentage = 0
        else:
            percentage = min(1.0, float(current) / float(total))
        
        filled_blocks = int(width * percentage)
        empty_blocks = width - filled_blocks
        
        bar = filled * filled_blocks + empty * empty_blocks
        
        return f"{bar} {percentage*100:.0f}%"


class EmojiHealth:
    """Classe para determinar emojis baseados em valores de saúde financeira"""
    
    @staticmethod
    def get_score_emoji(score: int) -> str:
        """Retorna emoji baseado no score (0-100)"""
        if score >= 80:
            return "🟢"
        elif score >= 60:
            return "🟡"
        elif score >= 40:
            return "🟠"
        else:
            return "🔴"
    
    @staticmethod
    def get_trend_emoji(current: Decimal, previous: Decimal) -> str:
        """Retorna emoji baseado na comparação de valores"""
        if not current or not previous or previous == 0:
            return "➡️"
        
        if current > previous * Decimal('1.05'):  # +5%
            return "📈"
        elif current < previous * Decimal('0.95'):  # -5%
            return "📉"
        else:
            return "➡️"
    
    @staticmethod
    def get_balance_emoji(balance: Decimal) -> str:
        """Retorna emoji baseado no saldo"""
        if not balance:
            return "⚪"
        
        if balance > 0:
            return "✅"
        elif balance < 0:
            return "⚠️"
        else:
            return "⚪"


# ==================== UTILITÁRIOS DE DATA ====================

def get_month_name(month: int) -> str:
    """
    Retorna o nome do mês em português
    """
    months = [
        'Janeiro', 'Fevereiro', 'Março', 'Abril',
        'Maio', 'Junho', 'Julho', 'Agosto',
        'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ]
    
    if 1 <= month <= 12:
        return months[month - 1]
    
    return 'Mês inválido'


def get_week_range(date: datetime) -> Tuple[datetime, datetime]:
    """
    Retorna o início e fim da semana para uma data
    Segunda a Domingo
    """
    if not date:
        return datetime.now(), datetime.now()
    
    # Encontrar a segunda-feira
    days_since_monday = date.weekday()
    start = date - timedelta(days=days_since_monday)
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Domingo é 6 dias depois
    end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    return start, end


# ==================== CACHE SIMPLES ====================

class SimpleCache:
    """Cache simples para melhorar performance"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 300):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Any:
        """Obtém valor do cache"""
        if key not in self.cache:
            return None
        
        # Verificar TTL
        if datetime.now().timestamp() - self.timestamps[key] > self.ttl:
            self.delete(key)
            return None
        
        return self.cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """Define valor no cache"""
        # Limpar cache se atingiu tamanho máximo
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.timestamps.keys(), key=lambda k: self.timestamps[k])
            self.delete(oldest_key)
        
        self.cache[key] = value
        self.timestamps[key] = datetime.now().timestamp()
    
    def delete(self, key: str) -> None:
        """Remove valor do cache"""
        self.cache.pop(key, None)
        self.timestamps.pop(key, None)
    
    def clear(self) -> None:
        """Limpa todo o cache"""
        self.cache.clear()
        self.timestamps.clear()


# ==================== ANALISADORES FINANCEIROS ====================

class FinancialAnalyzer:
    """Analisador avançado de métricas financeiras"""
    
    @staticmethod
    def calculate_health_score(
        income: Decimal,
        expenses: Decimal,
        savings_rate: Decimal,
        consistency_score: int = 50
    ) -> Tuple[int, str, Dict[str, Any]]:
        """
        Calcula score de saúde financeira com detalhamento
        """
        score = 0
        details = {}
        
        # Converter para float para cálculos
        income_float = float(income) if income else 0
        expenses_float = float(expenses) if expenses else 0
        savings_rate_float = float(savings_rate) if savings_rate else 0
        
        # Taxa de poupança (40 pontos max)
        if savings_rate_float >= 30:
            savings_points = 40
            details['savings_level'] = "Excelente"
        elif savings_rate_float >= 20:
            savings_points = 30
            details['savings_level'] = "Muito Boa"
        elif savings_rate_float >= 10:
            savings_points = 20
            details['savings_level'] = "Boa"
        elif savings_rate_float >= 5:
            savings_points = 10
            details['savings_level'] = "Regular"
        else:
            savings_points = 0
            details['savings_level'] = "Baixa"
        
        score += savings_points
        details['savings_points'] = savings_points
        
        # Equilíbrio receita/despesa (30 pontos max)
        if income_float > 0:
            expense_ratio = expenses_float / income_float
            if expense_ratio <= 0.7:  # Gasta 70% ou menos
                balance_points = 30
                details['expense_control'] = "Excelente"
            elif expense_ratio <= 0.8:
                balance_points = 25
                details['expense_control'] = "Muito Boa"
            elif expense_ratio <= 0.9:
                balance_points = 20
                details['expense_control'] = "Boa"
            elif expense_ratio <= 1.0:
                balance_points = 10
                details['expense_control'] = "Regular"
            else:
                balance_points = 0
                details['expense_control'] = "Ruim"
        else:
            balance_points = 0
            details['expense_control'] = "Sem dados"
        
        score += balance_points
        details['balance_points'] = balance_points
        
        # Consistência (20 pontos max)
        consistency_points = min(consistency_score * 20 // 100, 20)
        score += consistency_points
        details['consistency_points'] = consistency_points
        
        # Bônus por valor absoluto poupado (10 pontos max)
        savings_amount = income_float - expenses_float
        if savings_amount >= 1000:
            bonus_points = 10
        elif savings_amount >= 500:
            bonus_points = 5
        elif savings_amount >= 100:
            bonus_points = 2
        else:
            bonus_points = 0
        
        score += bonus_points
        details['bonus_points'] = bonus_points
        
        # Determinar status
        if score >= 85:
            status = "Excelente"
            emoji = "🟢"
        elif score >= 70:
            status = "Muito Boa"
            emoji = "🟢"
        elif score >= 55:
            status = "Boa"
            emoji = "🟡"
        elif score >= 40:
            status = "Regular"
            emoji = "🟠"
        else:
            status = "Precisa Melhorar"
            emoji = "🔴"
        
        details['status'] = status
        details['emoji'] = emoji
        details['total_score'] = score
        
        return score, f"{emoji} {status}", details
    
    @staticmethod
    def analyze_spending_patterns(transactions: List[Dict]) -> Dict[str, Any]:
        """
        Analisa padrões de gastos
        """
        if not transactions:
            return {'error': 'Sem dados suficientes'}
        
        # Agrupar por categoria
        by_category = {}
        by_day_of_week = [0] * 7
        by_hour = [0] * 24
        monthly_totals = []
        
        for t in transactions:
            # Por categoria
            category = t.get('category', 'Outros')
            amount = float(t.get('amount', 0))
            date = t.get('date')
            
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(amount)
            
            # Por dia da semana
            if date:
                by_day_of_week[date.weekday()] += amount
            
            # Por hora
            if date:
                by_hour[date.hour] += amount
        
        # Calcular insights
        insights = {
            'top_categories': sorted(
                [(cat, sum(amounts)) for cat, amounts in by_category.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5],
            'peak_spending_day': ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'][
                by_day_of_week.index(max(by_day_of_week))
            ] if max(by_day_of_week) > 0 else 'Nenhum',
            'peak_spending_hour': by_hour.index(max(by_hour)) if max(by_hour) > 0 else 0,
            'average_transaction': sum(t.get('amount', 0) for t in transactions) / len(transactions),
            'spending_consistency': FinancialAnalyzer._calculate_consistency(monthly_totals)
        }
        
        return insights
    
    @staticmethod
    def _calculate_consistency(values: List[float]) -> float:
        """
        Calcula consistência baseada no desvio padrão
        """
        if len(values) < 2:
            return 50.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5
        
        # Coefficient of variation (menor é melhor)
        cv = std_dev / mean if mean > 0 else 1
        
        # Converter para score (0-100, maior é melhor)
        consistency = max(0, 100 - (cv * 100))
        return min(100, consistency)
    
    @staticmethod
    def predict_monthly_expenses(historical_data: List[Decimal], trend_months: int = 3) -> Decimal:
        """
        Predição simples de gastos mensais baseada em tendência
        """
        if not historical_data or len(historical_data) < 2:
            return Decimal('0')
        
        # Usar apenas os últimos meses para tendência
        recent_data = historical_data[-trend_months:] if len(historical_data) >= trend_months else historical_data
        
        if len(recent_data) == 1:
            return recent_data[0]
        
        # Calcular tendência linear simples
        n = len(recent_data)
        x_mean = (n - 1) / 2
        y_mean = sum(recent_data) / n
        
        numerator = sum((i - x_mean) * (recent_data[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return recent_data[-1]
        
        slope = numerator / denominator
        prediction = recent_data[-1] + slope
        
        return max(Decimal('0'), prediction)


# ==================== COMPARADORES E RANKINGS ====================

class FinancialComparator:
    """Comparador de métricas financeiras"""
    
    @staticmethod
    def compare_periods(current: Dict, previous: Dict) -> Dict[str, Any]:
        """
        Compara dois períodos financeiros
        """
        comparison = {}
        
        metrics = ['total_income', 'total_expenses', 'balance', 'savings_rate']
        
        for metric in metrics:
            current_val = current.get(metric, 0)
            previous_val = previous.get(metric, 0)
            
            # Converter para float para cálculos
            if isinstance(current_val, Decimal):
                current_val = float(current_val)
            if isinstance(previous_val, Decimal):
                previous_val = float(previous_val)
            
            if previous_val != 0:
                change_pct = ((current_val - previous_val) / previous_val) * 100
            else:
                change_pct = 100 if current_val > 0 else 0
            
            comparison[metric] = {
                'current': current_val,
                'previous': previous_val,
                'change': current_val - previous_val,
                'change_pct': change_pct,
                'trend': TrendDirection.UP if change_pct > 5 else 
                        TrendDirection.DOWN if change_pct < -5 else 
                        TrendDirection.STABLE
            }
        
        return comparison
    
    @staticmethod
    def rank_categories(categories_data: Dict[str, Decimal]) -> List[Tuple[str, Decimal, float]]:
        """
        Ranqueia categorias por valor e percentual
        """
        if not categories_data:
            return []
        
        total = sum(categories_data.values())
        
        if total == 0:
            return []
        
        ranked = [
            (category, amount, float(amount / total * 100))
            for category, amount in categories_data.items()
        ]
        
        return sorted(ranked, key=lambda x: x[1], reverse=True)


# ==================== UTILITÁRIOS DE BACKUP E EXPORT ====================

class DataExporter:
    """Utilitários para exportação de dados"""
    
    @staticmethod
    def prepare_transactions_export(transactions: List) -> List[Dict]:
        """
        Prepara dados de transações para exportação
        """
        if not transactions:
            return []
        
        export_data = []
        
        for t in transactions:
            try:
                export_data.append({
                    'Data': t.date.strftime('%d/%m/%Y') if t.date else '',
                    'Descrição': t.description or '',
                    'Categoria': t.category.name if hasattr(t, 'category') and t.category else 'N/A',
                    'Tipo': 'Receita' if t.type.value == 'income' else 'Despesa',
                    'Valor': float(t.amount) if t.amount else 0,
                    'Método': t.payment_method or '',
                    'Observações': t.notes or '',
                    'Tags': t.tags or ''
                })
            except Exception as e:
                logger.error(f"Erro ao exportar transação {t.id}: {e}")
                continue
        
        return export_data
    
    @staticmethod
    def prepare_investments_export(investments: List) -> List[Dict]:
        """
        Prepara dados de investimentos para exportação
        """
        if not investments:
            return []
        
        export_data = []
        
        for inv in investments:
            try:
                export_data.append({
                    'Ticker': inv.ticker or '',
                    'Nome': inv.name or inv.ticker or '',
                    'Tipo': inv.type.value if inv.type else '',
                    'Quantidade': float(inv.quantity) if inv.quantity else 0,
                    'Preço_Médio': float(inv.avg_price) if inv.avg_price else 0,
                    'Total_Investido': float(inv.total_invested) if hasattr(inv, 'total_invested') else 0,
                    'Data_Compra': inv.purchase_date.strftime('%d/%m/%Y') if inv.purchase_date else '',
                    'Corretora': inv.broker or '',
                    'Status': 'Ativo' if inv.is_active else 'Inativo'
                })
            except Exception as e:
                logger.error(f"Erro ao exportar investimento {inv.id}: {e}")
                continue
        
        return export_data


# ==================== UTILITÁRIOS ESPECÍFICOS DO TELEGRAM ====================

def get_user_from_update(update: Update, session: Session) -> User:
    """
    Obtém usuário do banco a partir do Update, com tratamento de erro
    """
    telegram_user = update.effective_user
    
    # Tentar usar callback_query se não há message
    if not telegram_user and hasattr(update, 'callback_query') and update.callback_query:
        telegram_user = update.callback_query.from_user
    
    if not telegram_user:
        raise ValueError("Não foi possível identificar o usuário")
    
    try:
        user, _ = UserService.get_or_create_user(
            session=session,
            telegram_id=telegram_user.id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name
        )
        return user
    except Exception as e:
        logger.error(f"Erro ao obter/criar usuário {telegram_user.id}: {e}")
        raise


def create_deep_link(bot_username: str, payload: str) -> str:
    """
    Cria deep link para o bot
    """
    if not bot_username or not payload:
        return ""
    
    # Remover @ se presente
    bot_username = bot_username.replace('@', '')
    
    # Sanitizar payload
    payload = re.sub(r'[^a-zA-Z0-9_-]', '', payload)
    
    return f"https://t.me/{bot_username}?start={payload}"


def format_user_mention(user_id: int, name: str) -> str:
    """
    Formata menção de usuário
    """
    if not user_id or not name:
        return "Usuário"
    
    safe_name = escape_markdown_v2(name)
    return f"[{safe_name}](tg://user?id={user_id})"


# ==================== MÉTRICAS E MONITORAMENTO ====================

class MetricsCollector:
    """Coletor de métricas para monitoramento"""
    
    @staticmethod
    def log_user_action(user_id: int, action: str, metadata: Dict = None):
        """Registra ação do usuário para análise"""
        try:
            safe_metadata = json.dumps(metadata) if metadata else "{}"
            logger.info(
                f"USER_ACTION: user_id={user_id}, action={action}, metadata={safe_metadata}"
            )
        except Exception as e:
            logger.error(f"Erro ao registrar ação do usuário: {e}")
    
    @staticmethod
    def log_error(error: Exception, context: Dict = None):
        """Registra erro com contexto"""
        try:
            safe_context = json.dumps(context) if context else "{}"
            logger.error(
                f"ERROR: {error.__class__.__name__}: {str(error)}, context={safe_context}",
                exc_info=True
            )
        except Exception as e:
            logger.error(f"Erro ao registrar erro: {e}")
    
    @staticmethod
    def log_performance(operation: str, duration: float, success: bool = True):
        """Registra performance de operações"""
        try:
            logger.info(
                f"PERFORMANCE: operation={operation}, duration={duration:.3f}s, success={success}"
            )
        except Exception as e:
            logger.error(f"Erro ao registrar performance: {e}")


# ==================== DECORADORES ÚTEIS ====================

def timing_decorator(func):
    """Decorator para medir tempo de execução"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            success = True
            return result
        except Exception as e:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            MetricsCollector.log_performance(
                func.__name__, 
                duration, 
                success
            )
    return wrapper


def error_handler_decorator(func):
    """Decorator para capturar e logar erros"""
    @wraps(func)
    async def wrapper(update: Update, context, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            user_id = update.effective_user.id if update.effective_user else None
            MetricsCollector.log_error(e, {
                'function': func.__name__,
                'user_id': user_id,
                'update_type': type(update).__name__
            })
            
            # Tentar enviar mensagem de erro amigável
            try:
                if update.message:
                    await update.message.reply_text(
                        "❌ Ocorreu um erro inesperado. Nossa equipe foi notificada."
                    )
                elif hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.answer(
                        "❌ Erro inesperado. Tente novamente.",
                        show_alert=True
                    )
            except:
                pass  # Se não conseguir enviar mensagem, apenas prosseguir
            
            raise
    return wrapper


# ==================== INSTÂNCIA GLOBAL DE CACHE ====================

# Cache global para uso em toda a aplicação
app_cache = SimpleCache(max_size=200, ttl_seconds=600)


# ==================== FUNÇÕES DE COMPATIBILIDADE ====================

# Manter compatibilidade com versão anterior
def parse_amount(text: str) -> Decimal:
    """Função de compatibilidade - converte texto em Decimal"""
    result = AmountValidator.parse_and_validate(text)
    if result.is_valid:
        return result.value
    else:
        raise ValueError(result.error_message)


def parse_date(text: str) -> datetime:
    """Função de compatibilidade - converte texto em datetime"""
    result = DateValidator.parse_and_validate(text)
    if result.is_valid:
        return result.value
    else:
        raise ValueError(result.error_message)


def validate_amount(amount: Decimal) -> Optional[str]:
    """Função de compatibilidade - valida valor monetário"""
    if not amount:
        return "Valor inválido"
    
    if amount < Config.MIN_TRANSACTION_AMOUNT:
        return f"Valor mínimo é {format_currency(Config.MIN_TRANSACTION_AMOUNT)}"
    
    if amount > Config.MAX_TRANSACTION_AMOUNT:
        return f"Valor máximo é {format_currency(Config.MAX_TRANSACTION_AMOUNT)}"
    
    return None


def is_valid_ticker(ticker: str) -> bool:
    """Função de compatibilidade - valida ticker"""
    result = TickerValidator.validate_ticker(ticker)
    return result.is_valid


# ==================== FUNÇÕES DE UTILIDADE GERAL ====================

def safe_float(value: Any, default: float = 0.0) -> float:
    """Converte valor para float de forma segura"""
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, str):
            return float(value.replace(',', '.'))
        return default
    except (ValueError, TypeError):
        return default


def safe_decimal(value: Any, default: str = "0.00") -> Decimal:
    """Converte valor para Decimal de forma segura"""
    try:
        if value is None:
            return Decimal(default)
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            cleaned = value.replace(',', '.')
            return Decimal(cleaned)
        return Decimal(default)
    except (ValueError, TypeError, InvalidOperation):
        return Decimal(default)


def chunks(lst: List, n: int) -> List[List]:
    """Divide lista em chunks de tamanho n"""
    if not lst or n <= 0:
        return []
    
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def flatten_dict(d: Dict, parent_key: str = '', sep: str = '.') -> Dict:
    """Aplana dicionário aninhado"""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


# ==================== CONFIGURAÇÕES E CONSTANTES ====================

# Configurações do cache
CACHE_DEFAULT_TTL = 300  # 5 minutos
CACHE_MAX_SIZE = 200

# Configurações de rate limiting
DEFAULT_RATE_LIMIT = 30  # requests por minuto
DEFAULT_WINDOW = 60  # segundos

# Formatos de data aceitos
DATE_FORMATS = [
    '%d/%m/%Y',
    '%d/%m/%y', 
    '%Y/%m/%d',
    '%d/%m',
    '%m/%d/%Y',
    '%Y-%m-%d'
]

# Emojis padronizados
TREND_EMOJIS = {
    'up': '📈',
    'down': '📉',
    'stable': '➡️',
    'volatile': '📊'
}

HEALTH_EMOJIS = {
    'excellent': '🟢',
    'good': '🟡', 
    'warning': '🟠',
    'critical': '🔴'
}