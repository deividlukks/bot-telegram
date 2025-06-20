"""
Configurações para os testes
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base
from database import Database

@pytest.fixture(scope="session")
def test_db():
    """Cria banco de dados de teste"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    
    db = Database()
    db.engine = engine
    db.SessionLocal = SessionLocal
    
    yield db
    
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def session(test_db):
    """Cria sessão para testes"""
    with test_db.get_session() as session:
        yield session