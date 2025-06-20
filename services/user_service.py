"""
Serviço de gerenciamento de usuários do Finance Bot
Funcionalidades específicas para gestão de usuários e perfis
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Tuple, Dict, List, Any

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from models import User, Transaction, Investment, Category, InvestorProfile, TransactionType
from config import Config
from utils import format_currency, format_percentage

logger = logging.getLogger(__name__)


class UserService:
    """Serviço avançado para gerenciamento de usuários"""
    
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
            first_name: Primeiro nome
            last_name: Último nome (opcional)
            
        Returns:
            Tuple[User, bool]: (usuário, foi_criado)
        """
        try:
            # Buscar usuário existente
            user = session.query(User).filter(
                User.telegram_id == telegram_id
            ).first()
            
            if user:
                # Atualizar informações se mudaram
                updated = False
                
                if username and user.username != username:
                    logger.info(f"Atualizando username do usuário {telegram_id}: {user.username} -> {username}")
                    user.username = username
                    updated = True
                    
                if first_name and user.first_name != first_name:
                    logger.info(f"Atualizando nome do usuário {telegram_id}: {user.first_name} -> {first_name}")
                    user.first_name = first_name
                    updated = True
                    
                if last_name and user.last_name != last_name:
                    user.last_name = last_name
                    updated = True
                
                if updated:
                    user.updated_at = datetime.now()
                    session.commit()
                    logger.info(f"Informações do usuário {telegram_id} atualizadas")
                
                return user, False
            
            # Criar novo usuário
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                investor_profile=InvestorProfile.MODERATE,  # Perfil padrão
                timezone=Config.DEFAULT_TIMEZONE,
                notifications_enabled=True
            )
            
            session.add(user)
            session.flush()  # Para obter o ID antes do commit
            
            logger.info(f"Novo usuário criado: {telegram_id} (@{username})")
            
            # Criar categorias padrão para o novo usuário
            UserService._create_default_categories(session, user)
            
            session.commit()
            
            logger.info(f"Usuário {telegram_id} criado com sucesso com categorias padrão")
            
            return user, True
            
        except Exception as e:
            logger.error(f"Erro ao criar/obter usuário {telegram_id}: {e}")
            session.rollback()
            raise
    
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
                        is_system=True,
                        is_active=True
                    )
                    session.add(category)
            
            logger.info(f"Categorias padrão criadas para usuário {user.id}")
            
        except Exception as e:
            logger.error(f"Erro ao criar categorias padrão para usuário {user.id}: {e}")
            raise
    
    @staticmethod
    def update_profile(
        session: Session,
        user: User,
        **kwargs
    ) -> User:
        """
        Atualiza perfil do usuário
        
        Args:
            session: Sessão do banco
            user: Usuário a ser atualizado
            **kwargs: Campos a serem atualizados
            
        Returns:
            User: Usuário atualizado
        """
        try:
            updated_fields = []
            
            # Campos permitidos para atualização
            allowed_fields = {
                'investor_profile', 'monthly_income', 'savings_goal',
                'timezone', 'notifications_enabled', 'first_name', 
                'last_name', 'username'
            }
            
            for key, value in kwargs.items():
                if key in allowed_fields and hasattr(user, key) and value is not None:
                    old_value = getattr(user, key)
                    if old_value != value:
                        setattr(user, key, value)
                        updated_fields.append(f"{key}: {old_value} -> {value}")
            
            if updated_fields:
                user.updated_at = datetime.now()
                session.commit()
                logger.info(f"Perfil do usuário {user.id} atualizado: {', '.join(updated_fields)}")
            
            return user
            
        except Exception as e:
            logger.error(f"Erro ao atualizar perfil do usuário {user.id}: {e}")
            session.rollback()
            raise
    
    @staticmethod
    def get_user_statistics(session: Session, user: User) -> Dict[str, Any]:
        """
        Obtém estatísticas completas do usuário
        
        Args:
            session: Sessão do banco
            user: Usuário
            
        Returns:
            Dict: Estatísticas do usuário
        """
        try:
            # Calcular dias desde cadastro
            days_since_join = (datetime.now() - user.created_at).days
            
            # Estatísticas de transações
            total_transactions = session.query(Transaction).filter(
                Transaction.user_id == user.id
            ).count()
            
            total_income_transactions = session.query(Transaction).filter(
                Transaction.user_id == user.id,
                Transaction.type == TransactionType.INCOME
            ).count()
            
            total_expense_transactions = session.query(Transaction).filter(
                Transaction.user_id == user.id,
                Transaction.type == TransactionType.EXPENSE
            ).count()
            
            # Valores totais
            total_income_value = session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user.id,
                Transaction.type == TransactionType.INCOME
            ).scalar() or Decimal('0')
            
            total_expense_value = session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user.id,
                Transaction.type == TransactionType.EXPENSE
            ).scalar() or Decimal('0')
            
            # Estatísticas de investimentos
            total_investments = session.query(Investment).filter(
                Investment.user_id == user.id,
                Investment.is_active == True
            ).count()
            
            total_invested_value = session.query(func.sum(Investment.quantity * Investment.avg_price)).filter(
                Investment.user_id == user.id,
                Investment.is_active == True
            ).scalar() or Decimal('0')
            
            # Categorias personalizadas
            custom_categories = session.query(Category).filter(
                Category.user_id == user.id,
                Category.is_system == False
            ).count()
            
            # Primeira e última transação
            first_transaction = session.query(Transaction).filter(
                Transaction.user_id == user.id
            ).order_by(Transaction.date.asc()).first()
            
            last_transaction = session.query(Transaction).filter(
                Transaction.user_id == user.id
            ).order_by(Transaction.date.desc()).first()
            
            # Estatísticas de uso
            days_with_transactions = session.query(
                func.count(func.distinct(func.date(Transaction.date)))
            ).filter(
                Transaction.user_id == user.id
            ).scalar() or 0
            
            # Frequência de uso
            usage_frequency = (days_with_transactions / max(days_since_join, 1)) * 100
            
            return {
                'user_info': {
                    'id': user.id,
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'full_name': f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    'days_since_join': days_since_join,
                    'investor_profile': user.investor_profile.value if user.investor_profile else None,
                    'timezone': user.timezone,
                    'notifications_enabled': user.notifications_enabled
                },
                'financial_data': {
                    'total_income': float(total_income_value),
                    'total_expenses': float(total_expense_value),
                    'net_worth': float(total_income_value - total_expense_value),
                    'total_invested': float(total_invested_value)
                },
                'transaction_stats': {
                    'total_transactions': total_transactions,
                    'income_transactions': total_income_transactions,
                    'expense_transactions': total_expense_transactions,
                    'average_per_day': round(total_transactions / max(days_since_join, 1), 2),
                    'first_transaction_date': first_transaction.date.isoformat() if first_transaction else None,
                    'last_transaction_date': last_transaction.date.isoformat() if last_transaction else None
                },
                'investment_stats': {
                    'total_investments': total_investments,
                    'total_invested_value': float(total_invested_value),
                    'has_investments': total_investments > 0
                },
                'usage_stats': {
                    'days_with_transactions': days_with_transactions,
                    'usage_frequency_percent': round(usage_frequency, 1),
                    'custom_categories': custom_categories,
                    'is_active_user': usage_frequency > 10  # Mais de 10% dos dias com transações
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas do usuário {user.id}: {e}")
            return {
                'error': 'Erro ao calcular estatísticas',
                'user_info': {
                    'id': user.id,
                    'telegram_id': user.telegram_id
                }
            }
    
    @staticmethod
    def get_user_financial_summary(session: Session, user: User) -> str:
        """
        Gera resumo financeiro formatado para exibição
        
        Args:
            session: Sessão do banco
            user: Usuário
            
        Returns:
            str: Resumo formatado para Telegram
        """
        try:
            stats = UserService.get_user_statistics(session, user)
            
            if 'error' in stats:
                return "❌ Erro ao carregar informações financeiras."
            
            user_info = stats['user_info']
            financial = stats['financial_data']
            transactions = stats['transaction_stats']
            investments = stats['investment_stats']
            usage = stats['usage_stats']
            
            # Determinar status do usuário
            if usage['is_active_user']:
                status_emoji = "🟢"
                status_text = "Usuário Ativo"
            elif transactions['total_transactions'] > 0:
                status_emoji = "🟡"
                status_text = "Usuário Ocasional"
            else:
                status_emoji = "🔴"
                status_text = "Novo Usuário"
            
            # Perfil de investidor
            profile_emojis = {
                'conservative': '🛡️ Conservador',
                'moderate': '⚖️ Moderado', 
                'aggressive': '🚀 Agressivo'
            }
            profile_text = profile_emojis.get(user_info['investor_profile'], '❓ Não definido')
            
            summary = f"""
*👤 Perfil Financeiro*

*📊 Status:* {status_emoji} {status_text}
*🎯 Perfil:* {profile_text}
*📅 Membro há:* {user_info['days_since_join']} dias
*🌍 Timezone:* {user_info['timezone']}

*💰 Resumo Financeiro:*
• Total Receitas: {format_currency(financial['total_income'])}
• Total Despesas: {format_currency(financial['total_expenses'])}
• Patrimônio Líquido: {format_currency(financial['net_worth'])}
• Total Investido: {format_currency(financial['total_invested'])}

*📈 Atividade:*
• Transações: {transactions['total_transactions']} ({transactions['average_per_day']}/dia)
• Investimentos: {investments['total_investments']} ativos
• Frequência de Uso: {usage['usage_frequency_percent']}%
• Categorias Criadas: {usage['custom_categories']}

*⚙️ Configurações:*
• Notificações: {'✅ Ativas' if user_info['notifications_enabled'] else '❌ Desativas'}
• Renda Mensal: {format_currency(user.monthly_income) if user.monthly_income else 'Não definida'}
• Meta Poupança: {format_currency(user.savings_goal) if user.savings_goal else 'Não definida'}
"""
            
            # Adicionar insights baseados no perfil
            if transactions['total_transactions'] == 0:
                summary += "\n💡 *Dica:* Comece registrando sua primeira transação!"
            elif investments['total_investments'] == 0 and financial['net_worth'] > 1000:
                summary += "\n💡 *Dica:* Considere começar a investir para fazer seu dinheiro crescer!"
            elif usage['usage_frequency_percent'] < 20:
                summary += "\n💡 *Dica:* Use o bot mais frequentemente para melhores insights!"
            
            return summary
            
        except Exception as e:
            logger.error(f"Erro ao gerar resumo financeiro para usuário {user.id}: {e}")
            return "❌ Erro ao gerar resumo financeiro."
    
    @staticmethod
    def set_investor_profile(
        session: Session,
        user: User,
        profile: InvestorProfile
    ) -> bool:
        """
        Define o perfil de investidor do usuário
        
        Args:
            session: Sessão do banco
            user: Usuário
            profile: Novo perfil de investidor
            
        Returns:
            bool: True se atualizado com sucesso
        """
        try:
            old_profile = user.investor_profile
            user.investor_profile = profile
            user.updated_at = datetime.now()
            
            session.commit()
            
            logger.info(f"Perfil de investidor do usuário {user.id} alterado: {old_profile} -> {profile}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao definir perfil de investidor para usuário {user.id}: {e}")
            session.rollback()
            return False
    
    @staticmethod
    def set_financial_goals(
        session: Session,
        user: User,
        monthly_income: Optional[Decimal] = None,
        savings_goal: Optional[Decimal] = None
    ) -> bool:
        """
        Define metas financeiras do usuário
        
        Args:
            session: Sessão do banco
            user: Usuário
            monthly_income: Renda mensal (opcional)
            savings_goal: Meta de poupança mensal (opcional)
            
        Returns:
            bool: True se atualizado com sucesso
        """
        try:
            updated = False
            
            if monthly_income is not None:
                user.monthly_income = monthly_income
                updated = True
                logger.info(f"Renda mensal do usuário {user.id} definida: {format_currency(monthly_income)}")
            
            if savings_goal is not None:
                user.savings_goal = savings_goal
                updated = True
                logger.info(f"Meta de poupança do usuário {user.id} definida: {format_currency(savings_goal)}")
            
            if updated:
                user.updated_at = datetime.now()
                session.commit()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao definir metas financeiras para usuário {user.id}: {e}")
            session.rollback()
            return False
    
    @staticmethod
    def get_users_by_activity(
        session: Session,
        days: int = 30,
        min_transactions: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Obtém usuários ativos baseado em critérios
        
        Args:
            session: Sessão do banco
            days: Período em dias para considerar atividade
            min_transactions: Mínimo de transações no período
            
        Returns:
            List[Dict]: Lista de usuários ativos com estatísticas
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Query para usuários com transações no período
            active_users = session.query(
                User.id,
                User.telegram_id,
                User.username,
                User.first_name,
                func.count(Transaction.id).label('transaction_count'),
                func.max(Transaction.date).label('last_transaction')
            ).join(
                Transaction, Transaction.user_id == User.id
            ).filter(
                Transaction.date >= cutoff_date
            ).group_by(
                User.id, User.telegram_id, User.username, User.first_name
            ).having(
                func.count(Transaction.id) >= min_transactions
            ).order_by(
                func.count(Transaction.id).desc()
            ).all()
            
            result = []
            for user_data in active_users:
                result.append({
                    'user_id': user_data.id,
                    'telegram_id': user_data.telegram_id,
                    'username': user_data.username,
                    'first_name': user_data.first_name,
                    'transaction_count': user_data.transaction_count,
                    'last_transaction': user_data.last_transaction.isoformat()
                })
            
            logger.info(f"Encontrados {len(result)} usuários ativos nos últimos {days} dias")
            return result
            
        except Exception as e:
            logger.error(f"Erro ao buscar usuários ativos: {e}")
            return []
    
    @staticmethod
    def delete_user_data(
        session: Session,
        user: User,
        confirm_telegram_id: int
    ) -> bool:
        """
        Remove todos os dados do usuário (GDPR compliance)
        
        Args:
            session: Sessão do banco
            user: Usuário a ser removido
            confirm_telegram_id: ID do telegram para confirmação
            
        Returns:
            bool: True se removido com sucesso
        """
        try:
            # Verificação de segurança
            if user.telegram_id != confirm_telegram_id:
                logger.warning(f"Tentativa de exclusão com ID incorreto: {confirm_telegram_id} != {user.telegram_id}")
                return False
            
            user_id = user.id
            telegram_id = user.telegram_id
            
            # Remover em ordem para respeitar foreign keys
            # As transações e investimentos serão removidos automaticamente devido ao cascade
            session.delete(user)
            session.commit()
            
            logger.info(f"Usuário {telegram_id} (ID: {user_id}) e todos seus dados foram removidos")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover dados do usuário {user.telegram_id}: {e}")
            session.rollback()
            return False
    
    @staticmethod
    def export_user_data(session: Session, user: User) -> Dict[str, Any]:
        """
        Exporta todos os dados do usuário (GDPR compliance)
        
        Args:
            session: Sessão do banco
            user: Usuário
            
        Returns:
            Dict: Todos os dados do usuário
        """
        try:
            # Buscar todas as transações
            transactions = session.query(Transaction).filter(
                Transaction.user_id == user.id
            ).all()
            
            # Buscar todos os investimentos
            investments = session.query(Investment).filter(
                Investment.user_id == user.id
            ).all()
            
            # Buscar categorias personalizadas
            custom_categories = session.query(Category).filter(
                Category.user_id == user.id,
                Category.is_system == False
            ).all()
            
            # Montar dados completos
            export_data = {
                'user_profile': {
                    'telegram_id': user.telegram_id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'investor_profile': user.investor_profile.value if user.investor_profile else None,
                    'monthly_income': float(user.monthly_income) if user.monthly_income else None,
                    'savings_goal': float(user.savings_goal) if user.savings_goal else None,
                    'timezone': user.timezone,
                    'notifications_enabled': user.notifications_enabled,
                    'created_at': user.created_at.isoformat(),
                    'updated_at': user.updated_at.isoformat()
                },
                'transactions': [
                    {
                        'id': t.id,
                        'amount': float(t.amount),
                        'type': t.type.value,
                        'description': t.description,
                        'payment_method': t.payment_method,
                        'date': t.date.isoformat(),
                        'category_name': t.category.name,
                        'notes': t.notes,
                        'tags': t.tags,
                        'is_recurring': t.is_recurring,
                        'created_at': t.created_at.isoformat()
                    } for t in transactions
                ],
                'investments': [
                    {
                        'id': i.id,
                        'ticker': i.ticker,
                        'name': i.name,
                        'type': i.type.value,
                        'quantity': float(i.quantity),
                        'avg_price': float(i.avg_price),
                        'purchase_date': i.purchase_date.isoformat(),
                        'broker': i.broker,
                        'is_active': i.is_active,
                        'sale_date': i.sale_date.isoformat() if i.sale_date else None,
                        'sale_price': float(i.sale_price) if i.sale_price else None,
                        'sale_quantity': float(i.sale_quantity) if i.sale_quantity else None,
                        'created_at': i.created_at.isoformat()
                    } for i in investments
                ],
                'custom_categories': [
                    {
                        'id': c.id,
                        'name': c.name,
                        'type': c.type.value,
                        'description': c.description,
                        'icon': c.icon,
                        'is_active': c.is_active,
                        'created_at': c.created_at.isoformat()
                    } for c in custom_categories
                ],
                'export_metadata': {
                    'generated_at': datetime.now().isoformat(),
                    'total_transactions': len(transactions),
                    'total_investments': len(investments),
                    'total_custom_categories': len(custom_categories)
                }
            }
            
            logger.info(f"Dados do usuário {user.telegram_id} exportados com sucesso")
            return export_data
            
        except Exception as e:
            logger.error(f"Erro ao exportar dados do usuário {user.id}: {e}")
            return {
                'error': 'Erro ao exportar dados',
                'user_id': user.telegram_id
            }