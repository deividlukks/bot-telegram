"""
Serviço de Relatórios Simplificado para o Finance Bot
Versão sem imports circulares
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


@dataclass
class ReportPeriod:
    """Período de relatório"""
    start_date: datetime
    end_date: datetime
    label: str


class ReportService:
    """Serviço simplificado de relatórios"""
    
    @staticmethod
    def generate_monthly_report(session: Session, user) -> Dict[str, Any]:
        """Gera relatório mensal simplificado"""
        from models import Transaction, TransactionType
        
        now = datetime.now()
        start_date = datetime(now.year, now.month, 1)
        
        if now.month == 12:
            end_date = datetime(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
        
        # Buscar transações do mês
        transactions = session.query(Transaction).filter(
            Transaction.user_id == user.id,
            Transaction.date >= start_date,
            Transaction.date <= end_date
        ).all()
        
        # Calcular totais
        total_income = Decimal('0')
        total_expenses = Decimal('0')
        categories_breakdown = {}
        
        for t in transactions:
            if t.type == TransactionType.INCOME:
                total_income += t.amount
            else:
                total_expenses += t.amount
            
            # Breakdown por categoria
            cat_name = t.category.name
            if cat_name not in categories_breakdown:
                categories_breakdown[cat_name] = Decimal('0')
            categories_breakdown[cat_name] += t.amount
        
        balance = total_income - total_expenses
        savings_rate = (balance / total_income * 100) if total_income > 0 else Decimal('0')
        
        return {
            'period': f"{now.month:02d}/{now.year}",
            'total_income': total_income,
            'total_expenses': total_expenses,
            'balance': balance,
            'savings_rate': savings_rate,
            'transaction_count': len(transactions),
            'categories_breakdown': categories_breakdown
        }


class ReportFormatter:
    """Formatador de relatórios"""
    
    @staticmethod
    def format_monthly_report(report_data: Dict[str, Any]) -> str:
        """Formata relatório para exibição no Telegram"""
        from utils import format_currency, format_percentage
        
        message = f"*📊 Relatório Mensal - {report_data['period']}*\n\n"
        
        message += f"*💰 Resumo Financeiro:*\n"
        message += f"• Receitas: {format_currency(report_data['total_income'])}\n"
        message += f"• Despesas: {format_currency(report_data['total_expenses'])}\n"
        message += f"• Saldo: {format_currency(report_data['balance'])}\n"
        message += f"• Taxa Poupança: {format_percentage(report_data['savings_rate'])}\n"
        message += f"• Transações: {report_data['transaction_count']}\n\n"
        
        # Top categorias
        if report_data['categories_breakdown']:
            sorted_categories = sorted(
                report_data['categories_breakdown'].items(),
                key=lambda x: x[1], reverse=True
            )
            
            message += f"*🏷️ Principais Categorias:*\n"
            for category, amount in sorted_categories[:5]:
                message += f"• {category}: {format_currency(amount)}\n"
        
        return message


class PeriodUtils:
    """Utilitários para períodos"""
    
    @staticmethod
    def get_current_month() -> ReportPeriod:
        """Obtém período do mês atual"""
        now = datetime.now()
        start_date = datetime(now.year, now.month, 1)
        
        if now.month == 12:
            end_date = datetime(now.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(now.year, now.month + 1, 1) - timedelta(days=1)
        
        return ReportPeriod(
            start_date=start_date,
            end_date=end_date,
            label=f"{now.month:02d}/{now.year}"
        )


# Funções de conveniência
def generate_monthly_report(session: Session, user, year: int = None, month: int = None) -> Dict[str, Any]:
    """Função de conveniência para relatório mensal"""
    return ReportService.generate_monthly_report(session, user)


def get_formatted_monthly_report(session: Session, user, year: int = None, month: int = None) -> str:
    """Obtém relatório mensal formatado para Telegram"""
    try:
        report_data = generate_monthly_report(session, user, year, month)
        return ReportFormatter.format_monthly_report(report_data)
    except Exception as e:
        logger.error(f"Erro ao formatar relatório: {e}")
        return "❌ Erro ao gerar relatório. Tente novamente."


def get_quick_insights(session: Session, user) -> List[str]:
    """Obtém insights rápidos para exibição no bot"""
    try:
        report_data = generate_monthly_report(session, user)
        
        insights = []
        
        # Insight sobre saldo
        if report_data['balance'] > 0:
            insights.append(f"✅ Saldo positivo: {format_currency(report_data['balance'])}")
        else:
            insights.append(f"⚠️ Saldo negativo: {format_currency(report_data['balance'])}")
        
        # Insight sobre poupança
        savings_rate = report_data['savings_rate']
        if savings_rate >= 20:
            insights.append(f"🎯 Excelente taxa de poupança: {format_percentage(savings_rate)}")
        elif savings_rate >= 10:
            insights.append(f"👍 Boa taxa de poupança: {format_percentage(savings_rate)}")
        else:
            insights.append(f"📈 Oportunidade: Aumente sua poupança (atual: {format_percentage(savings_rate)})")
        
        # Insight sobre atividade
        if report_data['transaction_count'] > 20:
            insights.append("📊 Usuário muito ativo no controle financeiro!")
        elif report_data['transaction_count'] > 10:
            insights.append("📈 Bom acompanhamento das finanças!")
        else:
            insights.append("💡 Registre mais transações para melhores insights!")
        
        return insights[:3]  # Máximo 3 insights
        
    except Exception as e:
        logger.error(f"Erro ao gerar insights: {e}")
        return ["❌ Erro ao carregar insights"]


def clear_user_cache(user_id: int) -> None:
    """Limpa cache de relatórios do usuário"""
    # Por enquanto, função placeholder
    # Implementar cache real se necessário
    pass


# Imports locais no final para evitar circular imports
try:
    from utils import format_currency, format_percentage
except ImportError:
    # Fallback se utils não estiver disponível
    def format_currency(amount):
        return f"R$ {float(amount):,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
    
    def format_percentage(value, decimals=1):
        return f"{float(value):.{decimals}f}%"