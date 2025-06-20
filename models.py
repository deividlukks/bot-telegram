"""
Modelos de dados para o Finance Bot
Usa Decimal para valores monetários e SQLAlchemy 2.0+ syntax
"""
from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Boolean, Text, DateTime, 
    ForeignKey, Enum, Numeric, Index, UniqueConstraint
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, 
    relationship, validates
)
from sqlalchemy.sql import func


class TransactionType(PyEnum):
    """Tipos de transação"""
    INCOME = "income"
    EXPENSE = "expense"


class InvestmentType(PyEnum):
    """Tipos de investimento"""
    STOCK = "stock"          # Ações
    FII = "fii"              # Fundos Imobiliários
    CRYPTO = "crypto"        # Criptomoedas
    ETF = "etf"              # ETFs
    FIXED_INCOME = "fixed"   # Renda Fixa
    OTHER = "other"          # Outros


class InvestorProfile(PyEnum):
    """Perfis de investidor"""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class AlertType(PyEnum):
    """Tipos de alerta"""
    DIVIDEND = "dividend"
    MARKET = "market"
    OPPORTUNITY = "opportunity"
    REMINDER = "reminder"


class Base(DeclarativeBase):
    """Base class para todos os modelos"""
    pass


class TimestampMixin:
    """Mixin para adicionar timestamps automaticamente"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )


class User(Base, TimestampMixin):
    """Modelo de usuário"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        Integer, 
        unique=True, 
        index=True,
        nullable=False
    )
    username: Mapped[Optional[str]] = mapped_column(String(100))
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Perfil financeiro
    investor_profile: Mapped[InvestorProfile] = mapped_column(
        Enum(InvestorProfile),
        default=InvestorProfile.MODERATE
    )
    monthly_income: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    savings_goal: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2),
        nullable=True
    )
    
    # Configurações
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="America/Sao_Paulo"
    )
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True
    )
    
    # Relacionamentos
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    investments: Mapped[List["Investment"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    categories: Mapped[List["Category"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"


class Category(Base, TimestampMixin):
    """Modelo de categoria"""
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint('user_id', 'name', 'type', name='uq_user_category'),
        Index('idx_category_user_type', 'user_id', 'type'), # NOME ALTERADO
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType),
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(255))
    icon: Mapped[Optional[str]] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="categories")
    transactions: Mapped[List["Transaction"]] = relationship(
        back_populates="category",
        lazy="dynamic"
    )
    
    @validates('name')
    def validate_name(self, key, name):
        """Valida o nome da categoria"""
        if not name or not name.strip():
            raise ValueError("Nome da categoria não pode ser vazio")
        return name.strip()
    
    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name}, type={self.type.value})>"


class Transaction(Base, TimestampMixin):
    """Modelo de transação financeira"""
    __tablename__ = "transactions"
    __table_args__ = (
        Index('idx_user_date', 'user_id', 'date'),
        Index('idx_transaction_user_type', 'user_id', 'type'), # NOME ALTERADO
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False
    )
    
    # Dados financeiros - SEMPRE use Decimal para valores monetários
    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )
    
    # Informações da transação
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType),
        nullable=False
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Campos opcionais
    notes: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[Optional[str]] = mapped_column(String(255))  # JSON array
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="transactions")
    category: Mapped["Category"] = relationship(back_populates="transactions")
    
    @validates('amount')
    def validate_amount(self, key, amount):
        """Valida o valor da transação"""
        if amount <= 0:
            raise ValueError("Valor deve ser maior que zero")
        # Garantir que é Decimal
        return Decimal(str(amount))
    
    @validates('description')
    def validate_description(self, key, description):
        """Valida a descrição"""
        if not description or not description.strip():
            raise ValueError("Descrição não pode ser vazia")
        return description.strip()
    
    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, amount={self.amount}, type={self.type.value})>"


class Investment(Base, TimestampMixin):
    """Modelo de investimento"""
    __tablename__ = "investments"
    __table_args__ = (
        Index('idx_user_ticker', 'user_id', 'ticker'),
        Index('idx_user_active', 'user_id', 'is_active'),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Identificação do ativo
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(100))
    type: Mapped[InvestmentType] = mapped_column(
        Enum(InvestmentType),
        nullable=False
    )
    
    # Dados de compra - SEMPRE use Decimal para valores monetários
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 8),  # Mais casas decimais para criptomoedas
        nullable=False
    )
    avg_price: Mapped[Decimal] = mapped_column(
        Numeric(15, 4),
        nullable=False
    )
    purchase_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    broker: Mapped[Optional[str]] = mapped_column(String(50))
    
    # Dados de venda (se aplicável)
    sale_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sale_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4))
    sale_quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 8))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="investments")
    
    @property
    def total_invested(self) -> Decimal:
        """Calcula o valor total investido"""
        return self.quantity * self.avg_price
    
    @property
    def current_quantity(self) -> Decimal:
        """Retorna a quantidade atual (considerando vendas parciais)"""
        if self.sale_quantity:
            return self.quantity - self.sale_quantity
        return self.quantity
    
    @validates('quantity', 'avg_price')
    def validate_positive(self, key, value):
        """Valida valores positivos"""
        if value <= 0:
            raise ValueError(f"{key} deve ser maior que zero")
        return Decimal(str(value))
    
    def __repr__(self) -> str:
        return f"<Investment(id={self.id}, ticker={self.ticker}, quantity={self.quantity})>"


class Alert(Base, TimestampMixin):
    """Modelo de alerta/notificação"""
    __tablename__ = "alerts"
    __table_args__ = (
        Index('idx_user_scheduled', 'user_id', 'scheduled_for', 'is_sent'),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Dados do alerta
    type: Mapped[AlertType] = mapped_column(
        Enum(AlertType),
        nullable=False
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Agendamento
    scheduled_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Metadados
    data: Mapped[Optional[str]] = mapped_column(Text)  # JSON
    priority: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="alerts")
    
    def __repr__(self) -> str:
        return f"<Alert(id={self.id}, type={self.type.value}, scheduled_for={self.scheduled_for})>"


# Categorias padrão do sistema
DEFAULT_CATEGORIES = {
    TransactionType.INCOME: [
        ("Salário", "💼", "Salário mensal"),
        ("Freelance", "💻", "Trabalhos freelance"),
        ("Investimentos", "📈", "Rendimentos de investimentos"),
        ("Vendas", "🛒", "Vendas de produtos/serviços"),
        ("Outros", "💰", "Outras receitas"),
    ],
    TransactionType.EXPENSE: [
        ("Alimentação", "🍽️", "Gastos com alimentação"),
        ("Transporte", "🚗", "Gastos com transporte"),
        ("Moradia", "🏠", "Aluguel, condomínio, etc"),
        ("Saúde", "🏥", "Gastos médicos e farmácia"),
        ("Educação", "📚", "Cursos, livros, etc"),
        ("Lazer", "🎮", "Entretenimento e diversão"),
        ("Compras", "🛍️", "Compras diversas"),
        ("Contas", "📄", "Água, luz, internet, etc"),
        ("Outros", "💸", "Outras despesas"),
    ]
}