"""
Configuração e gerenciamento do banco de dados
Versão melhorada com connection pooling, retry logic e monitoramento
"""
import logging
import time
from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any
import threading
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event, Engine, text
from sqlalchemy.exc import (
    SQLAlchemyError, DisconnectionError, 
    OperationalError, IntegrityError
)
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import StaticPool, QueuePool
from sqlalchemy import MetaData

from config import Config, DEFAULT_CATEGORIES, Formatters
from models import (
    Base, User, Category, TransactionType, 
    Transaction, Investment, Alert
)

logger = logging.getLogger(__name__)


class DatabaseMetrics:
    """Métricas do banco de dados"""
    
    def __init__(self):
        self.connection_count = 0
        self.query_count = 0
        self.error_count = 0
        self.total_query_time = 0.0
        self.last_reset = datetime.now()
        self._lock = threading.Lock()
    
    def record_connection(self):
        with self._lock:
            self.connection_count += 1
    
    def record_query(self, execution_time: float):
        with self._lock:
            self.query_count += 1
            self.total_query_time += execution_time
    
    def record_error(self):
        with self._lock:
            self.error_count += 1
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            avg_query_time = (
                self.total_query_time / self.query_count 
                if self.query_count > 0 else 0
            )
            uptime = datetime.now() - self.last_reset
            
            return {
                'connections': self.connection_count,
                'queries': self.query_count,
                'errors': self.error_count,
                'avg_query_time_ms': round(avg_query_time * 1000, 2),
                'uptime_hours': round(uptime.total_seconds() / 3600, 2),
                'queries_per_hour': round(
                    self.query_count / (uptime.total_seconds() / 3600)
                    if uptime.total_seconds() > 0 else 0, 2
                )
            }
    
    def reset(self):
        with self._lock:
            self.connection_count = 0
            self.query_count = 0
            self.error_count = 0
            self.total_query_time = 0.0
            self.last_reset = datetime.now()


class Database:
    """Gerenciador avançado do banco de dados"""
    
    def __init__(self):
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[scoped_session] = None
        self.metrics = DatabaseMetrics()
        self._connection_retries = 3
        self._retry_delay = 1.0
        self._health_check_interval = 300  # 5 minutos
        self._last_health_check = None
        self._is_healthy = True
        
        self._initialize()
    
    def _initialize(self):
        """Inicializa a conexão com o banco"""
        try:
            self.engine = self._create_engine()
            self.SessionLocal = scoped_session(
                sessionmaker(
                    autocommit=False,
                    autoflush=False,
                    bind=self.engine,
                    expire_on_commit=False
                )
            )
            
            # Configurar eventos de monitoramento
            self._setup_events()
            
            logger.info("✅ Conexão com banco de dados estabelecida")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
            raise
    
    def _create_engine(self) -> Engine:
        """Cria a engine do SQLAlchemy com configurações otimizadas"""
        db_config = Config.get_database_config()
        
        if db_config['url'].startswith('sqlite'):
            # Configurações para SQLite
            engine = create_engine(
                db_config['url'],
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
                echo=db_config.get('echo', False),
                json_serializer=lambda obj: obj,
                future=True
            )
            
            # Habilitar foreign keys e WAL mode no SQLite
            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                # WAL mode para melhor concorrência
                cursor.execute("PRAGMA journal_mode=WAL")
                # Foreign keys
                cursor.execute("PRAGMA foreign_keys=ON")
                # Timeout para evitar locks
                cursor.execute("PRAGMA busy_timeout=30000")
                # Sincronização mais rápida
                cursor.execute("PRAGMA synchronous=NORMAL")
                # Cache size otimizado
                cursor.execute("PRAGMA cache_size=10000")
                cursor.close()
        
        else:
            # Configurações para PostgreSQL
            connect_args = {}
            
            # SSL para produção
            if Config.ENVIRONMENT == 'production':
                connect_args['sslmode'] = 'require'
            
            engine = create_engine(
                db_config['url'],
                pool_size=db_config.get('pool_size', 5),
                max_overflow=db_config.get('max_overflow', 10),
                pool_timeout=db_config.get('pool_timeout', 30),
                pool_pre_ping=db_config.get('pool_pre_ping', True),
                pool_recycle=3600,  # Reciclar conexões a cada hora
                echo=db_config.get('echo', False),
                connect_args=connect_args,
                future=True
            )
        
        return engine
    
    def _setup_events(self):
        """Configura eventos para monitoramento"""
        
        @event.listens_for(self.engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            self.metrics.record_connection()
            logger.debug("Nova conexão estabelecida")
        
        @event.listens_for(self.engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            context._query_start_time = time.time()
        
        @event.listens_for(self.engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            if hasattr(context, '_query_start_time'):
                execution_time = time.time() - context._query_start_time
                self.metrics.record_query(execution_time)
                
                # Log queries lentas
                if execution_time > 1.0:
                    logger.warning(f"Query lenta detectada: {execution_time:.2f}s")
    
    def create_tables(self):
        """Cria todas as tabelas no banco com retry logic"""
        for attempt in range(self._connection_retries):
            try:
                logger.info("Criando tabelas do banco de dados...")
                Base.metadata.create_all(bind=self.engine)
                logger.info("✅ Tabelas criadas com sucesso!")
                return
                
            except Exception as e:
                self.metrics.record_error()
                if attempt < self._connection_retries - 1:
                    logger.warning(f"Tentativa {attempt + 1} falhou: {e}. Tentando novamente...")
                    time.sleep(self._retry_delay * (attempt + 1))
                else:
                    logger.error(f"❌ Erro ao criar tabelas após {self._connection_retries} tentativas: {e}")
                    raise
    
    def drop_tables(self):
        """Remove todas as tabelas do banco (CUIDADO!)"""
        if Config.ENVIRONMENT == 'production':
            raise RuntimeError("❌ Não é possível dropar tabelas em produção!")
        
        logger.warning("🗑️ Removendo todas as tabelas do banco...")
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("✅ Tabelas removidas!")
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Context manager para sessões com retry e error handling"""
        session = None
        
        for attempt in range(self._connection_retries):
            try:
                session = self.SessionLocal()
                yield session
                session.commit()
                return
                
            except IntegrityError as e:
                if session:
                    session.rollback()
                logger.error(f"Erro de integridade: {e}")
                raise
                
            except (DisconnectionError, OperationalError) as e:
                if session:
                    session.rollback()
                self.metrics.record_error()
                
                if attempt < self._connection_retries - 1:
                    logger.warning(f"Erro de conexão (tentativa {attempt + 1}): {e}")
                    time.sleep(self._retry_delay * (attempt + 1))
                    # Tentar recriar a engine em caso de falha persistente
                    if attempt == self._connection_retries - 2:
                        self._recreate_engine()
                else:
                    logger.error(f"❌ Erro de conexão após {self._connection_retries} tentativas: {e}")
                    raise
                    
            except Exception as e:
                if session:
                    session.rollback()
                self.metrics.record_error()
                logger.error(f"Erro inesperado na sessão: {e}")
                raise
                
            finally:
                if session:
                    session.close()
    
    def _recreate_engine(self):
        """Recria a engine em caso de falha persistente"""
        try:
            logger.info("🔄 Recriando engine do banco de dados...")
            old_engine = self.engine
            
            # Criar nova engine
            self.engine = self._create_engine()
            self.SessionLocal.configure(bind=self.engine)
            
            # Fechar engine antiga
            if old_engine:
                old_engine.dispose()
            
            logger.info("✅ Engine recriada com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao recriar engine: {e}")
            raise
    
    def health_check(self) -> bool:
        """Verifica a saúde da conexão com o banco"""
        now = datetime.now()
        
        # Só executa health check se passou o intervalo
        if (self._last_health_check and 
            now - self._last_health_check < timedelta(seconds=self._health_check_interval)):
            return self._is_healthy
        
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT 1")).scalar()
                self._is_healthy = (result == 1)
                
            self._last_health_check = now
            
            if self._is_healthy:
                logger.debug("✅ Health check: banco de dados saudável")
            else:
                logger.warning("⚠️ Health check: possível problema no banco")
                
            return self._is_healthy
            
        except Exception as e:
            self.metrics.record_error()
            self._is_healthy = False
            logger.error(f"❌ Health check falhou: {e}")
            return False
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Retorna informações sobre as conexões"""
        if not self.engine:
            return {"status": "disconnected"}
        
        info = {
            "status": "connected" if self._is_healthy else "unhealthy",
            "engine_url": str(self.engine.url).replace(self.engine.url.password or "", "***"),
            "pool_size": getattr(self.engine.pool, 'size', None),
            "checked_out": getattr(self.engine.pool, 'checkedout', None),
            "overflow": getattr(self.engine.pool, 'overflow', None),
            "checked_in": getattr(self.engine.pool, 'checkedin', None),
        }
        
        info.update(self.metrics.get_stats())
        return info
    
    def init_user_categories(self, user: User, session: Session):
        """Inicializa as categorias padrão para um novo usuário"""
        logger.info(f"Criando categorias padrão para usuário {user.id}")
        
        try:
            categories_created = 0
            
            for transaction_type_str, categories in DEFAULT_CATEGORIES.items():
                # Converter string para enum
                transaction_type = (
                    TransactionType.INCOME if transaction_type_str == "income" 
                    else TransactionType.EXPENSE
                )
                
                for name, icon, description in categories:
                    # Verificar se categoria já existe
                    existing = session.query(Category).filter(
                        Category.user_id == user.id,
                        Category.name == name,
                        Category.type == transaction_type
                    ).first()
                    
                    if not existing:
                        category = Category(
                            user_id=user.id,
                            name=name,
                            type=transaction_type,
                            icon=icon,
                            description=description,
                            is_system=True
                        )
                        session.add(category)
                        categories_created += 1
            
            session.commit()
            logger.info(f"✅ {categories_created} categorias criadas para usuário {user.id}")
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Erro ao criar categorias para usuário {user.id}: {e}")
            raise
    
    def backup_database(self, backup_path: Optional[str] = None) -> str:
        """Cria backup do banco de dados"""
        import shutil
        from pathlib import Path
        
        if not backup_path:
            backup_path = Config.BACKUP_PATH
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if Config.DATABASE_URL.startswith('sqlite'):
            # Backup SQLite
            db_file = Config.DATABASE_URL.replace('sqlite:///', '')
            backup_file = f"{backup_path}/finance_bot_backup_{timestamp}.db"
            
            Path(backup_path).mkdir(exist_ok=True, parents=True)
            shutil.copy2(db_file, backup_file)
            
            logger.info(f"✅ Backup SQLite criado: {backup_file}")
            return backup_file
        
        else:
            # Backup PostgreSQL (requer pg_dump)
            import subprocess
            
            backup_file = f"{backup_path}/finance_bot_backup_{timestamp}.sql"
            Path(backup_path).mkdir(exist_ok=True, parents=True)
            
            cmd = f"pg_dump {Config.DATABASE_URL} > {backup_file}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"✅ Backup PostgreSQL criado: {backup_file}")
                return backup_file
            else:
                logger.error(f"❌ Erro no backup PostgreSQL: {result.stderr}")
                raise RuntimeError(f"Falha no backup: {result.stderr}")
    
    def optimize_database(self):
        """Otimiza o banco de dados"""
        logger.info("🔧 Iniciando otimização do banco de dados...")
        
        try:
            if Config.DATABASE_URL.startswith('sqlite'):
                with self.get_session() as session:
                    # VACUUM para compactar o banco
                    session.execute(text("VACUUM"))
                    # ANALYZE para atualizar estatísticas
                    session.execute(text("ANALYZE"))
                    logger.info("✅ SQLite otimizado (VACUUM + ANALYZE)")
            
            else:
                with self.get_session() as session:
                    # VACUUM e ANALYZE no PostgreSQL
                    session.execute(text("VACUUM ANALYZE"))
                    logger.info("✅ PostgreSQL otimizado (VACUUM ANALYZE)")
                    
        except Exception as e:
            logger.error(f"❌ Erro na otimização: {e}")
            raise
    
    def get_database_size(self) -> Dict[str, Any]:
        """Retorna informações sobre o tamanho do banco"""
        try:
            with self.get_session() as session:
                if Config.DATABASE_URL.startswith('sqlite'):
                    # Tamanho do arquivo SQLite
                    import os
                    db_file = Config.DATABASE_URL.replace('sqlite:///', '')
                    
                    if os.path.exists(db_file):
                        file_size = os.path.getsize(db_file)
                        
                        # Estatísticas das tabelas
                        tables_info = {}
                        for table_name in ['users', 'transactions', 'investments', 'categories', 'alerts']:
                            try:
                                count_result = session.execute(
                                    text(f"SELECT COUNT(*) FROM {table_name}")
                                ).scalar()
                                tables_info[table_name] = count_result or 0
                            except:
                                tables_info[table_name] = 0
                        
                        return {
                            'database_size_bytes': file_size,
                            'database_size_mb': round(file_size / (1024 * 1024), 2),
                            'tables': tables_info,
                            'total_records': sum(tables_info.values())
                        }
                
                else:
                    # PostgreSQL database size
                    db_name = Config.DATABASE_URL.split('/')[-1]
                    
                    size_result = session.execute(
                        text(f"SELECT pg_size_pretty(pg_database_size('{db_name}'))")
                    ).scalar()
                    
                    # Contagem de registros por tabela
                    tables_info = {}
                    for table_name in ['users', 'transactions', 'investments', 'categories', 'alerts']:
                        try:
                            count_result = session.execute(
                                text(f"SELECT COUNT(*) FROM {table_name}")
                            ).scalar()
                            tables_info[table_name] = count_result or 0
                        except:
                            tables_info[table_name] = 0
                    
                    return {
                        'database_size': size_result,
                        'tables': tables_info,
                        'total_records': sum(tables_info.values())
                    }
                    
        except Exception as e:
            logger.error(f"❌ Erro ao obter tamanho do banco: {e}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, days_to_keep: int = 365):
        """Remove dados antigos do banco"""
        if Config.ENVIRONMENT == 'production':
            logger.warning("⚠️ Limpeza em produção - procedendo com cuidado")
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        try:
            with self.get_session() as session:
                # Limpar alertas antigos enviados
                old_alerts = session.query(Alert).filter(
                    Alert.is_sent == True,
                    Alert.sent_at < cutoff_date
                ).count()
                
                if old_alerts > 0:
                    session.query(Alert).filter(
                        Alert.is_sent == True,
                        Alert.sent_at < cutoff_date
                    ).delete()
                    
                    logger.info(f"🗑️ {old_alerts} alertas antigos removidos")
                
                # Aqui você pode adicionar outras limpezas se necessário
                # Por exemplo, logs de sistema, caches expirados, etc.
                
                session.commit()
                logger.info(f"✅ Limpeza concluída - dados anteriores a {cutoff_date.date()}")
                
        except Exception as e:
            logger.error(f"❌ Erro na limpeza: {e}")
            raise
    
    def reset_metrics(self):
        """Reseta as métricas do banco"""
        self.metrics.reset()
        logger.info("📊 Métricas do banco resetadas")
    
    def cleanup(self):
        """Limpa recursos do banco"""
        try:
            if self.SessionLocal:
                self.SessionLocal.remove()
            
            if self.engine:
                self.engine.dispose()
                
            logger.info("🧹 Recursos do banco liberados")
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza: {e}")


class DatabaseManager:
    """Manager singleton para o banco de dados"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.db = Database()
            self._initialized = True
    
    def get_database(self) -> Database:
        """Retorna a instância do banco"""
        return self.db
    
    def health_check(self) -> bool:
        """Health check via manager"""
        return self.db.health_check()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Métricas via manager"""
        return self.db.metrics.get_stats()


# Instância global do banco
db_manager = DatabaseManager()
db = db_manager.get_database()


# Funções auxiliares para facilitar o uso
def get_db() -> Generator[Session, None, None]:
    """Alias para db.get_session()"""
    with db.get_session() as session:
        yield session


def init_database():
    """Inicializa o banco de dados"""
    try:
        db.create_tables()
        logger.info("✅ Banco de dados inicializado com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        raise


def check_database_health() -> bool:
    """Verifica a saúde do banco"""
    return db.health_check()


def get_database_info() -> Dict[str, Any]:
    """Retorna informações completas do banco"""
    return {
        'connection_info': db.get_connection_info(),
        'size_info': db.get_database_size(),
        'health': db.health_check(),
        'metrics': db.metrics.get_stats()
    }


def backup_database(backup_path: Optional[str] = None) -> str:
    """Cria backup do banco"""
    return db.backup_database(backup_path)


def optimize_database():
    """Otimiza o banco de dados"""
    db.optimize_database()


def cleanup_old_data(days_to_keep: int = 365):
    """Remove dados antigos"""
    db.cleanup_old_data(days_to_keep)


# Decorator para retry automático em operações de banco
def database_retry(max_retries: int = 3, delay: float = 1.0):
    """Decorator para retry automático em operações de banco"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                    
                except (DisconnectionError, OperationalError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Tentativa {attempt + 1} falhou: {e}. Tentando novamente...")
                        time.sleep(delay * (attempt + 1))
                    else:
                        logger.error(f"❌ Operação falhou após {max_retries} tentativas")
                        
                except Exception as e:
                    logger.error(f"❌ Erro não recuperável: {e}")
                    raise
            
            raise last_exception
        return wrapper
    return decorator


# Context manager para transações com rollback automático
@contextmanager
def database_transaction():
    """Context manager para transações com rollback automático"""
    with db.get_session() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


# Função para migração de dados
def migrate_data():
    """Executa migrações de dados se necessário"""
    logger.info("🔄 Verificando necessidade de migrações...")
    
    try:
        with db.get_session() as session:
            # Verificar se existem tabelas
            inspector = session.get_bind().inspect(session.get_bind())
            tables = inspector.get_table_names()
            
            if not tables:
                logger.info("📋 Nenhuma tabela encontrada - primeira execução")
                return
            
            # Aqui você pode adicionar lógica de migração específica
            # Por exemplo, verificar versões de schema, adicionar colunas, etc.
            
            logger.info("✅ Verificação de migração concluída")
            
    except Exception as e:
        logger.error(f"❌ Erro na migração: {e}")
        raise


# Função para inicialização completa
def initialize_database_system():
    """Inicializa todo o sistema de banco de dados"""
    try:
        logger.info("🚀 Inicializando sistema de banco de dados...")
        
        # 1. Inicializar banco
        init_database()
        
        # 2. Verificar migrações
        migrate_data()
        
        # 3. Health check inicial
        if not check_database_health():
            raise RuntimeError("❌ Health check inicial falhou")
        
        # 4. Otimizar se necessário (apenas em desenvolvimento)
        if Config.ENVIRONMENT == 'development':
            logger.info("🔧 Otimizando banco (desenvolvimento)")
            optimize_database()
        
        logger.info("✅ Sistema de banco de dados inicializado com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro na inicialização do sistema: {e}")
        raise