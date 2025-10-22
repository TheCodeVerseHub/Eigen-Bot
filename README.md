# Fun2Oosh - Discord Casino Bot

A fun, production-ready Discord bot featuring casino games, in-server economy, and responsible gaming features.

## Features

### 🎰 Games
- **Blackjack**: Full implementation with dealer AI, hit/stand, insurance
- **Roulette**: European wheel with multiple bet types (single, dozen, color, etc.)
- **Slots**: 3-reel slot machine with paytable and jackpot
- **Poker**: Basic Texas Hold'em scaffold (expandable)
- **Bowling**: Mini-game with wagering

### 💰 Economy System
- Wallet and bank system
- Work, daily, weekly rewards with cooldowns
- Transfer coins between users
- Leaderboard
- Transaction history

### 🛡️ Safety & Moderation
- Responsible gaming notices
- Wager limits and cooldowns
- Anti-fraud detection
- Admin controls for moderation
- Age verification (placeholder)

### 🔧 Technical Features
- Async/await throughout
- SQLite for development, PostgreSQL for production
- Docker support
- Comprehensive logging
- Unit tests
- Type hints and documentation

## Installation

### Prerequisites
- Python 3.11+
- Discord Bot Token (from [Discord Developer Portal](https://discord.com/developers/applications))

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/fun2oosh.git
   cd fun2oosh
   ```

2. Create virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your bot token and settings
   ```

5. Run the bot:
   ```bash
   python bot.py
   ```

## Configuration

### Environment Variables
- `DISCORD_TOKEN`: Your bot's token
- `DATABASE_URL`: Database connection string
- `OWNER_ID`: Your Discord user ID for admin commands
- `LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)
- `GUILD_ID`: For faster slash command sync during development

### Game Settings
Adjust in `.env`:
- `MIN_BET`: Minimum bet amount
- `MAX_BET`: Maximum bet amount
- `WORK_REWARD`: Coins earned from !work
- `DAILY_REWARD`: Daily reward amount
- `WEEKLY_REWARD`: Weekly reward amount

## Usage

### Basic Commands
- `^balance` - Check your wallet and bank
- `^work` - Earn coins (30 min cooldown)
- `^daily` - Claim daily reward
- `^leaderboard` - Top 10 richest users

### Games
- `^blackjack <bet>` - Start blackjack game
- `^roulette <type> <value> <bet>` - Play roulette
- `^slots <bet>` - Play slots

### Admin Commands
- `^add_money <user> <amount>` - Add coins to user
- `^reset_economy` - Reset all economy data

## Deployment

### Docker
```bash
docker build -t fun2oosh .
docker run -d --env-file .env fun2oosh
```

### Docker Compose
```bash
docker-compose up -d
```

### Production Hosting
- **Heroku**: Set env vars, deploy Python app
- **Render**: Connect repo, set env vars
- **Railway**: Similar to Render
- **AWS**: Use EC2 or Lambda

## Database

### Development (SQLite)
Default: `sqlite+aiosqlite:///fun2oosh.db`

### Production (PostgreSQL)
Set `DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db`

## Security

- Store tokens and secrets as environment variables
- Use `.env` file locally, never commit
- Implement proper error handling
- Monitor for rate limits
- Regular dependency updates

## Responsible Gaming

This bot includes responsible gaming features:
- Gambling addiction warnings
- Daily wager limits
- Age verification (implement in production)
- Clear odds and payout information
- Easy opt-out options

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new features
4. Ensure code passes linting
5. Submit pull request

## License

MIT License - see LICENSE file

## Support

- Create issue on GitHub
- Join our Discord server (link in bio)
- Check documentation in `/docs`

## Disclaimer

This bot is for entertainment purposes only. Gambling can be addictive. Please play responsibly. If you need help with gambling addiction, contact professional services.
