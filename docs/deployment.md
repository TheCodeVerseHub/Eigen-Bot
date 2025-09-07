# Deployment Guide

## Local Development
1. Clone the repository
2. Create virtual environment: `python -m venv venv`
3. Activate: `venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Linux/Mac)
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in values
6. Run: `python bot.py`

## Production Deployment

### Docker
1. Build image: `docker build -t fun2oosh .`
2. Run container: `docker run -d --env-file .env fun2oosh`

### Docker Compose
```yaml
version: '3.8'
services:
  fun2oosh:
    build: .
    env_file: .env
    restart: unless-stopped
```

### Heroku
1. Create Heroku app
2. Set environment variables
3. Deploy via Git or Docker

### Render
1. Connect GitHub repo
2. Set environment variables
3. Deploy

### AWS/Railway/Fly
Similar process - set env vars and deploy Python app

## Environment Variables
- `DISCORD_TOKEN`: Bot token from Discord Developer Portal
- `DATABASE_URL`: PostgreSQL URL for production
- `OWNER_ID`: Your Discord user ID
- `LOG_LEVEL`: INFO/DEBUG
- `TOPGG_TOKEN`: For top.gg integration

## Database Migration
For production, use PostgreSQL:
- Install asyncpg
- Update DATABASE_URL
- Run migrations if needed

## Security
- Never commit .env file
- Use environment variables for secrets
- Keep dependencies updated
- Monitor for vulnerabilities

## Scaling
- For 2k+ guilds, consider sharding
- Use Redis for caching
- Monitor rate limits
- Implement proper error handling
