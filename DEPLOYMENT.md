# GSIN Platform Deployment Guide

## Overview
This guide covers deployment of the GSIN trading platform, including backend, frontend, database, and supporting services.

## Prerequisites

### Required Services
- PostgreSQL database (Supabase recommended)
- Python 3.10+
- Node.js 18+
- Redis (optional, for caching)
- Sentry account (for error tracking)

### Environment Variables

#### Backend (.env)
```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/dbname
# Or use Supabase
SUPABASE_DB_URL=postgresql://...

# JWT
JWT_SECRET_KEY=your-secret-key-min-32-chars

# Market Data APIs
TWELVEDATA_API_KEY=your-key
ALPACA_API_KEY=your-key
ALPACA_SECRET_KEY=your-secret
POLYGON_API_KEY=your-key
FINNHUB_API_KEY=your-key

# Sentry
SENTRY_DSN=your-sentry-dsn

# CORS
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# Workers
EVOLUTION_INTERVAL_SECONDS=480
MONITORING_WORKER_INTERVAL_SECONDS=900
MAX_CONCURRENT_BACKTESTS=3

# MCN Storage
MCN_STORAGE_PATH=./mcn_store
```

#### Frontend (.env.local)
```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Backend Deployment

### 1. Setup
```bash
cd GSIN-backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Database Migration
```bash
# Run Alembic migrations
alembic upgrade head

# Seed initial data
python scripts/seed_plans.py
python scripts/setup_admin_accounts.py
```

### 3. Run Security Audit
```bash
python scripts/run_security_audit.py
```

### 4. Run Tests
```bash
# Run all tests
python backend/run_all_tests.py

# Or with pytest
pytest backend/tests/ -v
```

### 5. Start Server
```bash
# Development
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Production (with Gunicorn)
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Frontend Deployment

### 1. Setup
```bash
cd GSIN.fin
npm install
```

### 2. Build
```bash
npm run build
```

### 3. Start
```bash
# Development
npm run dev

# Production
npm start
```

## Docker Deployment

### Using Docker Compose
```bash
docker-compose up -d
```

### Manual Docker Build
```bash
# Backend
docker build -t gsin-backend -f Dockerfile .
docker run -p 8000:8000 --env-file .env gsin-backend

# Frontend
cd GSIN.fin
docker build -t gsin-frontend .
docker run -p 3000:3000 --env-file .env.local gsin-frontend
```

## Production Checklist

### Security
- [ ] All environment variables set and secure
- [ ] JWT_SECRET_KEY is strong (32+ chars)
- [ ] CORS configured for production domains only
- [ ] HTTPS enabled
- [ ] Security headers configured
- [ ] Rate limiting enabled
- [ ] SQL injection protection verified
- [ ] XSS protection enabled

### Performance
- [ ] Database indexes created
- [ ] Connection pooling configured
- [ ] Caching enabled
- [ ] CDN configured (for static assets)
- [ ] Load balancer configured (if needed)

### Monitoring
- [ ] Sentry configured and tested
- [ ] Health check endpoints working
- [ ] Logging configured
- [ ] Metrics collection enabled
- [ ] Alerts configured

### Database
- [ ] Migrations run
- [ ] Backup strategy in place
- [ ] Connection pooling configured
- [ ] Indexes verified

### Workers
- [ ] Evolution Worker running
- [ ] Monitoring Worker running
- [ ] Backtest Worker configured
- [ ] Worker intervals set appropriately

## Health Checks

### Backend Health
```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### API Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check DATABASE_URL
   - Verify database is accessible
   - Check firewall rules

2. **Workers Not Running**
   - Check logs for errors
   - Verify worker threads started
   - Check database connectivity

3. **Market Data API Errors**
   - Verify API keys are set
   - Check rate limits
   - Verify API provider status

4. **Frontend Can't Connect to Backend**
   - Check NEXT_PUBLIC_BACKEND_URL
   - Verify CORS settings
   - Check network connectivity

## Scaling

### Horizontal Scaling
- Use load balancer for multiple backend instances
- Use Redis for shared cache
- Use database connection pooling
- Use CDN for static assets

### Vertical Scaling
- Increase worker threads
- Increase database connections
- Increase memory allocation
- Optimize database queries

## Backup and Recovery

### Database Backups
```bash
# PostgreSQL backup
pg_dump -h host -U user -d dbname > backup.sql

# Restore
psql -h host -U user -d dbname < backup.sql
```

### MCN Storage Backups
- MCN state stored in `mcn_store/`
- Backup regularly
- Include in disaster recovery plan

## Support

For issues or questions:
- Check logs: `backend/logs/`
- Review API docs: `/docs`
- Check health endpoints: `/health`, `/ready`
- Review monitoring: `/api/monitoring/metrics`

