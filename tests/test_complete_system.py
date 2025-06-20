"""
Sistema de testes completo para o Finance Bot
Testa todas as funcionalidades principais do bot
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telegram import Update, User as TelegramUser, Message, Chat, CallbackQuery

from models import Base, User, Transaction, Investment, Category, TransactionType, InvestmentType
from services import UserService, TransactionService, InvestmentService, CategoryService
from utils import (
    AmountValidator, DateValidator, TickerValidator, TextValidator,
    format_currency, format_percentage, FinancialAnalyzer
)
from config import Config
from database import Database


class TestFixtures:
    """Fixtures para testes"""
    
    @pytest.fixture(scope="session")
    def test_engine(self):
        """Engine de banco para testes"""
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=engine)
        return engine
    
    @pytest.fixture
    def test_session(self, test_engine):
        """Sessão de banco para testes"""
        Session = sessionmaker(bind=test_engine)
        session = Session()
        
        yield session
        
        # Cleanup após teste
        session.rollback()
        session.close()
    
    @pytest.fixture
    def test_user(self, test_session):
        """Usuário de teste"""
        user = User(
            telegram_id=123456789,
            username="testuser",
            first_name="Test",
            last_name="User"
        )
        test_session.add(user)
        test_session.commit()
        return user
    
    @pytest.fixture
    def test_category_income(self, test_session, test_user):
        """Categoria de receita para testes"""
        category = Category(
            user_id=test_user.id,
            name="Salário",
            type=TransactionType.INCOME,
            icon="💼",
            is_system=True
        )
        test_session.add(category)
        test_session.commit()
        return category
    
    @pytest.fixture
    def test_category_expense(self, test_session, test_user):
        """Categoria de despesa para testes"""
        category = Category(
            user_id=test_user.id,
            name="Alimentação",
            type=TransactionType.EXPENSE,
            icon="🍽️",
            is_system=True
        )
        test_session.add(category)
        test_session.commit()
        return category
    
    @pytest.fixture
    def mock_update(self):
        """Mock do Update do Telegram"""
        update = Mock(spec=Update)
        update.effective_user = Mock(spec=TelegramUser)
        update.effective_user.id = 123456789
        update.effective_user.username = "testuser"
        update.effective_user.first_name = "Test"
        update.effective_user.last_name = "User"
        
        update.message = Mock(spec=Message)
        update.message.text = "test message"
        update.message.reply_text = AsyncMock()
        
        update.callback_query = None
        return update


# ==================== TESTES DE VALIDADORES ====================

class TestValidators(TestFixtures):
    """Testes para os validadores"""
    
    def test_amount_validator_valid_formats(self):
        """Testa formatos válidos de valor"""
        test_cases = [
            ("100", Decimal("100.00")),
            ("100.50", Decimal("100.50")),
            ("100,50", Decimal("100.50")),
            ("1.000,50", Decimal("1000.50")),
            ("1,000.50", Decimal("1000.50")),
            ("R$ 150,75", Decimal("150.75")),
            ("  250.25  ", Decimal("250.25")),
        ]
        
        for input_value, expected in test_cases:
            result = AmountValidator.parse_and_validate(input_value)
            assert result.is_valid, f"Failed for input: {input_value}"
            assert result.value == expected, f"Expected {expected}, got {result.value}"
    
    def test_amount_validator_invalid_formats(self):
        """Testa formatos inválidos de valor"""
        invalid_cases = [
            "",
            "abc",
            "100.50.25",
            "-50",
            "0",
            "999999999999",  # Acima do limite
        ]
        
        for invalid_input in invalid_cases:
            result = AmountValidator.parse_and_validate(invalid_input)
            assert not result.is_valid, f"Should be invalid: {invalid_input}"
            assert result.error_message is not None
    
    def test_date_validator_valid_formats(self):
        """Testa formatos válidos de data"""
        test_cases = [
            "hoje",
            "ontem",
            "31/12/2023",
            "31/12/23",
            "31/12",  # Ano atual
            "2023/12/31",
        ]
        
        for date_input in test_cases:
            result = DateValidator.parse_and_validate(date_input)
            assert result.is_valid, f"Failed for input: {date_input}"
            assert isinstance(result.value, datetime)
    
    def test_date_validator_invalid_formats(self):
        """Testa formatos inválidos de data"""
        invalid_cases = [
            "",
            "32/12/2023",  # Dia inválido
            "31/13/2023",  # Mês inválido
            "31/12/2030",  # Futuro
            "abc",
            "31/12/1990",  # Muito antigo
        ]
        
        for invalid_input in invalid_cases:
            result = DateValidator.parse_and_validate(invalid_input)
            assert not result.is_valid, f"Should be invalid: {invalid_input}"
    
    def test_ticker_validator(self):
        """Testa validação de tickers"""
        valid_cases = [
            ("PETR4", "stock"),
            ("MXRF11", "fii"),
            ("BTC", "crypto"),
            ("IVVB11", "etf"),
            ("LTN", "fixed"),
        ]
        
        for ticker, inv_type in valid_cases:
            result = TickerValidator.validate_ticker(ticker, inv_type)
            assert result.is_valid, f"Failed for {ticker} ({inv_type})"
            assert result.value == ticker
        
        # Casos inválidos
        invalid_cases = [
            ("", "stock"),
            ("PETR", "stock"),  # Muito curto para ação
            ("PETR444", "stock"),  # Muito longo
            ("abc123", "fii"),  # Formato errado para FII
        ]
        
        for ticker, inv_type in invalid_cases:
            result = TickerValidator.validate_ticker(ticker, inv_type)
            assert not result.is_valid, f"Should be invalid: {ticker} ({inv_type})"
    
    def test_text_validator(self):
        """Testa validação de textos"""
        # Descrições válidas
        valid_descriptions = [
            "Almoço no restaurante",
            "Compras no supermercado",
            "Pagamento de conta de luz",
        ]
        
        for desc in valid_descriptions:
            result = TextValidator.validate_description(desc)
            assert result.is_valid
            assert result.value == desc
        
        # Descrições inválidas
        invalid_descriptions = [
            "",
            "   ",
            "a" * 256,  # Muito longo
            "<script>alert('xss')</script>",  # Caracteres maliciosos
        ]
        
        for desc in invalid_descriptions:
            result = TextValidator.validate_description(desc)
            assert not result.is_valid


# ==================== TESTES DE SERVIÇOS ====================

class TestServices(TestFixtures):
    """Testes para os serviços de negócio"""
    
    def test_user_service_create_user(self, test_session):
        """Testa criação de usuário"""
        user, created = UserService.get_or_create_user(
            session=test_session,
            telegram_id=987654321,
            username="newuser",
            first_name="New",
            last_name="User"
        )
        
        assert created is True
        assert user.telegram_id == 987654321
        assert user.username == "newuser"
        assert user.first_name == "New"
        assert user.last_name == "User"
    
    def test_user_service_get_existing_user(self, test_session, test_user):
        """Testa obtenção de usuário existente"""
        user, created = UserService.get_or_create_user(
            session=test_session,
            telegram_id=test_user.telegram_id
        )
        
        assert created is False
        assert user.id == test_user.id
    
    def test_transaction_service_create_transaction(self, test_session, test_user, test_category_expense):
        """Testa criação de transação"""
        transaction = TransactionService.create_transaction(
            session=test_session,
            user=test_user,
            category=test_category_expense,
            amount=Decimal("50.00"),
            description="Almoço",
            payment_method="cash",
            date=datetime.now(),
            transaction_type=TransactionType.EXPENSE
        )
        
        assert transaction.user_id == test_user.id
        assert transaction.category_id == test_category_expense.id
        assert transaction.amount == Decimal("50.00")
        assert transaction.description == "Almoço"
        assert transaction.type == TransactionType.EXPENSE
    
    def test_transaction_service_validation_errors(self, test_session, test_user, test_category_income):
        """Testa validações de transação"""
        # Tentar criar transação de despesa com categoria de receita
        with pytest.raises(ValueError):
            TransactionService.create_transaction(
                session=test_session,
                user=test_user,
                category=test_category_income,  # Categoria de receita
                amount=Decimal("50.00"),
                description="Test",
                payment_method="cash",
                date=datetime.now(),
                transaction_type=TransactionType.EXPENSE  # Tipo despesa
            )
        
        # Valor muito alto
        with pytest.raises(ValueError):
            TransactionService.create_transaction(
                session=test_session,
                user=test_user,
                category=test_category_income,
                amount=Decimal("9999999.00"),
                description="Test",
                payment_method="cash",
                date=datetime.now(),
                transaction_type=TransactionType.INCOME
            )
    
    def test_transaction_service_monthly_summary(self, test_session, test_user, test_category_income, test_category_expense):
        """Testa resumo mensal"""
        # Criar algumas transações
        TransactionService.create_transaction(
            session=test_session,
            user=test_user,
            category=test_category_income,
            amount=Decimal("3000.00"),
            description="Salário",
            payment_method="bank_transfer",
            date=datetime.now(),
            transaction_type=TransactionType.INCOME
        )
        
        TransactionService.create_transaction(
            session=test_session,
            user=test_user,
            category=test_category_expense,
            amount=Decimal("500.00"),
            description="Alimentação",
            payment_method="cash",
            date=datetime.now(),
            transaction_type=TransactionType.EXPENSE
        )
        
        # Obter resumo
        now = datetime.now()
        summary = TransactionService.get_monthly_summary(
            session=test_session,
            user=test_user,
            year=now.year,
            month=now.month
        )
        
        assert summary['total_income'] == Decimal("3000.00")
        assert summary['total_expenses'] == Decimal("500.00")
        assert summary['balance'] == Decimal("2500.00")
        assert summary['savings_rate'] == Decimal("83.33")  # (2500/3000)*100
        assert summary['transaction_count'] == 2
    
    def test_investment_service_create_investment(self, test_session, test_user):
        """Testa criação de investimento"""
        investment = InvestmentService.create_investment(
            session=test_session,
            user=test_user,
            ticker="PETR4",
            investment_type=InvestmentType.STOCK,
            quantity=Decimal("100.0000"),
            price=Decimal("25.50"),
            purchase_date=datetime.now()
        )
        
        assert investment.user_id == test_user.id
        assert investment.ticker == "PETR4"
        assert investment.type == InvestmentType.STOCK
        assert investment.quantity == Decimal("100.0000")
        assert investment.avg_price == Decimal("25.50")
        assert investment.total_invested == Decimal("2550.00")
    
    def test_investment_service_add_to_existing(self, test_session, test_user):
        """Testa adição a investimento existente"""
        # Criar investimento inicial
        investment1 = InvestmentService.create_investment(
            session=test_session,
            user=test_user,
            ticker="VALE3",
            investment_type=InvestmentType.STOCK,
            quantity=Decimal("100.0000"),
            price=Decimal("20.00"),
            purchase_date=datetime.now()
        )
        
        # Adicionar mais do mesmo ativo
        investment2 = InvestmentService.create_investment(
            session=test_session,
            user=test_user,
            ticker="VALE3",
            investment_type=InvestmentType.STOCK,
            quantity=Decimal("50.0000"),
            price=Decimal("22.00"),
            purchase_date=datetime.now()
        )
        
        # Deve ser o mesmo investimento (atualizado)
        assert investment1.id == investment2.id
        assert investment2.quantity == Decimal("150.0000")  # 100 + 50
        
        # Preço médio: ((100*20) + (50*22)) / 150 = 3100/150 = 20.67
        expected_avg = Decimal("20.67")
        assert abs(investment2.avg_price - expected_avg) < Decimal("0.01")
    
    def test_investment_service_portfolio_summary(self, test_session, test_user):
        """Testa resumo da carteira"""
        # Criar alguns investimentos
        InvestmentService.create_investment(
            session=test_session,
            user=test_user,
            ticker="PETR4",
            investment_type=InvestmentType.STOCK,
            quantity=Decimal("100.0000"),
            price=Decimal("25.00"),
            purchase_date=datetime.now()
        )
        
        InvestmentService.create_investment(
            session=test_session,
            user=test_user,
            ticker="MXRF11",
            investment_type=InvestmentType.FII,
            quantity=Decimal("50.0000"),
            price=Decimal("10.00"),
            purchase_date=datetime.now()
        )
        
        # Obter resumo
        summary = InvestmentService.get_portfolio_summary(test_session, test_user)
        
        assert summary['total_invested'] == Decimal("3000.00")  # 2500 + 500
        assert len(summary['investments']) == 2
        assert len(summary['by_type']) == 2
        assert 'stock' in summary['by_type']
        assert 'fii' in summary['by_type']
    
    def test_category_service_create_category(self, test_session, test_user):
        """Testa criação de categoria"""
        category = CategoryService.create_category(
            session=test_session,
            user=test_user,
            name="Transporte",
            category_type=TransactionType.EXPENSE,
            description="Gastos com transporte",
            icon="🚗"
        )
        
        assert category.user_id == test_user.id
        assert category.name == "Transporte"
        assert category.type == TransactionType.EXPENSE
        assert category.description == "Gastos com transporte"
        assert category.icon == "🚗"
        assert category.is_system is False
    
    def test_category_service_duplicate_name(self, test_session, test_user):
        """Testa criação de categoria com nome duplicado"""
        # Criar primeira categoria
        CategoryService.create_category(
            session=test_session,
            user=test_user,
            name="Educação",
            category_type=TransactionType.EXPENSE
        )
        
        # Tentar criar outra com mesmo nome e tipo
        with pytest.raises(ValueError):
            CategoryService.create_category(
                session=test_session,
                user=test_user,
                name="Educação",
                category_type=TransactionType.EXPENSE
            )


# ==================== TESTES DE FORMATAÇÃO ====================

class TestFormatters:
    """Testes para funções de formatação"""
    
    def test_format_currency(self):
        """Testa formatação de moeda"""
        test_cases = [
            (Decimal("1234.56"), "R$ 1.234,56"),
            (Decimal("0.50"), "R$ 0,50"),
            (Decimal("1000000.00"), "R$ 1.000.000,00"),
            (0, "R$ 0,00"),
            (1234.56, "R$ 1.234,56"),
        ]
        
        for amount, expected in test_cases:
            result = format_currency(amount)
            assert result == expected, f"Expected {expected}, got {result}"
    
    def test_format_percentage(self):
        """Testa formatação de percentual"""
        test_cases = [
            (Decimal("15.6"), "15.6%"),
            (Decimal("0.5"), "0.5%"),
            (Decimal("100.0"), "100.0%"),
            (15.6, "15.6%"),
        ]
        
        for value, expected in test_cases:
            result = format_percentage(value)
            assert result == expected


# ==================== TESTES DE ANÁLISE FINANCEIRA ====================

class TestFinancialAnalyzer:
    """Testes para o analisador financeiro"""
    
    def test_calculate_health_score_excellent(self):
        """Testa cálculo de score excelente"""
        score, status, details = FinancialAnalyzer.calculate_health_score(
            income=Decimal("5000.00"),
            expenses=Decimal("3000.00"),
            savings_rate=Decimal("40.0"),
            consistency_score=90
        )
        
        assert score >= 80
        assert "Excelente" in status
        assert details['savings_level'] == "Excelente"
        assert details['expense_control'] == "Boa"  # 60% de gastos
    
    def test_calculate_health_score_poor(self):
        """Testa cálculo de score ruim"""
        score, status, details = FinancialAnalyzer.calculate_health_score(
            income=Decimal("2000.00"),
            expenses=Decimal("2500.00"),  # Gastando mais que ganha
            savings_rate=Decimal("-25.0"),  # Taxa negativa
            consistency_score=20
        )
        
        assert score < 40
        assert "Precisa Melhorar" in status
        assert details['savings_level'] == "Baixa"
        assert details['expense_control'] == "Ruim"
    
    def test_analyze_spending_patterns(self):
        """Testa análise de padrões de gasto"""
        # Simular transações
        transactions = [
            {
                'category': 'Alimentação',
                'amount': 500,
                'date': datetime(2023, 12, 15, 12, 30)  # Sexta, 12:30
            },
            {
                'category': 'Transporte',
                'amount': 200,
                'date': datetime(2023, 12, 18, 8, 15)   # Segunda, 8:15
            },
            {
                'category': 'Alimentação',
                'amount': 300,
                'date': datetime(2023, 12, 20, 19, 45)  # Quarta, 19:45
            }
        ]
        
        insights = FinancialAnalyzer.analyze_spending_patterns(transactions)
        
        assert 'top_categories' in insights
        assert insights['top_categories'][0][0] == 'Alimentação'  # Categoria com maior gasto
        assert insights['top_categories'][0][1] == 800  # Total de alimentação
        
        assert 'peak_spending_day' in insights
        assert 'peak_spending_hour' in insights
        assert 'average_transaction' in insights
        assert insights['average_transaction'] == 1000 / 3  # Média dos gastos
    
    def test_predict_monthly_expenses(self):
        """Testa predição de gastos mensais"""
        # Dados históricos crescentes
        historical_data = [
            Decimal("1000.00"),
            Decimal("1100.00"),
            Decimal("1200.00"),
            Decimal("1300.00")
        ]
        
        prediction = FinancialAnalyzer.predict_monthly_expenses(historical_data)
        
        # Deve prever um valor maior que o último mês
        assert prediction > Decimal("1300.00")
        assert prediction <= Decimal("1500.00")  # Não deve ser excessivo
        
        # Dados estáveis
        stable_data = [Decimal("1000.00")] * 5
        prediction_stable = FinancialAnalyzer.predict_monthly_expenses(stable_data)
        
        # Deve prever valor similar
        assert abs(prediction_stable - Decimal("1000.00")) < Decimal("50.00")


# ==================== TESTES DE INTEGRAÇÃO ====================

class TestIntegration(TestFixtures):
    """Testes de integração completos"""
    
    @pytest.mark.asyncio
    async def test_complete_transaction_flow(self, test_session, test_user, test_category_expense):
        """Testa fluxo completo de transação"""
        # Simular dados de entrada do usuário
        amount_input = "R$ 150,75"
        description_input = "Almoço no restaurante"
        date_input = "15/12/2023"
        
        # Validar e processar entrada
        amount_result = AmountValidator.parse_and_validate(amount_input)
        assert amount_result.is_valid
        
        description_result = TextValidator.validate_description(description_input)
        assert description_result.is_valid
        
        date_result = DateValidator.parse_and_validate(date_input, allow_future=False)
        assert date_result.is_valid
        
        # Criar transação
        transaction = TransactionService.create_transaction(
            session=test_session,
            user=test_user,
            category=test_category_expense,
            amount=amount_result.value,
            description=description_result.value,
            payment_method="credit_card",
            date=date_result.value,
            transaction_type=TransactionType.EXPENSE
        )
        
        # Verificar resultado
        assert transaction.amount == Decimal("150.75")
        assert transaction.description == "Almoço no restaurante"
        assert transaction.date.day == 15
        assert transaction.date.month == 12
        assert transaction.date.year == 2023
    
    def test_complete_investment_flow(self, test_session, test_user):
        """Testa fluxo completo de investimento"""
        # Dados de entrada
        ticker_input = "PETR4"
        quantity_input = "100"
        price_input = "25,50"
        
        # Validar entrada
        ticker_result = TickerValidator.validate_ticker(ticker_input, "stock")
        assert ticker_result.is_valid
        
        quantity_result = AmountValidator.parse_and_validate(quantity_input)
        assert quantity_result.is_valid
        
        price_result = AmountValidator.parse_and_validate(price_input)
        assert price_result.is_valid
        
        # Criar investimento
        investment = InvestmentService.create_investment(
            session=test_session,
            user=test_user,
            ticker=ticker_result.value,
            investment_type=InvestmentType.STOCK,
            quantity=quantity_result.value,
            price=price_result.value,
            purchase_date=datetime.now()
        )
        
        # Verificar resultado
        assert investment.ticker == "PETR4"
        assert investment.quantity == Decimal("100.00")
        assert investment.avg_price == Decimal("25.50")
        assert investment.total_invested == Decimal("2550.00")
    
    def test_financial_health_calculation(self, test_session, test_user, test_category_income, test_category_expense):
        """Testa cálculo completo de saúde financeira"""
        # Criar transações variadas
        transactions_data = [
            (test_category_income, Decimal("5000.00"), TransactionType.INCOME, "Salário"),
            (test_category_expense, Decimal("1200.00"), TransactionType.EXPENSE, "Aluguel"),
            (test_category_expense, Decimal("500.00"), TransactionType.EXPENSE, "Alimentação"),
            (test_category_expense, Decimal("300.00"), TransactionType.EXPENSE, "Transporte"),
        ]
        
        for category, amount, tx_type, description in transactions_data:
            TransactionService.create_transaction(
                session=test_session,
                user=test_user,
                category=category,
                amount=amount,
                description=description,
                payment_method="bank_transfer",
                date=datetime.now(),
                transaction_type=tx_type
            )
        
        # Obter resumo
        now = datetime.now()
        summary = TransactionService.get_monthly_summary(
            session=test_session,
            user=test_user,
            year=now.year,
            month=now.month
        )
        
        # Calcular saúde financeira
        score, status, details = FinancialAnalyzer.calculate_health_score(
            income=summary['total_income'],
            expenses=summary['total_expenses'],
            savings_rate=summary['savings_rate']
        )
        
        # Verificar resultados
        assert summary['total_income'] == Decimal("5000.00")
        assert summary['total_expenses'] == Decimal("2000.00")
        assert summary['balance'] == Decimal("3000.00")
        assert summary['savings_rate'] == Decimal("60.0")
        
        assert score >= 60  # Deve ter boa pontuação
        assert "🟢" in status or "🟡" in status  # Status bom ou excelente


# ==================== TESTES DE PERFORMANCE ====================

class TestPerformance:
    """Testes de performance e carga"""
    
    def test_large_dataset_performance(self, test_session, test_user, test_category_expense):
        """Testa performance com grande volume de dados"""
        import time
        
        # Criar muitas transações
        start_time = time.time()
        
        for i in range(1000):
            TransactionService.create_transaction(
                session=test_session,
                user=test_user,
                category=test_category_expense,
                amount=Decimal(f"{50 + (i % 100)}.00"),
                description=f"Transação {i}",
                payment_method="cash",
                date=datetime.now() - timedelta(days=i % 365),
                transaction_type=TransactionType.EXPENSE
            )
        
        creation_time = time.time() - start_time
        
        # Verificar se a criação foi razoavelmente rápida
        assert creation_time < 30  # Menos de 30 segundos para 1000 transações
        
        # Testar consulta
        start_time = time.time()
        
        transactions = TransactionService.get_user_transactions(
            session=test_session,
            user=test_user,
            limit=100
        )
        
        query_time = time.time() - start_time
        
        assert len(transactions) == 100
        assert query_time < 1  # Menos de 1 segundo para consulta
    
    def test_memory_usage(self, test_session):
        """Testa uso de memória"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Criar e processar dados
        users = []
        for i in range(100):
            user, _ = UserService.get_or_create_user(
                session=test_session,
                telegram_id=1000000 + i,
                username=f"user{i}",
                first_name=f"User",
                last_name=f"{i}"
            )
            users.append(user)
        
        current_memory = process.memory_info().rss
        memory_increase = current_memory - initial_memory
        
        # Verificar se o aumento de memória é razoável
        assert memory_increase < 50 * 1024 * 1024  # Menos de 50MB


# ==================== TESTES DE SEGURANÇA ====================

class TestSecurity:
    """Testes de segurança"""
    
    def test_sql_injection_prevention(self, test_session, test_user, test_category_expense):
        """Testa prevenção de SQL injection"""
        # Tentar injeção SQL na descrição
        malicious_description = "'; DROP TABLE transactions; --"
        
        # Deve ser tratado como texto normal
        transaction = TransactionService.create_transaction(
            session=test_session,
            user=test_user,
            category=test_category_expense,
            amount=Decimal("50.00"),
            description=malicious_description,
            payment_method="cash",
            date=datetime.now(),
            transaction_type=TransactionType.EXPENSE
        )
        
        # Verificar que a descrição foi salva como texto
        assert transaction.description == malicious_description
        
        # Verificar que as tabelas ainda existem
        count = test_session.query(Transaction).count()
        assert count >= 1
    
    def test_input_sanitization(self):
        """Testa sanitização de entrada"""
        # XSS attempt
        xss_input = "<script>alert('xss')</script>"
        
        result = TextValidator.validate_description(xss_input)
        assert not result.is_valid
        assert "caracteres não permitidos" in result.error_message.lower()
        
        # Caracteres especiais válidos
        valid_input = "Compra no Pão de Açúcar - R$ 50,00 (desconto 10%)"
        
        result = TextValidator.validate_description(valid_input)
        assert result.is_valid
    
    def test_amount_limits_enforcement(self):
        """Testa aplicação de limites de valores"""
        # Valor muito alto
        huge_amount = "999999999999.99"
        
        result = AmountValidator.parse_and_validate(huge_amount)
        assert not result.is_valid
        assert "máximo" in result.error_message.lower()
        
        # Valor negativo
        negative_amount = "-100.00"
        
        result = AmountValidator.parse_and_validate(negative_amount)
        assert not result.is_valid


# ==================== CONFIGURAÇÃO DOS TESTES ====================

@pytest.fixture(autouse=True)
def setup_test_config():
    """Configuração automática para todos os testes"""
    # Configurar limites menores para testes
    original_max = Config.MAX_TRANSACTION_AMOUNT
    original_min = Config.MIN_TRANSACTION_AMOUNT
    
    Config.MAX_TRANSACTION_AMOUNT = Decimal("100000.00")
    Config.MIN_TRANSACTION_AMOUNT = Decimal("0.01")
    
    yield
    
    # Restaurar valores originais
    Config.MAX_TRANSACTION_AMOUNT = original_max
    Config.MIN_TRANSACTION_AMOUNT = original_min


# ==================== RUNNER DOS TESTES ====================

if __name__ == "__main__":
    # Executar testes específicos
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--durations=10"
    ])