"""
Serviços de lógica de negócio do Finance Bot
"""
import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any

from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import (
    User, Transaction, Investment, Category, Alert,
    TransactionType, InvestmentType, AlertType
)
from config import Config

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Exceção base para erros de serviços"""
    pass


class ValidationError(ServiceError):
    """Erro de validação de dados"""
    pass


class NotFoundError(ServiceError):
    """Erro quando recurso não é encontrado"""
    pass


class PermissionError(ServiceError):
    """Erro de permissão de acesso"""
    pass


class UserService:
    """Serviço para gerenciamento de usuários"""
    
    @staticmethod
    def get_or_create_user(
        session: Session,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Tuple[User, bool]:
        """
        Obtém ou cria um usuário
        
        Args:
            session: Sessão do banco de dados
            telegram_id: ID único do usuário no Telegram
            username: Nome de usuário do Telegram (opcional)
            first_name: Primeiro nome (opcional)
            last_name: Último nome (opcional)
            
        Returns:
            Tuple[User, bool]: (usuário, foi_criado)
            
        Raises:
            ServiceError: Em caso de erro no banco de dados
        """
        try:
            user = session.query(User).filter(
                User.telegram_id == telegram_id
            ).first()
            
            if user:
                # Atualizar informações se mudaram
                updated = False
                
                if username and user.username != username:
                    user.username = username
                    updated = True
                    
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    updated = True
                    
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                
                if updated:
                    session.commit()
                    logger.info(f"Usuário atualizado: {user.telegram_id}")
                
                return user, False
            
            # Criar novo usuário
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            
            session.add(user)
            session.flush()  # Para obter o ID antes do commit
            
            # Criar categorias padrão
            UserService._create_default_categories(session, user)
            
            session.commit()
            
            logger.info(f"Novo usuário criado: {user.telegram_id} (ID: {user.id})")
            
            return user, True
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao criar/atualizar usuário {telegram_id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def _create_default_categories(session: Session, user: User) -> None:
        """Cria categorias padrão para novo usuário"""
        from models import DEFAULT_CATEGORIES
        
        try:
            for transaction_type, categories in DEFAULT_CATEGORIES.items():
                for name, icon, description in categories:
                    category = Category(
                        user_id=user.id,
                        name=name,
                        type=transaction_type,
                        icon=icon,
                        description=description,
                        is_system=True
                    )
                    session.add(category)
            
            logger.info(f"Categorias padrão criadas para usuário {user.id}")
            
        except Exception as e:
            logger.error(f"Erro ao criar categorias padrão para usuário {user.id}: {e}")
            raise ServiceError("Erro ao criar categorias padrão")
    
    @staticmethod
    def update_profile(
        session: Session,
        user: User,
        **kwargs
    ) -> User:
        """
        Atualiza o perfil do usuário
        
        Args:
            session: Sessão do banco de dados
            user: Usuário a ser atualizado
            **kwargs: Campos a serem atualizados
            
        Returns:
            User: Usuário atualizado
            
        Raises:
            ValidationError: Se dados inválidos
            ServiceError: Em caso de erro no banco
        """
        try:
            # Validar campos permitidos
            allowed_fields = {
                'username', 'first_name', 'last_name', 'investor_profile',
                'monthly_income', 'savings_goal', 'timezone', 'notifications_enabled'
            }
            
            invalid_fields = set(kwargs.keys()) - allowed_fields
            if invalid_fields:
                raise ValidationError(f"Campos inválidos: {invalid_fields}")
            
            # Validações específicas
            if 'monthly_income' in kwargs:
                income = kwargs['monthly_income']
                if income is not None and income < 0:
                    raise ValidationError("Renda mensal não pode ser negativa")
            
            if 'savings_goal' in kwargs:
                goal = kwargs['savings_goal']
                if goal is not None and goal < 0:
                    raise ValidationError("Meta de poupança não pode ser negativa")
            
            # Aplicar atualizações
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            session.commit()
            
            logger.info(f"Perfil do usuário {user.id} atualizado: {list(kwargs.keys())}")
            
            return user
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao atualizar perfil do usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def get_user_stats(session: Session, user: User) -> Dict[str, Any]:
        """
        Obtém estatísticas do usuário
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            
        Returns:
            Dict: Estatísticas do usuário
        """
        try:
            # Contar transações
            transaction_count = session.query(Transaction).filter(
                Transaction.user_id == user.id
            ).count()
            
            # Contar investimentos ativos
            investment_count = session.query(Investment).filter(
                Investment.user_id == user.id,
                Investment.is_active == True
            ).count()
            
            # Dias desde cadastro
            days_since_join = (datetime.now() - user.created_at).days
            
            # Primeira e última transação
            first_transaction = session.query(Transaction).filter(
                Transaction.user_id == user.id
            ).order_by(Transaction.date.asc()).first()
            
            last_transaction = session.query(Transaction).filter(
                Transaction.user_id == user.id
            ).order_by(Transaction.date.desc()).first()
            
            return {
                'transaction_count': transaction_count,
                'investment_count': investment_count,
                'days_since_join': days_since_join,
                'first_transaction_date': first_transaction.date if first_transaction else None,
                'last_transaction_date': last_transaction.date if last_transaction else None,
                'categories_count': len(user.categories)
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao obter estatísticas do usuário {user.id}: {e}")
            return {}


class TransactionService:
    """Serviço para gerenciamento de transações"""
    
    @staticmethod
    def create_transaction(
        session: Session,
        user: User,
        category: Category,
        amount: Decimal,
        description: str,
        payment_method: str,
        date: datetime,
        transaction_type: TransactionType,
        **kwargs
    ) -> Transaction:
        """
        Cria uma nova transação
        
        Args:
            session: Sessão do banco de dados
            user: Usuário proprietário
            category: Categoria da transação
            amount: Valor da transação
            description: Descrição
            payment_method: Método de pagamento/recebimento
            date: Data da transação
            transaction_type: Tipo da transação (INCOME/EXPENSE)
            **kwargs: Campos opcionais (notes, tags, is_recurring)
            
        Returns:
            Transaction: Transação criada
            
        Raises:
            ValidationError: Se dados inválidos
            PermissionError: Se categoria não pertence ao usuário
            ServiceError: Em caso de erro no banco
        """
        try:
            # Validações
            TransactionService._validate_transaction_data(
                user, category, amount, description, transaction_type
            )
            
            # Truncar descrição se necessário
            description = description[:Config.MAX_DESCRIPTION_LENGTH]
            
            transaction = Transaction(
                user_id=user.id,
                category_id=category.id,
                amount=amount,
                type=transaction_type,
                description=description,
                payment_method=payment_method,
                date=date,
                notes=kwargs.get('notes'),
                tags=kwargs.get('tags'),
                is_recurring=kwargs.get('is_recurring', False)
            )
            
            session.add(transaction)
            session.commit()
            
            logger.info(
                f"Transação criada: {transaction.type.value} "
                f"R$ {transaction.amount} para usuário {user.id}"
            )
            
            return transaction
            
        except ValidationError:
            raise
        except PermissionError:
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao criar transação para usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def _validate_transaction_data(
        user: User,
        category: Category,
        amount: Decimal,
        description: str,
        transaction_type: TransactionType
    ) -> None:
        """Valida dados da transação"""
        
        # Validar se categoria pertence ao usuário
        if category.user_id != user.id:
            raise PermissionError("Categoria não pertence ao usuário")
        
        # Validar tipo da categoria
        if category.type != transaction_type:
            raise ValidationError(
                f"Categoria '{category.name}' é do tipo {category.type.value}, "
                f"mas a transação é do tipo {transaction_type.value}"
            )
        
        # Validar categoria ativa
        if not category.is_active:
            raise ValidationError(f"Categoria '{category.name}' está inativa")
        
        # Validar limites de valor
        if amount < Config.MIN_TRANSACTION_AMOUNT:
            raise ValidationError(
                f"Valor mínimo é R$ {Config.MIN_TRANSACTION_AMOUNT}"
            )
        
        if amount > Config.MAX_TRANSACTION_AMOUNT:
            raise ValidationError(
                f"Valor máximo é R$ {Config.MAX_TRANSACTION_AMOUNT}"
            )
        
        # Validar descrição
        if not description or not description.strip():
            raise ValidationError("Descrição não pode estar vazia")
    
    @staticmethod
    def get_user_transactions(
        session: Session,
        user: User,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[TransactionType] = None,
        category_id: Optional[int] = None
    ) -> List[Transaction]:
        """
        Obtém transações do usuário com filtros
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            limit: Limite de resultados
            offset: Offset para paginação
            start_date: Data inicial (opcional)
            end_date: Data final (opcional)
            transaction_type: Tipo de transação (opcional)
            category_id: ID da categoria (opcional)
            
        Returns:
            List[Transaction]: Lista de transações
            
        Raises:
            ValidationError: Se parâmetros inválidos
            ServiceError: Em caso de erro no banco
        """
        try:
            # Validar limites
            if limit <= 0 or limit > Config.MAX_TRANSACTIONS_PER_PAGE:
                limit = Config.MAX_TRANSACTIONS_PER_PAGE
            
            if offset < 0:
                offset = 0
            
            query = session.query(Transaction).filter(
                Transaction.user_id == user.id
            )
            
            # Aplicar filtros
            if start_date:
                query = query.filter(Transaction.date >= start_date)
            
            if end_date:
                query = query.filter(Transaction.date <= end_date)
            
            if transaction_type:
                query = query.filter(Transaction.type == transaction_type)
            
            if category_id:
                # Validar se categoria pertence ao usuário
                category = session.query(Category).filter(
                    Category.id == category_id,
                    Category.user_id == user.id
                ).first()
                
                if not category:
                    raise ValidationError("Categoria não encontrada ou não pertence ao usuário")
                
                query = query.filter(Transaction.category_id == category_id)
            
            return query.order_by(
                Transaction.date.desc(),
                Transaction.id.desc()
            ).limit(limit).offset(offset).all()
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar transações do usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def get_monthly_summary(
        session: Session,
        user: User,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """
        Obtém resumo financeiro mensal
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            year: Ano
            month: Mês (1-12)
            
        Returns:
            Dict: Resumo financeiro do mês
            
        Raises:
            ValidationError: Se ano/mês inválidos
            ServiceError: Em caso de erro no banco
        """
        try:
            # Validar parâmetros
            if not (1 <= month <= 12):
                raise ValidationError("Mês deve estar entre 1 e 12")
            
            if year < 2000 or year > datetime.now().year + 1:
                raise ValidationError("Ano inválido")
            
            # Calcular período
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            
            # Buscar transações do período
            transactions = session.query(Transaction).filter(
                Transaction.user_id == user.id,
                Transaction.date >= start_date,
                Transaction.date < end_date
            ).all()
            
            # Calcular totais
            total_income = Decimal('0')
            total_expenses = Decimal('0')
            expenses_by_category = {}
            income_by_category = {}
            
            for t in transactions:
                if t.type == TransactionType.INCOME:
                    total_income += t.amount
                    category_name = t.category.name
                    
                    if category_name not in income_by_category:
                        income_by_category[category_name] = Decimal('0')
                    income_by_category[category_name] += t.amount
                    
                else:  # EXPENSE
                    total_expenses += t.amount
                    category_name = t.category.name
                    
                    if category_name not in expenses_by_category:
                        expenses_by_category[category_name] = Decimal('0')
                    expenses_by_category[category_name] += t.amount
            
            # Calcular métricas
            balance = total_income - total_expenses
            savings_rate = (
                (balance / total_income * 100) 
                if total_income > 0 
                else Decimal('0')
            )
            
            # Número de dias no mês
            days_in_month = (end_date - start_date).days
            daily_average_expense = (
                total_expenses / Decimal(str(days_in_month))
                if total_expenses > 0 and days_in_month > 0
                else Decimal('0')
            )
            
            return {
                'period': f"{month:02d}/{year}",
                'start_date': start_date,
                'end_date': end_date,
                'total_income': total_income,
                'total_expenses': total_expenses,
                'balance': balance,
                'savings_rate': float(savings_rate),
                'expenses_by_category': {k: float(v) for k, v in expenses_by_category.items()},
                'income_by_category': {k: float(v) for k, v in income_by_category.items()},
                'transaction_count': len(transactions),
                'daily_average_expense': float(daily_average_expense),
                'days_in_period': days_in_month
            }
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            logger.error(f"Erro ao obter resumo mensal para usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def get_financial_health_score(
        session: Session,
        user: User,
        months_to_analyze: int = 3
    ) -> Tuple[int, str]:
        """
        Calcula score de saúde financeira (0-100)
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            months_to_analyze: Número de meses para análise
            
        Returns:
            Tuple[int, str]: (score, status)
            
        Raises:
            ServiceError: Em caso de erro no banco
        """
        try:
            # Obter resumos dos últimos meses
            now = datetime.now()
            summaries = []
            
            for i in range(months_to_analyze):
                date = now - timedelta(days=30 * i)
                try:
                    summary = TransactionService.get_monthly_summary(
                        session, user, date.year, date.month
                    )
                    summaries.append(summary)
                except Exception:
                    continue  # Ignorar meses com erro
            
            if not summaries or all(s['total_income'] == 0 for s in summaries):
                return 50, "Sem dados suficientes"
            
            # Filtrar apenas meses com receita
            valid_summaries = [s for s in summaries if s['total_income'] > 0]
            
            if not valid_summaries:
                return 50, "Sem dados suficientes"
            
            # Calcular médias
            avg_savings_rate = sum(s['savings_rate'] for s in valid_summaries) / len(valid_summaries)
            avg_balance = sum(s['balance'] for s in valid_summaries) / len(valid_summaries)
            
            # Calcular score baseado em múltiplos fatores
            score = 50  # Base
            
            # Taxa de poupança (0-40 pontos)
            if avg_savings_rate >= 30:
                score += 40
            elif avg_savings_rate >= 20:
                score += 30
            elif avg_savings_rate >= 10:
                score += 20
            elif avg_savings_rate >= 5:
                score += 10
            elif avg_savings_rate < 0:
                score -= 20  # Penalizar gastos acima da receita
            
            # Consistência de saldo positivo (0-20 pontos)
            positive_months = sum(1 for s in valid_summaries if s['balance'] > 0)
            consistency_ratio = positive_months / len(valid_summaries)
            score += int(consistency_ratio * 20)
            
            # Estabilidade de receita (0-10 pontos)
            if len(valid_summaries) > 1:
                incomes = [s['total_income'] for s in valid_summaries]
                avg_income = sum(incomes) / len(incomes)
                income_stability = 1 - (max(incomes) - min(incomes)) / avg_income
                score += int(max(0, income_stability) * 10)
            
            # Garantir que score está entre 0 e 100
            score = max(0, min(100, score))
            
            # Determinar status
            if score >= 80:
                status = "Excelente"
            elif score >= 60:
                status = "Boa"
            elif score >= 40:
                status = "Regular"
            else:
                status = "Precisa melhorar"
            
            return score, status
            
        except Exception as e:
            logger.error(f"Erro ao calcular score de saúde financeira para usuário {user.id}: {e}")
            return 50, "Erro no cálculo"
    
    @staticmethod
    def delete_transaction(
        session: Session,
        user: User,
        transaction_id: int
    ) -> bool:
        """
        Exclui uma transação
        
        Args:
            session: Sessão do banco de dados
            user: Usuário proprietário
            transaction_id: ID da transação
            
        Returns:
            bool: True se excluída com sucesso
            
        Raises:
            NotFoundError: Se transação não encontrada
            PermissionError: Se transação não pertence ao usuário
            ServiceError: Em caso de erro no banco
        """
        try:
            transaction = session.query(Transaction).filter(
                Transaction.id == transaction_id
            ).first()
            
            if not transaction:
                raise NotFoundError("Transação não encontrada")
            
            if transaction.user_id != user.id:
                raise PermissionError("Transação não pertence ao usuário")
            
            session.delete(transaction)
            session.commit()
            
            logger.info(f"Transação {transaction_id} excluída pelo usuário {user.id}")
            
            return True
            
        except (NotFoundError, PermissionError):
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao excluir transação {transaction_id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")


class InvestmentService:
    """Serviço para gerenciamento de investimentos"""
    
    @staticmethod
    def create_investment(
        session: Session,
        user: User,
        ticker: str,
        investment_type: InvestmentType,
        quantity: Decimal,
        price: Decimal,
        purchase_date: datetime,
        broker: Optional[str] = None
    ) -> Investment:
        """
        Cria um novo investimento ou atualiza existente
        
        Args:
            session: Sessão do banco de dados
            user: Usuário proprietário
            ticker: Código do ativo
            investment_type: Tipo de investimento
            quantity: Quantidade comprada
            price: Preço unitário
            purchase_date: Data da compra
            broker: Corretora (opcional)
            
        Returns:
            Investment: Investimento criado ou atualizado
            
        Raises:
            ValidationError: Se dados inválidos
            ServiceError: Em caso de erro no banco
        """
        try:
            # Validações
            InvestmentService._validate_investment_data(
                ticker, quantity, price, purchase_date
            )
            
            ticker = ticker.upper().strip()
            
            # Verificar se já existe investimento ativo deste ticker
            existing = session.query(Investment).filter(
                Investment.user_id == user.id,
                Investment.ticker == ticker,
                Investment.is_active == True
            ).first()
            
            if existing:
                # Calcular novo preço médio ponderado
                total_quantity = existing.quantity + quantity
                total_value = (existing.quantity * existing.avg_price) + (quantity * price)
                new_avg_price = total_value / total_quantity
                
                existing.quantity = total_quantity
                existing.avg_price = new_avg_price
                
                session.commit()
                
                logger.info(
                    f"Investimento atualizado: {ticker} "
                    f"Nova quantidade: {total_quantity} (usuário {user.id})"
                )
                
                return existing
            
            # Criar novo investimento
            investment = Investment(
                user_id=user.id,
                ticker=ticker,
                name=ticker,  # Pode ser atualizado depois com nome real
                type=investment_type,
                quantity=quantity,
                avg_price=price,
                purchase_date=purchase_date,
                broker=broker
            )
            
            session.add(investment)
            session.commit()
            
            logger.info(
                f"Investimento criado: {ticker} "
                f"Quantidade: {quantity} (usuário {user.id})"
            )
            
            return investment
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao criar investimento para usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def _validate_investment_data(
        ticker: str,
        quantity: Decimal,
        price: Decimal,
        purchase_date: datetime
    ) -> None:
        """Valida dados do investimento"""
        
        if not ticker or not ticker.strip():
            raise ValidationError("Ticker não pode estar vazio")
        
        if len(ticker.strip()) < 3 or len(ticker.strip()) > 10:
            raise ValidationError("Ticker deve ter entre 3 e 10 caracteres")
        
        if quantity <= 0:
            raise ValidationError("Quantidade deve ser maior que zero")
        
        if price <= 0:
            raise ValidationError("Preço deve ser maior que zero")
        
        if purchase_date > datetime.now():
            raise ValidationError("Data de compra não pode ser no futuro")
        
        # Validar valor total não excessivo
        total_value = quantity * price
        if total_value > Decimal('10000000'):  # 10 milhões
            raise ValidationError("Valor total do investimento muito alto")
    
    @staticmethod
    def sell_investment(
        session: Session,
        user: User,
        investment_id: int,
        quantity: Decimal,
        price: Decimal,
        sale_date: datetime
    ) -> Investment:
        """
        Registra venda de investimento
        
        Args:
            session: Sessão do banco de dados
            user: Usuário proprietário
            investment_id: ID do investimento
            quantity: Quantidade vendida
            price: Preço de venda
            sale_date: Data da venda
            
        Returns:
            Investment: Investimento atualizado
            
        Raises:
            NotFoundError: Se investimento não encontrado
            PermissionError: Se investimento não pertence ao usuário
            ValidationError: Se dados inválidos
            ServiceError: Em caso de erro no banco
        """
        try:
            investment = session.query(Investment).filter(
                Investment.id == investment_id
            ).first()
            
            if not investment:
                raise NotFoundError("Investimento não encontrado")
            
            if investment.user_id != user.id:
                raise PermissionError("Investimento não pertence ao usuário")
            
            if not investment.is_active:
                raise ValidationError("Investimento já foi totalmente vendido")
            
            # Validações
            if quantity <= 0:
                raise ValidationError("Quantidade de venda deve ser maior que zero")
            
            if quantity > investment.current_quantity:
                raise ValidationError(
                    f"Quantidade de venda ({quantity}) maior que disponível "
                    f"({investment.current_quantity})"
                )
            
            if price <= 0:
                raise ValidationError("Preço de venda deve ser maior que zero")
            
            if sale_date > datetime.now():
                raise ValidationError("Data de venda não pode ser no futuro")
            
            # Atualizar investimento
            investment.sale_quantity = (
                (investment.sale_quantity or Decimal('0')) + quantity
            )
            
            # Se vendeu tudo, marcar como inativo
            if investment.current_quantity == 0:
                investment.is_active = False
                investment.sale_date = sale_date
                investment.sale_price = price
            
            session.commit()
            
            logger.info(
                f"Venda registrada: {investment.ticker} "
                f"Quantidade: {quantity} Preço: {price} (usuário {user.id})"
            )
            
            return investment
            
        except (NotFoundError, PermissionError, ValidationError):
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao registrar venda do investimento {investment_id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def get_portfolio_summary(
        session: Session,
        user: User
    ) -> Dict[str, Any]:
        """
        Obtém resumo da carteira de investimentos
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            
        Returns:
            Dict: Resumo da carteira
            
        Raises:
            ServiceError: Em caso de erro no banco
        """
        try:
            investments = session.query(Investment).filter(
                Investment.user_id == user.id,
                Investment.is_active == True
            ).all()
            
            if not investments:
                return {
                    'total_invested': Decimal('0'),
                    'total_current': Decimal('0'),
                    'total_profit': Decimal('0'),
                    'profit_percentage': Decimal('0'),
                    'by_type': {},
                    'investments': [],
                    'asset_count': 0,
                    'diversification_score': 0
                }
            
            # Calcular totais por tipo
            by_type = {}
            total_invested = Decimal('0')
            
            for inv in investments:
                inv_type = inv.type.value
                if inv_type not in by_type:
                    by_type[inv_type] = {
                        'count': 0,
                        'total_invested': Decimal('0'),
                        'percentage': Decimal('0'),
                        'assets': []
                    }
                
                by_type[inv_type]['count'] += 1
                by_type[inv_type]['total_invested'] += inv.total_invested
                by_type[inv_type]['assets'].append(inv.ticker)
                total_invested += inv.total_invested
            
            # Calcular percentuais
            for inv_type in by_type:
                if total_invested > 0:
                    by_type[inv_type]['percentage'] = (
                        by_type[inv_type]['total_invested'] / total_invested * 100
                    )
                
                # Converter Decimal para float para serialização
                by_type[inv_type]['total_invested'] = float(by_type[inv_type]['total_invested'])
                by_type[inv_type]['percentage'] = float(by_type[inv_type]['percentage'])
            
            # Calcular score de diversificação
            num_assets = len(investments)
            num_types = len(by_type)
            diversification_score = min(100, (num_assets * 5) + (num_types * 15))
            
            # Por enquanto, usar valor investido como valor atual
            # Em produção, buscar valores atuais de uma API de mercado
            total_current = total_invested
            total_profit = total_current - total_invested
            profit_percentage = (
                (total_profit / total_invested * 100)
                if total_invested > 0
                else Decimal('0')
            )
            
            return {
                'total_invested': float(total_invested),
                'total_current': float(total_current),
                'total_profit': float(total_profit),
                'profit_percentage': float(profit_percentage),
                'by_type': by_type,
                'investments': investments,
                'asset_count': num_assets,
                'diversification_score': diversification_score
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao obter resumo da carteira do usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def get_user_investments(
        session: Session,
        user: User,
        active_only: bool = True,
        investment_type: Optional[InvestmentType] = None
    ) -> List[Investment]:
        """
        Obtém investimentos do usuário
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            active_only: Se deve retornar apenas investimentos ativos
            investment_type: Filtrar por tipo de investimento
            
        Returns:
            List[Investment]: Lista de investimentos
            
        Raises:
            ServiceError: Em caso de erro no banco
        """
        try:
            query = session.query(Investment).filter(
                Investment.user_id == user.id
            )
            
            if active_only:
                query = query.filter(Investment.is_active == True)
            
            if investment_type:
                query = query.filter(Investment.type == investment_type)
            
            return query.order_by(
                Investment.purchase_date.desc(),
                Investment.ticker
            ).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar investimentos do usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")


class CategoryService:
    """Serviço para gerenciamento de categorias"""
    
    @staticmethod
    def create_category(
        session: Session,
        user: User,
        name: str,
        category_type: TransactionType,
        description: Optional[str] = None,
        icon: Optional[str] = None
    ) -> Category:
        """
        Cria uma nova categoria
        
        Args:
            session: Sessão do banco de dados
            user: Usuário proprietário
            name: Nome da categoria
            category_type: Tipo da categoria (INCOME/EXPENSE)
            description: Descrição (opcional)
            icon: Ícone emoji (opcional)
            
        Returns:
            Category: Categoria criada
            
        Raises:
            ValidationError: Se dados inválidos ou categoria já existe
            ServiceError: Em caso de erro no banco
        """
        try:
            # Validações
            CategoryService._validate_category_data(name, description, icon)
            
            name = name.strip()
            
            # Verificar se já existe categoria com mesmo nome e tipo
            existing = session.query(Category).filter(
                Category.user_id == user.id,
                func.lower(Category.name) == func.lower(name),
                Category.type == category_type
            ).first()
            
            if existing:
                raise ValidationError(f"Categoria '{name}' já existe para este tipo")
            
            # Verificar limite de categorias
            count = session.query(Category).filter(
                Category.user_id == user.id
            ).count()
            
            if count >= Config.MAX_CATEGORIES_PER_USER:
                raise ValidationError(
                    f"Limite de {Config.MAX_CATEGORIES_PER_USER} categorias atingido"
                )
            
            category = Category(
                user_id=user.id,
                name=name,
                type=category_type,
                description=description,
                icon=icon,
                is_system=False
            )
            
            session.add(category)
            session.commit()
            
            logger.info(f"Categoria criada: '{name}' para usuário {user.id}")
            
            return category
            
        except ValidationError:
            raise
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Erro de integridade ao criar categoria: {e}")
            raise ValidationError("Categoria já existe ou dados inválidos")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao criar categoria para usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def _validate_category_data(
        name: str,
        description: Optional[str] = None,
        icon: Optional[str] = None
    ) -> None:
        """Valida dados da categoria"""
        
        if not name or not name.strip():
            raise ValidationError("Nome da categoria não pode estar vazio")
        
        if len(name.strip()) > 100:
            raise ValidationError("Nome da categoria muito longo (máximo 100 caracteres)")
        
        if description and len(description) > 255:
            raise ValidationError("Descrição muito longa (máximo 255 caracteres)")
        
        if icon and len(icon) > 10:
            raise ValidationError("Ícone muito longo (máximo 10 caracteres)")
    
    @staticmethod
    def get_user_categories(
        session: Session,
        user: User,
        category_type: Optional[TransactionType] = None,
        active_only: bool = True,
        include_system: bool = True
    ) -> List[Category]:
        """
        Obtém categorias do usuário
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            category_type: Filtrar por tipo (opcional)
            active_only: Se deve retornar apenas categorias ativas
            include_system: Se deve incluir categorias do sistema
            
        Returns:
            List[Category]: Lista de categorias
            
        Raises:
            ServiceError: Em caso de erro no banco
        """
        try:
            query = session.query(Category).filter(
                Category.user_id == user.id
            )
            
            if category_type:
                query = query.filter(Category.type == category_type)
            
            if active_only:
                query = query.filter(Category.is_active == True)
            
            if not include_system:
                query = query.filter(Category.is_system == False)
            
            return query.order_by(
                Category.is_system.asc(),  # Categorias personalizadas primeiro
                Category.name
            ).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar categorias do usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def update_category(
        session: Session,
        user: User,
        category_id: int,
        **kwargs
    ) -> Category:
        """
        Atualiza uma categoria
        
        Args:
            session: Sessão do banco de dados
            user: Usuário proprietário
            category_id: ID da categoria
            **kwargs: Campos a serem atualizados
            
        Returns:
            Category: Categoria atualizada
            
        Raises:
            NotFoundError: Se categoria não encontrada
            PermissionError: Se categoria não pertence ao usuário
            ValidationError: Se dados inválidos
            ServiceError: Em caso de erro no banco
        """
        try:
            category = session.query(Category).filter(
                Category.id == category_id
            ).first()
            
            if not category:
                raise NotFoundError("Categoria não encontrada")
            
            if category.user_id != user.id:
                raise PermissionError("Categoria não pertence ao usuário")
            
            # Não permitir edição de categorias do sistema
            if category.is_system:
                raise ValidationError("Não é possível editar categorias do sistema")
            
            # Validar campos permitidos
            allowed_fields = {'name', 'description', 'icon', 'is_active'}
            invalid_fields = set(kwargs.keys()) - allowed_fields
            
            if invalid_fields:
                raise ValidationError(f"Campos inválidos: {invalid_fields}")
            
            # Validar dados se fornecidos
            if 'name' in kwargs:
                CategoryService._validate_category_data(
                    kwargs['name'],
                    kwargs.get('description', category.description),
                    kwargs.get('icon', category.icon)
                )
            
            # Aplicar atualizações
            for key, value in kwargs.items():
                if hasattr(category, key):
                    setattr(category, key, value)
            
            session.commit()
            
            logger.info(f"Categoria {category_id} atualizada pelo usuário {user.id}")
            
            return category
            
        except (NotFoundError, PermissionError, ValidationError):
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao atualizar categoria {category_id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def delete_category(
        session: Session,
        user: User,
        category_id: int
    ) -> bool:
        """
        Exclui uma categoria (soft delete)
        
        Args:
            session: Sessão do banco de dados
            user: Usuário proprietário
            category_id: ID da categoria
            
        Returns:
            bool: True se excluída com sucesso
            
        Raises:
            NotFoundError: Se categoria não encontrada
            PermissionError: Se categoria não pertence ao usuário
            ValidationError: Se categoria possui transações ou é do sistema
            ServiceError: Em caso de erro no banco
        """
        try:
            category = session.query(Category).filter(
                Category.id == category_id
            ).first()
            
            if not category:
                raise NotFoundError("Categoria não encontrada")
            
            if category.user_id != user.id:
                raise PermissionError("Categoria não pertence ao usuário")
            
            # Não permitir exclusão de categorias do sistema
            if category.is_system:
                raise ValidationError("Não é possível excluir categorias do sistema")
            
            # Verificar se possui transações
            transaction_count = session.query(Transaction).filter(
                Transaction.category_id == category_id
            ).count()
            
            if transaction_count > 0:
                # Fazer soft delete (apenas desativar)
                category.is_active = False
                session.commit()
                
                logger.info(
                    f"Categoria {category_id} desativada (possui {transaction_count} transações)"
                )
            else:
                # Exclusão física se não possui transações
                session.delete(category)
                session.commit()
                
                logger.info(f"Categoria {category_id} excluída fisicamente")
            
            return True
            
        except (NotFoundError, PermissionError, ValidationError):
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao excluir categoria {category_id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")


class AlertService:
    """Serviço para gerenciamento de alertas e notificações"""
    
    @staticmethod
    def create_alert(
        session: Session,
        user: User,
        alert_type: AlertType,
        title: str,
        message: str,
        scheduled_for: datetime,
        metadata: Optional[Dict] = None,
        priority: int = 0
    ) -> Alert:
        """
        Cria um novo alerta
        
        Args:
            session: Sessão do banco de dados
            user: Usuário destinatário
            alert_type: Tipo do alerta
            title: Título do alerta
            message: Mensagem do alerta
            scheduled_for: Data/hora para envio
            metadata: Dados adicionais (opcional)
            priority: Prioridade (0-10, padrão 0)
            
        Returns:
            Alert: Alerta criado
            
        Raises:
            ValidationError: Se dados inválidos
            ServiceError: Em caso de erro no banco
        """
        try:
            # Validações
            AlertService._validate_alert_data(title, message, scheduled_for, priority)
            
            alert = Alert(
                user_id=user.id,
                type=alert_type,
                title=title.strip(),
                message=message.strip(),
                scheduled_for=scheduled_for,
                data=json.dumps(metadata) if metadata else None,
                priority=priority
            )
            
            session.add(alert)
            session.commit()
            
            logger.info(
                f"Alerta criado: {alert_type.value} "
                f"para usuário {user.id} em {scheduled_for}"
            )
            
            return alert
            
        except ValidationError:
            raise
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao criar alerta para usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def _validate_alert_data(
        title: str,
        message: str,
        scheduled_for: datetime,
        priority: int
    ) -> None:
        """Valida dados do alerta"""
        
        if not title or not title.strip():
            raise ValidationError("Título do alerta não pode estar vazio")
        
        if len(title.strip()) > 100:
            raise ValidationError("Título muito longo (máximo 100 caracteres)")
        
        if not message or not message.strip():
            raise ValidationError("Mensagem do alerta não pode estar vazia")
        
        if len(message.strip()) > 1000:
            raise ValidationError("Mensagem muito longa (máximo 1000 caracteres)")
        
        if scheduled_for < datetime.now() - timedelta(hours=1):
            raise ValidationError("Data de agendamento não pode ser muito no passado")
        
        if not (0 <= priority <= 10):
            raise ValidationError("Prioridade deve estar entre 0 e 10")
    
    @staticmethod
    def get_pending_alerts(
        session: Session,
        limit: int = 100
    ) -> List[Alert]:
        """
        Obtém alertas pendentes para envio
        
        Args:
            session: Sessão do banco de dados
            limit: Limite de resultados
            
        Returns:
            List[Alert]: Lista de alertas pendentes
            
        Raises:
            ServiceError: Em caso de erro no banco
        """
        try:
            return session.query(Alert).filter(
                Alert.is_sent == False,
                Alert.scheduled_for <= datetime.now()
            ).order_by(
                Alert.priority.desc(),
                Alert.scheduled_for.asc()
            ).limit(limit).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar alertas pendentes: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def mark_as_sent(
        session: Session,
        alert: Alert
    ) -> None:
        """
        Marca alerta como enviado
        
        Args:
            session: Sessão do banco de dados
            alert: Alerta a ser marcado
            
        Raises:
            ServiceError: Em caso de erro no banco
        """
        try:
            alert.is_sent = True
            alert.sent_at = datetime.now()
            session.commit()
            
            logger.info(f"Alerta {alert.id} marcado como enviado")
            
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Erro ao marcar alerta {alert.id} como enviado: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")
    
    @staticmethod
    def get_user_alerts(
        session: Session,
        user: User,
        limit: int = 20,
        sent_only: bool = False
    ) -> List[Alert]:
        """
        Obtém alertas de um usuário
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            limit: Limite de resultados
            sent_only: Se deve retornar apenas alertas enviados
            
        Returns:
            List[Alert]: Lista de alertas
            
        Raises:
            ServiceError: Em caso de erro no banco
        """
        try:
            query = session.query(Alert).filter(
                Alert.user_id == user.id
            )
            
            if sent_only:
                query = query.filter(Alert.is_sent == True)
            
            return query.order_by(
                Alert.scheduled_for.desc()
            ).limit(limit).all()
            
        except SQLAlchemyError as e:
            logger.error(f"Erro ao buscar alertas do usuário {user.id}: {e}")
            raise ServiceError(f"Erro no banco de dados: {str(e)}")


# Utilitários para análise financeira
class AnalysisService:
    """Serviço para análises financeiras avançadas"""
    
    @staticmethod
    def get_spending_trends(
        session: Session,
        user: User,
        months: int = 6
    ) -> Dict[str, Any]:
        """
        Analisa tendências de gastos
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            months: Número de meses para análise
            
        Returns:
            Dict: Análise de tendências
        """
        try:
            trends = {}
            now = datetime.now()
            
            for i in range(months):
                date = now - timedelta(days=30 * i)
                summary = TransactionService.get_monthly_summary(
                    session, user, date.year, date.month
                )
                
                month_key = f"{date.year}-{date.month:02d}"
                trends[month_key] = {
                    'total_expenses': summary['total_expenses'],
                    'total_income': summary['total_income'],
                    'savings_rate': summary['savings_rate'],
                    'top_categories': dict(
                        sorted(
                            summary['expenses_by_category'].items(),
                            key=lambda x: x[1],
                            reverse=True
                        )[:5]
                    )
                }
            
            # Calcular tendências
            expense_values = [trends[k]['total_expenses'] for k in sorted(trends.keys())]
            income_values = [trends[k]['total_income'] for k in sorted(trends.keys())]
            
            expense_trend = AnalysisService._calculate_trend(expense_values)
            income_trend = AnalysisService._calculate_trend(income_values)
            
            return {
                'monthly_data': trends,
                'expense_trend': expense_trend,
                'income_trend': income_trend,
                'analysis_period_months': months
            }
            
        except Exception as e:
            logger.error(f"Erro ao analisar tendências para usuário {user.id}: {e}")
            return {}
    
    @staticmethod
    def _calculate_trend(values: List[float]) -> str:
        """Calcula tendência de uma série de valores"""
        if len(values) < 2:
            return "stable"
        
        # Calcular média das duas metades
        mid = len(values) // 2
        first_half_avg = sum(values[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(values[mid:]) / len(values[mid:]) if len(values[mid:]) > 0 else 0
        
        if first_half_avg == 0:
            return "stable"
        
        change_percent = ((second_half_avg - first_half_avg) / first_half_avg) * 100
        
        if change_percent > 10:
            return "increasing"
        elif change_percent < -10:
            return "decreasing"
        else:
            return "stable"
    
    @staticmethod
    def generate_recommendations(
        session: Session,
        user: User
    ) -> List[str]:
        """
        Gera recomendações personalizadas
        
        Args:
            session: Sessão do banco de dados
            user: Usuário
            
        Returns:
            List[str]: Lista de recomendações
        """
        try:
            recommendations = []
            
            # Analisar saúde financeira
            health_score, _ = TransactionService.get_financial_health_score(session, user)
            
            # Obter resumo do mês atual
            now = datetime.now()
            summary = TransactionService.get_monthly_summary(session, user, now.year, now.month)
            
            # Analisar carteira de investimentos
            portfolio = InvestmentService.get_portfolio_summary(session, user)
            
            # Gerar recomendações baseadas nos dados
            if health_score < 40:
                recommendations.extend([
                    "🚨 Revise urgentemente seus gastos mensais",
                    "💡 Identifique despesas supérfluas que podem ser cortadas",
                    "📊 Crie um orçamento detalhado e siga rigorosamente"
                ])
            
            if summary['savings_rate'] < 10:
                recommendations.append("💰 Tente aumentar sua taxa de poupança para pelo menos 10%")
            
            if portfolio['asset_count'] == 0:
                recommendations.append("📈 Considere começar a investir suas economias")
            elif portfolio['diversification_score'] < 50:
                recommendations.append("🎯 Diversifique mais sua carteira de investimentos")
            
            # Analisar gastos por categoria
            if summary['expenses_by_category']:
                top_expense_category = max(
                    summary['expenses_by_category'].items(),
                    key=lambda x: x[1]
                )
                
                if (top_expense_category[1] / summary['total_expenses']) > 0.4:
                    recommendations.append(
                        f"⚠️ Seus gastos com '{top_expense_category[0]}' estão muito altos "
                        f"({(top_expense_category[1] / summary['total_expenses'] * 100):.1f}% do total)"
                    )
            
            return recommendations[:5]  # Máximo 5 recomendações
            
        except Exception as e:
            logger.error(f"Erro ao gerar recomendações para usuário {user.id}: {e}")
            return ["💡 Continue registrando suas transações para receber recomendações personalizadas!"]