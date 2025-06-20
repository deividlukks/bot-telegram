# 🏗️ Arquitetura do Finance Bot

## Visão Geral

O Finance Bot segue uma arquitetura em camadas com separação clara de responsabilidades:
┌─────────────────────────────────────┐
│         Telegram Bot API            │
├─────────────────────────────────────┤
│          Handlers Layer             │
│   (main, finance, investment...)    │
├─────────────────────────────────────┤
│         Services Layer              │
│  (Business Logic & Validation)     │
├─────────────────────────────────────┤
│          Models Layer               │
│    (SQLAlchemy ORM Models)         │
├─────────────────────────────────────┤
│         Database Layer              │
│    (PostgreSQL/SQLite)             │
└─────────────────────────────────────┘

## Componentes Principais

### Handlers
- Recebem e processam mensagens do Telegram
- Gerenciam estados da conversa
- Delegam lógica para Services

### Services
- Contêm toda lógica de negócio
- Validam dados
- Executam operações no banco

### Models
- Definem estrutura dos dados
- Relacionamentos entre entidades
- Validações básicas

### Utils
- Funções auxiliares
- Formatação e parsing
- Helpers reutilizáveis

## Fluxo de Dados

1. Usuário envia mensagem
2. Handler apropriado é acionado
3. Handler valida entrada básica
4. Service executa lógica de negócio
5. Model persiste no banco
6. Handler formata e retorna resposta

## Decisões de Design

### Uso de Decimal
Todos valores monetários usam `Decimal` para garantir precisão.

### Context Managers
Sessões do banco sempre usam context managers para garantir fechamento.

### Type Hints
Todo código usa type hints para melhor manutenibilidade.

### Async/Await
Handlers são assíncronos para melhor performance.