# Eigen Bot - Comprehensive Discord Community & Economy Bot

> **A feature-rich, production-ready Discord bot combining economy systems, community engagement, entertainment, and powerful moderation tools.**

Eigen Bot is an all-in-one Discord bot designed for thriving communities. Built with modern async Python and discord.py, it offers a complete suite of features from economy management and casino games to starboard highlights, voting systems, and custom tags—all with hybrid command support (both prefix `f?` and slash `/` commands).

---

## Core Features

### **Economy System**
A full-featured virtual currency system for your server:
- **Wallet & Bank**: Secure storage for user coins with separate wallet/bank balances
- **Income Commands**:
  - `f?work` / `/work` - Earn coins through work (30min cooldown)
  - `f?collect` / `/collect` - Hourly reward collection
  - `f?daily` - Claim daily rewards
  - `f?weekly` - Claim weekly rewards
- **Transfers**: `f?transfer @user <amount>` - Send coins to other members
- **Leaderboard**: `f?leaderboard` - View top 10 richest users
- **Profile**: `f?profile [@user]` - View detailed user profile with stats
- **Transaction History**: Full audit trail of all economic activity
- **Anti-Fraud Protection**: Built-in detection and prevention systems

### **Casino & Games**
Professional casino implementation with responsible gaming features:
- **Blackjack**: Full implementation with dealer AI, hit/stand, double down, insurance
- **Roulette**: European wheel with multiple bet types (numbers, dozens, colors, odds/evens)
- **Slots**: 3-reel slot machine with paytable and progressive jackpot
- **Poker**: Texas Hold'em framework (expandable)
- **Bowling**: Mini-game with wagering support
- **Responsible Gaming**: 
  - Configurable bet limits (min/max)
  - Daily wager limits per user
  - Cooldown systems to prevent excessive gambling
  - Addiction awareness notices

### **Starboard System**
Highlight the best messages in your community:
- **Automatic Highlighting**: Messages that reach a star threshold appear in starboard
- **Customizable**:
  - Set custom star emoji (, , etc.)
  - Adjustable threshold (1-50 stars)
  - Self-starring enabled/disabled
- **Beautiful Embeds**: Dynamic colors based on star count, author thumbnails, timestamps
- **Real-time Updates**: Starboard messages update as stars are added/removed
- **Smart Handling**: Tracks who starred what, prevents duplicates, handles uncached messages
- **Admin Tools**: `f?starboard_cleanup` to remove invalid entries
- **Commands**: 
  - `f?starboard setup #channel <threshold> <emoji>`
  - `f?starboard stats` - View server statistics
  - `f?starboard toggle` - Enable/disable system

### **Tag System**
Create and share custom text snippets:
- **Create Tags**: `f?tags create <name> <content>` - Store reusable text
- **Retrieve Tags**: `f?tag <name>` - Quickly fetch stored content
- **Edit Tags**: `f?tags edit <name> <new_content>` - Update existing tags
- **Delete Tags**: `f?tags delete <name>` - Remove unwanted tags
- **List Tags**: `f?tags list` - View all server tags
- **Usage Tracking**: Tracks how many times each tag is used
- **Per-Server**: Tags are unique to each guild

### � **Election/Voting System**
Democratic decision-making for your community:
- **Create Elections**: `f?election create <title> <candidates> [duration]`
- **Weighted Voting**: Vote strength based on user roles/tenure
- **Multiple Candidates**: Support for 2-10 candidates per election
- **Live Results**: Real-time vote counting and display
- **Interactive Voting**: Button-based voting interface
- **Vote Changes**: Users can change their vote before election ends
- **Timed Elections**: Auto-close after specified duration (1-1440 minutes)
- **Visual Results**: Beautiful result displays with percentages and vote counts

### **Invite Tracker System**
Professional invite tracking and analytics:
- **Invite Codes**: `/invitecodes` - View your invite codes and usage statistics
- **Invited List**: `/invitedlist` - List members you've invited to the server
- **Check Inviter**: `/inviter` - See who invited a specific member
- **Leaderboard**: `/inviteleaderboard` - Server-wide invite rankings
- **Real-time Tracking**: Automatic detection of invite usage
- **Fake Detection**: Flags accounts less than 7 days old
- **Leave Tracking**: Updates stats when invited members leave
- **Detailed Analytics**: Total, valid, left, and fake invite statistics

### **Fun Commands**
Entertainment and engagement features:
- **Programming Jokes**: `f?joke` - Get a clean programming-related joke
- **Compliments**: `f?compliment [@user]` - Give professional programming compliments
- **Fortune**: `f?fortune` - Receive a programming-themed fortune
- **Trivia**: `f?trivia` - Programming trivia questions with categories
- **8-Ball**: `f?8ball <question>` - Magic 8-ball responses
- **Coin Flip**: `f?coinflip` - Heads or tails
- **Dice Roll**: `f?roll [size] [count]` - Roll dice (supports custom sizes and counts)

### � **Community Engagement**
Build an active, engaged community:
- **Random Quotes**: `f?quote` - Inspirational programming quotes
- **Random Questions**: `f?question` - Programming discussion starters
- **Memes**: `f?meme` - Programming humor (placeholder API integration)
- **Suggestions**: Submit and discuss community ideas
- **QOTD (Question of the Day)**: Automated daily discussion prompts

### **Utility Commands**
Helpful tools for server management and user convenience:
- **Emote List**: `f?emotes [search]` - Browse server emojis with optional search
- **Member Count**: `f?membercount` - View current server member count
- **Random Color**: `f?randomcolor` - Generate random hex colors with preview
- **Reminders**: `f?remindme <time> <message>` - Set personal reminders (10m, 2h, 1d format)
- **User Info**: `f?whois [@user]` - Detailed user information and stats
- **Invite Info**: View detailed information about server invites

### **Admin & Moderation**
Powerful tools for server administrators:
- **Economy Management**:
  - `f?add_money @user <amount>` - Give coins to users
  - `f?reset_economy CONFIRM` - Reset all economy data (with confirmations)
- **Permission-Based**: All admin commands restricted to bot owner
- **Audit Logs**: All admin actions are logged
- **Safe Guards**: Multiple confirmation steps for destructive actions


---

## **Technical Excellence**

### **Architecture & Design**
- **Async/Await**: Full async implementation for optimal performance
- **Hybrid Commands**: Every command works with both `f?` prefix and `/` slash commands
- **Cog-Based Structure**: Modular design for easy maintenance and extensibility
- **Type Hints**: Comprehensive type annotations throughout codebase
- **Error Handling**: Graceful error handling with user-friendly messages
- **Unknown Command Silence**: Unknown commands produce no output (clean UX)

### **Database & Persistence**
- **SQLAlchemy ORM**: Modern async database operations
- **SQLite (Dev)**: Fast development with file-based database
- **PostgreSQL (Production)**: Scalable production deployment
- **Multiple Databases**: Separate SQLite DBs for tags, starboard, invites
- **Data Integrity**: Proper constraints, indexes, and transaction handling
- **Migration Ready**: Easy schema updates and data migrations

### **Performance & Reliability**
- **Connection Pooling**: Efficient database connection management
- **Caching**: Smart caching for starboard and invite systems
- **Rate Limiting**: Built-in cooldown management
- **Graceful Degradation**: Continues working even if some features fail
- **Comprehensive Logging**: Detailed logs for debugging and monitoring
- **Raw Event Handling**: Starboard processes uncached messages efficiently

### **Security & Safety**
- **Environment Variables**: Secure token and config storage
- **Permission Checks**: Role-based command access control
- **Input Validation**: Sanitization of user inputs
- **SQL Injection Prevention**: Parameterized queries throughout
- **Anti-Fraud**: Detection systems for economy abuse
- **Responsible Gaming**: Daily limits and cooldowns for gambling

---

## Installation & Setup

### **Prerequisites**
- Python 3.11 or higher
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- Git (for cloning)

### **Quick Start**

1. **Clone the Repository**
   ```bash
   git clone https://github.com/TheCodeVerseHub/Eigen-Bot.git
   cd Eigen-Bot
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv .venv
   
   # Linux/macOS
   source .venv/bin/activate
   
   # Windows
   .venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your bot token and settings
   ```

5. **Run the Bot**
   ```bash
   python bot.py
   ```

### **Environment Variables**

Create a `.env` file with the following:

```env
# Required
DISCORD_TOKEN=your_bot_token_here

# Database (optional, defaults to SQLite)
DATABASE_URL=sqlite+aiosqlite:///eigen.db
# For production: postgresql+asyncpg://user:pass@host:port/dbname

# Bot Configuration
OWNER_ID=your_discord_user_id
LOG_LEVEL=INFO

# Development (optional)
GUILD_ID=your_test_server_id  # For faster slash command sync

# Economy Settings
MIN_BET=10
MAX_BET=10000
WORK_REWARD=100
DAILY_REWARD=500
WEEKLY_REWARD=2500
DAILY_WAGER_LIMIT=100000
```

---

## Usage Guide

### **Command Prefixes**
- **Prefix Commands**: `f?command` (e.g., `f?balance`)
- **Slash Commands**: `/command` (e.g., `/balance`)
- **Hybrid**: Most commands support both formats!

### **Economy Commands**
```
f?balance [@user]       - Check wallet and bank balance
f?work                  - Earn coins (30min cooldown)
f?collect              - Hourly reward (1h cooldown)
f?daily                - Claim daily reward (24h cooldown)
f?weekly               - Claim weekly reward (7d cooldown)
f?transfer @user amt   - Send coins to another user
f?leaderboard          - Top 10 richest users
f?profile [@user]      - View detailed profile
```

### **Casino Commands**
```
f?blackjack <bet>                           - Play blackjack
f?roulette <type> <value> <bet>            - Play roulette
  Types: number, dozen, color, even/odd
f?slots <bet>                              - Play slot machine
```

### **Starboard Commands**
```
f?starboard setup #channel <threshold> <emoji>  - Setup starboard
f?starboard channel #channel                    - Change channel
f?starboard threshold <number>                  - Change star requirement
f?starboard emoji <emoji>                       - Change star emoji
f?starboard stats                               - View statistics
f?starboard toggle                              - Enable/disable
f?starboard_cleanup confirm                     - Clean invalid entries
```

### **Tag Commands**
```
f?tag <name>                - Retrieve a tag
f?tags create <name> <content>  - Create new tag
f?tags edit <name> <content>    - Edit existing tag
f?tags delete <name>            - Delete a tag
f?tags list                     - List all tags
```

### **Election Commands**
```
f?election create <title> <candidates> [duration]  - Start election
f?election results                                 - View results
f?election end                                     - Force end election
```

### **Invite Tracker Commands**
```
f?invitecodes              - View your invite codes and usage
f?invitedlist              - List members you've invited
f?inviter [@member]        - Check who invited a member
f?inviteleaderboard        - Server invite rankings
f?syncinvites             - Sync invite cache (Admin)
f?invitedocs              - View documentation
```

### **Fun Commands**
```
f?joke                - Programming joke
f?compliment [@user]  - Give compliment
f?fortune            - Programming fortune
f?trivia             - Programming trivia question
f?8ball <question>   - Magic 8-ball
f?coinflip           - Flip a coin
f?roll [size] [count] - Roll dice
```

### **Community Commands**
```
f?quote              - Random programming quote
f?question           - Random programming question
f?meme               - Programming meme
```

### **Utility Commands**
```
f?emotes [search]              - List server emojis
f?membercount                  - Server member count
f?randomcolor                  - Random color generator
f?remindme <time> <message>    - Set reminder (10m, 2h, 1d)
f?whois [@user]                - User information
```

### **Admin Commands** (Owner Only)
```
f?add_money @user <amount>     - Give coins to user
f?reset_economy CONFIRM        - Reset all economy data
```

---

## Docker Deployment

### **Using Docker**
```bash
# Build image
docker build -t eigen-bot .

# Run container
docker run -d --env-file .env eigen-bot
```

### **Using Docker Compose**
```bash
docker-compose up -d
```

### **Docker Compose Example**
```yaml
version: '3.8'
services:
  eigen-bot:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

---

## Production Hosting

### **Recommended Platforms**

#### **Railway** (Recommended)
1. Connect GitHub repository
2. Add environment variables
3. Deploy automatically on push

#### **Render**
1. Create new Web Service
2. Connect repository
3. Set environment variables
4. Deploy

#### **Heroku**
1. Create new app
2. Set environment variables (Config Vars)
3. Deploy via Git or GitHub integration

#### **AWS EC2**
1. Launch Ubuntu instance
2. Install Python 3.11+
3. Clone repo and setup
4. Use systemd or PM2 for process management

#### **VPS (DigitalOcean, Linode, etc.)**
1. Setup Ubuntu 22.04 server
2. Install dependencies
3. Setup systemd service
4. Configure nginx reverse proxy (optional)

### **Production Checklist**
- [ ] Set `DATABASE_URL` to PostgreSQL
- [ ] Configure proper `LOG_LEVEL`
- [ ] Set up automated backups
- [ ] Monitor bot health and logs
- [ ] Keep dependencies updated
- [ ] Rotate bot token periodically
- [ ] Set up error alerting

---

## Database Management

### **Development (SQLite)**
```env
DATABASE_URL=sqlite+aiosqlite:///eigen.db
```
- Perfect for testing and development
- File-based, easy to backup
- No external dependencies

### **Production (PostgreSQL)**
```env
DATABASE_URL=postgresql+asyncpg://user:password@host:port/database
```
- Scalable for large servers
- Better concurrent access
- Advanced features and indexing

### **Database Files**
```
data/
├── eigen.db          # Main economy database (SQLAlchemy)
├── tags.db           # Tag system (aiosqlite)
├── starboard.db      # Starboard system (aiosqlite)
└── invites.db        # Invite tracker system (aiosqlite)
```

---

## Testing

### **Run Tests**
```bash
# Install dev dependencies
pip install pytest pytest-asyncio

# Run test suite
pytest

# Run with coverage
pytest --cov=. --cov-report=html
```

### **Test Structure**
```
tests/
├── conftest.py          # Shared fixtures
├── test_economy.py      # Economy tests
└── __init__.py
```

---

## Contributing

We welcome contributions! Here's how:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

### **Contribution Guidelines**
- Add tests for new features
- Follow existing code style
- Update documentation
- Ensure all tests pass
- Use type hints
- Write clear commit messages

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

---

## Support & Documentation

### **Getting Help**
- **Documentation**: Check `/docs` folder
- **Bug Reports**: [Open an issue](https://github.com/TheCodeVerseHub/Eigen-Bot/issues)
- **Feature Requests**: [Open an issue](https://github.com/TheCodeVerseHub/Eigen-Bot/issues)
- **Discord**: Join our support server (link in bio)

### **Documentation**
- [Deployment Guide](docs/deployment.md)
- [Top.gg Submission](docs/topgg_submission.md)

---

## Responsible Gaming Disclaimer

**Important Notice**: This bot is designed for **entertainment purposes only**.

- Virtual currency has no real-world value
- Gambling can be addictive
- Please play responsibly
- Take breaks if needed
- If you have concerns about gambling addiction, seek professional help

**Resources**:
- [National Council on Problem Gambling](https://www.ncpgambling.org/)
- [Gamblers Anonymous](https://www.gamblersanonymous.org/)

---

## Roadmap

### **Planned Features**
- [ ] Web dashboard for server configuration
- [ ] Advanced moderation tools
- [ ] Custom game modes and tournaments
- [ ] Achievement system
- [ ] Social features (friends, gifts)
- [ ] Seasonal events and limited-time content
- [ ] Multi-language support
- [ ] API for third-party integrations

---

## Acknowledgments

Built with:
- [discord.py](https://github.com/Rapptz/discord.py) - Discord API wrapper
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM and database toolkit
- [aiosqlite](https://github.com/omnilib/aiosqlite) - Async SQLite
- [python-dotenv](https://github.com/theskumar/python-dotenv) - Environment management

Special thanks to:
- The discord.py community
- All contributors and testers
- You, for using Eigen Bot!

---

<div align="center">

**Eigen Bot** - Where Community Meets Economy

[GitHub](https://github.com/TheCodeVerseHub/Eigen-Bot) • [Issues](https://github.com/TheCodeVerseHub/Eigen-Bot/issues) • [Discord](https://discord.gg/your-server)

Made with ❤️ for Discord communities

</div>
