# GSIN Trading Platform

A comprehensive AI-powered trading platform with strategy engine, brain AI, market data integration, and automated trading execution.

## Features

- **Strategy Engine**: Create, backtest, and evolve trading strategies
- **Brain AI**: MCN-powered strategy recommendations and signal generation
- **Market Data**: Real-time and historical market data from multiple providers
- **Trading Execution**: Paper and real trading with broker integration
- **Groups**: Collaborative trading groups with strategy sharing
- **Admin Dashboard**: Comprehensive metrics and system management
- **Royalties**: Strategy creator royalty system

## Architecture

### Backend (FastAPI)
- FastAPI REST API
- PostgreSQL database (Supabase)
- Background workers (Evolution, Monitoring, Backtest)
- MCN (Memory Cluster Networks) for AI
- Market data providers with fallback
- WebSocket for real-time data

### Frontend (Next.js)
- Next.js 14 with TypeScript
- Zustand for state management
- Real-time WebSocket connections
- Responsive UI

## Quick Start

### Backend
```bash
cd GSIN-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up environment variables
cp config/.env.example .env
# Edit .env with your configuration

# Run migrations
alembic upgrade head

# Start server
uvicorn backend.main:app --reload
```

### Frontend
```bash
cd GSIN.fin
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your configuration

# Start development server
npm run dev
```

## Testing

```bash
# Run all tests
cd GSIN-backend
python backend/run_all_tests.py

# Run specific test suite
pytest backend/tests/unit -v
pytest backend/tests/integration -v
pytest backend/tests/e2e -v

# Run with coverage
pytest --cov=backend --cov-report=html
```

## Security Audit

```bash
cd GSIN-backend
python scripts/run_security_audit.py
```

## Performance Testing

```bash
cd GSIN-backend
python scripts/run_performance_test.py
```

## API Documentation

Once the backend is running:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Health Checks

- Health: http://localhost:8000/health
- Readiness: http://localhost:8000/ready
- Detailed Health: http://localhost:8000/api/monitoring/health/detailed (admin only)

## Project Structure

```
gsin_new_git/
├── GSIN-backend/          # Backend FastAPI application
│   ├── backend/
│   │   ├── api/           # API endpoints
│   │   ├── brain/         # Brain AI service
│   │   ├── broker/         # Broker integration
│   │   ├── db/             # Database models and CRUD
│   │   ├── market_data/    # Market data providers
│   │   ├── strategy_engine/# Strategy engine
│   │   ├── workers/        # Background workers
│   │   └── utils/          # Utilities
│   ├── tests/              # Test suite
│   └── scripts/            # Utility scripts
├── GSIN.fin/              # Frontend Next.js application
└── docs/                  # Documentation
```

## Environment Variables

See `DEPLOYMENT.md` for complete environment variable documentation.

## Deployment

See `DEPLOYMENT.md` for detailed deployment instructions.

## License

Proprietary - All rights reserved

## Support

For issues or questions, please contact the development team.

