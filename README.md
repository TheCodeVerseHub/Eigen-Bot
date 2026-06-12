# Eigen Bot 

> **A feature-rich, production-ready Discord bot for community engagement, support tickets, entertainment, and powerful moderation tools.**

Eigen Bot is an all-in-one Discord bot designed for thriving communities. Built with modern async Python and discord.py, it offers a modular suite of features accessible via hybrid commands (both prefix `?` and slash `/` commands).

[**Quick Start**](#quick-start) • [**Feature Index**](#feature-index) • [**Detailed Setup**](./docs/SETUP_GUIDE.md) • [**Support Server**](https://discord.gg/yourlink)

---

### Quick Links
* **[Ticket System](./docs/TICKETS.md)** — Professional thread-based support management.
* **[Gaming & Quests](./docs/GAMES.md)** — Counting game, CodeBuddy, and Daily Quests.
* **[Full Command Reference](./docs/FEATURES.md)** — Comprehensive command library with syntax and examples.
* **[Advanced Configuration](./docs/SETUP_GUIDE.md)** — Docker, Env Vars, and Database info.

---

### Quick Start
Get Eigen Bot running in under 2 minutes. Ensure you have **Python 3.11+** and **FFMpeg** installed.

#### 1. Clone the repository
```
git clone [https://github.com/youngcoder45/Eigen-bot-In-Python.git](https://github.com/youngcoder45/Eigen-bot-In-Python.git)
cd Eigen-bot-In-Python
```

#### 2. Setup Virtual Environment
```
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

#### 3. Install Dependencies
```
pip install -r requirements.txt
```

#### 4. Configure & Run
```
cp .env.example .env  # Add your DISCORD_TOKEN to .env
python bot.py
```

---

### Essential Env Vars

| Variable         | Description                                               |
|------------------|-----------------------------------------------------------|
| `DISCORD_TOKEN`    | Required. Your bot application token.                     |
| `OWNER_ID`         | Your Discord user ID for admin overrides.                |
| `GUILD_IDS`        | Comma-separated IDs for fast slash command syncing.      |

---

## Feature Index

Every module is moved to detailed markdown files in `/docs` for easy scanning.
### Support Tickets
Thread-based categories (Bugs, Support, Partnerships) with persistent button panels.
### Engagement Games
Anti-grief Counting game, CodeBuddy quizzes, and Daily Quest rewards.
### Starboard System
Automatic highlighting of community-voted content with dynamic embeds.
### Tag System
High-speed custom text snippet storage and retrieval.
### Elections & Voting
Democratic decision-making with weighted roles.
### Staff Applications
DM-based application system with admin review channels.

---

## Secondary Information

<details>
<summary><b>Fun & Utility Commands</b></summary>

### Fun
- `?joke`
- `?trivia`
- `?8ball`
- `?coinflip`
- `?roll`
- `?fridge`

### Utility
- `?afk`
- `?setbirthday`
- `?remindme`
- `/timestamp`

### Admin utilities
- `/say` — Make the bot send a message.
- `/edit` — Edit a bot message sent via `/say` (by message ID; opens a modal).
- `/react` — Add a reaction as the bot (emoji + optional message link; defaults to last message in the channel).

### Moderation
- `?chowkidar` (alias: `?ch`) — Start tracking a user (staff only).
- `?lc` (alias: `?listchowki`) — List currently tracked users (staff only).

### CodeBuddy practice
- `/question <category>` — Sends a practice MCQ; reply with `a`/`b`/`c` in that channel to get ✅/❌ feedback (no points).

### Social
- `?quote`
- `?meme`
- `/suggest`
- `/bumplb`

Full details available in **FEATURES.md**

</details>

---

<details>
<summary><b>Technical Excellence</b></summary>

### Architecture
Modular Cog-based structure for easy hot-reloading (`?reload`).
### Persistence
Uses **aiosqlite** for async database operations across dedicated `.db` files.
### Security
Role-based access control (RBAC) and parameterized SQL queries to prevent injection.
### Deployment
Fully containerized for **Docker** and **Docker Compose**.

</details>

---

<details>
<summary><b>Contributing & Legal</b></summary>

### Contribute
We welcome PRs! See **[CONTRIBUTING.md](CONTRIBUTING.md)**

### Economy
Economy features have moved to the `another-bot/` repository.

### License
[MIT License](LICENSE)

### Legal
[Terms of Service](TERMS_OF_SERVICE.md) | [Privacy Policy](PRIVACY_POLICY.md)

</details>

---

<div align="center">

## Eigen Bot  
### Where Community Meets Support

Developed by **[@youngcoder45](https://github.com/youngcoder45)** & **[@1Frodox](https://github.com/1Frodox)**

[GitHub](https://github.com/youngcoder45/Eigen-bot-In-Python) • [Issues](https://github.com/youngcoder45/Eigen-bot-In-Python/issues)

Made with ❤️ for Discord communities

</div>
