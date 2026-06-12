# Full Feature and Command Library

Eigen Bot supports both slash commands (`/command`) and prefix commands
(`?command`). Hybrid commands work with both forms unless a row notes
`prefix-only` or `slash-only`.

Use `/help` or `?helpmenu` in Discord for interactive help. This file is the
static reference for server admins and contributors who want to compare the
documentation with the command cogs.

## Help

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/help [query]` | slash | Show all commands, or details for one command or cog. | `/help tickets` |
| `?helpmenu [query]` | prefix | Show the interactive help menu. | `?helpmenu starboard` |

## Admin

These commands require administrator permissions.

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/reload <cog_name>` | slash | Reload a cog after code or config changes. | `/reload tickets` |
| `?reload <cog_name>` | prefix | Reload a cog by module name. | `?reload fun` |
| `/sync` | slash | Sync slash commands with Discord. | `/sync` |
| `?sync` | prefix | Sync slash commands from chat. | `?sync` |
| `?diagnose` | prefix-only | Hidden diagnostic command for administrators. | `?diagnose` |
| `/say <text>` | slash-only | Send a message as the bot. | `/say Welcome to the server` |
| `/edit <message_id>` | slash-only | Edit a bot message previously sent with `/say`. | `/edit 123456789012345678` |
| `/react <emoji> [message_link]` | slash-only | Add a reaction as the bot, using a message link or the latest channel message. | `/react thumbs_up` |

## AFK

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/afk [reason]` or `?afk [reason]` | hybrid | Mark yourself AFK with an optional reason. | `/afk In a meeting` |
| `?unafk` | prefix-only | Remove your AFK status manually. Aliases: `?back`, `?return`. | `?unafk` |
| `/afklist` or `?afklist` | hybrid | List current AFK users. Aliases: `?afkstatus`, `?whoafk`. | `/afklist` |
| `?afkignore` | prefix-only | Toggle AFK mention replies in the current channel. | `?afkignore` |
| `?afkignored` | prefix-only | List channels where AFK replies are disabled. | `?afkignored` |
| `?afkreset <member>` | prefix-only | Admin reset for a member's AFK status. | `?afkreset @Sam` |
| `?afkclear <member>` | prefix-only | Admin clear for a member's AFK status. | `?afkclear @Sam` |

## Birthdays

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/birthday <day> <month> <year>` or `?birthday <day> <month> <year>` | hybrid | Save a birthday for automatic wishes. | `/birthday 14 8 2000` |

## Bump Leaderboard

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/bumplb` or `?bumplb` | hybrid | Show the top bumpers. Alias: `?blb`. | `/bumplb` |
| `/bumpstats` or `?bumpstats` | hybrid | Show total bumps and most recent bumper. Alias: `?bst`. | `/bumpstats` |
| `/setbumpchannel <channel>` or `?setbumpchannel <channel>` | hybrid | Set the channel where Disboard bumps count. | `/setbumpchannel #bump` |
| `/addbumps <user> <amount>` | hybrid | Admin add bumps to a user. | `/addbumps @Sam 3` |
| `/removebumps <user> <amount>` | hybrid | Admin remove bumps from a user. | `/removebumps @Sam 1` |
| `?mybumps` | prefix-only | Show your personal bump stats. | `?mybumps` |
| `?topbump` | prefix-only | Show the top three bumpers. | `?topbump` |

## Watchlog Moderation

These commands are staff-only.

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/setwlchannel` or `?setwlchannel` | hybrid | Set the current channel as the watchlog channel. | `/setwlchannel` |
| `/chowkidar <user>` or `?chowkidar <user>` | hybrid | Start tracking a user's actions. Alias: `?ch`. | `/chowkidar @Sam` |
| `?lc` | prefix-only | List currently tracked users. Alias: `?listchowki`. | `?lc` |
| `/endwl <user>` or `?endwl <user>` | hybrid | Stop tracking a user. | `/endwl @Sam` |
| `/purgewl <user>` or `?purgewl <user>` | hybrid | Delete watchlogs for a user. | `/purgewl @Sam` |

## CodeBuddy

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/codehelp` | slash-only | Show CodeBuddy help and FAQ buttons. | `/codehelp` |
| `?quizhelp` | prefix-only | Show CodeBuddy help from prefix chat. | `?quizhelp` |
| `/question [category]` | slash-only | Send a practice MCQ without points. | `/question python` |
| `/frequency <minutes>` | slash-only | Set automatic quiz frequency from 1 to 30 minutes. | `/frequency 10` |
| `/codeleaderboard` or `?codeleaderboard` | slash/prefix | Show coding quiz leaderboard. Prefix alias: `?clb`. | `/codeleaderboard` |
| `/codestats` or `?codestats` | slash/prefix | Show your personal coding quiz stats. Prefix alias: `?cst`. | `/codestats` |
| `/codeweek` or `?codeweek` | slash/prefix | Show the weekly coding leaderboard. Prefix aliases: `?cw`, `?cwlb`. | `/codeweek` |
| `/codestreak` or `?codestreak` | slash/prefix | Show the coding streak leaderboard. Prefix aliases: `?csl`, `?cslb`. | `/codestreak` |

## Daily Quests

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/dailyquest` or `?dailyquest` | slash/prefix | View daily quest progress and rewards. Prefix aliases: `?dq`, `?quests`, `?quest`, `?daily`, `?checklist`. | `/dailyquest` |
| `?inventory` | prefix-only | Show quest rewards inventory. Aliases: `?inv`, `?rewards`. | `?inventory` |

## Counting Game

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/setcountingchannel <channel>` | slash-only | Set the channel for the counting game. | `/setcountingchannel #counting` |
| `?donateguild` | prefix-only | Donate one personal save to the server save pool. Alias: `?dg`. | `?donateguild` |
| `?guildsaves` | prefix-only | Show the server save pool. Aliases: `?gsaves`, `?serversaves`, `?ssaves`. | `?guildsaves` |
| `/highscoretable` or `?highscoretable` | hybrid | Show recent counting highscores. Alias: `?highscores`. | `/highscoretable` |
| `?mcl` | prefix-only | Show the most-count leaderboard. Alias: `?tc`. | `?mcl` |
| `?mrl` | prefix-only | Show the most-ruined leaderboard. | `?mrl` |
| `?scs` | prefix-only | Show server counting stats. | `?scs` |

## Community and Fun

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/quote` or `?quote` | hybrid | Send a motivational or programming quote. | `/quote` |
| `?meme` | prefix-only | Send a programming meme. | `?meme` |
| `/reload-data` or `?reload-data` | hybrid | Admin reload for quotes and questions. | `/reload-data` |
| `/fridge` or `?fridge` | hybrid | Send a generated fridge image. | `/fridge` |
| `?pat` | prefix-only | Send a wholesome pat gif. | `?pat` |
| `/compliment` or `?compliment` | hybrid | Send a programming compliment. | `/compliment` |
| `/joke` or `?joke` | hybrid | Send a programming joke. | `/joke` |
| `/fortune` or `?fortune` | hybrid | Send a programming fortune. | `/fortune` |
| `/flip` or `?flip` | hybrid | Flip a coin. | `/flip` |
| `?topic` | prefix-only | Send a random chat topic. | `?topic` |
| `?gif [query]` | prefix-only | Send a gif matching a query, or a random gif. | `?gif coding` |
| `?singledice` | prefix-only | Roll a single die. Use `?roll` for multi-dice. | `?singledice` |
| `/choose <options>` or `?choose <options>` | hybrid | Choose randomly from a list of options. | `/choose pizza, noodles, tacos` |
| `/tod` or `?tod` | hybrid | Start a Truth or Dare prompt with buttons. | `/tod` |
| `?truth` | prefix-only | Send a truth prompt. | `?truth` |
| `?dare` | prefix-only | Send a dare prompt. | `?dare` |

## Utility

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/join-vc` or `?join-vc` | hybrid | Join your voice channel. | `/join-vc` |
| `/about` or `?about` | hybrid | Show bot information. | `/about` |
| `/song [user]` or `?song [user]` | hybrid | Show Spotify listening status. Prefix aliases: `?sp`, `?spotify`. | `/song @Sam` |
| `?uptime` | prefix-only | Hidden uptime diagnostic command. | `?uptime` |
| `/bug <bug>` or `?bug <bug>` | hybrid | Report a small bot bug. | `/bug Button did not respond` |
| `/support` or `?support` | hybrid | Get the support server invite link. | `/support` |
| `/newfeature <feature>` | slash-only | Suggest a new bot feature. | `/newfeature Add polls` |
| `/feedback <rating> <message>` | slash-only | Share bot feedback. | `/feedback 5 Great bot` |
| `/timestamp <date> [time] [style] [timezone]` | slash-only | Generate Discord timestamp markup. | `/timestamp 2026-01-04 14:30` |
| `?dm` | prefix-only | Explain why users should not DM members for help. | `?dm` |
| `/emotes [search]` or `?emotes [search]` | hybrid | List custom server emojis. | `/emotes cat` |
| `/membercount` or `?membercount` | hybrid | Show server member count. | `/membercount` |
| `/randomcolor` or `?randomcolor` | hybrid | Generate a random hex color. | `/randomcolor` |
| `?roll [size] [count]` | prefix-only | Roll dice, defaulting to one d6. | `?roll 20 2` |
| `/remindme <time> <reminder>` or `?remindme <time> <reminder>` | hybrid | Set a reminder with `s`, `m`, `h`, `d`, or `w`. | `/remindme 10m Submit report` |
| `?inviteinfo <code>` | prefix-only | Show information about a Discord invite. | `?inviteinfo abc123` |
| `/avatar [user]` or `?avatar [user]` | hybrid | Show a user's avatar. | `/avatar @Sam` |
| `/serverinfo` or `?serverinfo` | hybrid | Show server details and stats. | `/serverinfo` |
| `/color <hex_code>` or `?color <hex_code>` | hybrid | Preview a hex color. | `/color #3366ff` |
| `?distance <x1,y1> <x2,y2>` | prefix-only | Calculate distance between coordinates. | `?distance 0,0 3,4` |
| `?grep [-i] <pattern> [limit]` | prefix-only | Search recent messages. Aliases: `?search`, `?find`. | `?grep -i error 50` |

## Staff Applications

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/setapps <channel>` | slash-only | Set the staff application review channel. | `/setapps #staff-review` |
| `/panel` or `?panel` | hybrid | Post the staff application panel. | `/panel` |
| `/applications <user>` | slash-only | View a user's staff applications. | `/applications @Sam` |

## Suggestions

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/setsuggestchannel <channel>` or `?setsuggestchannel <channel>` | hybrid | Set the channel where suggestions are posted. | `/setsuggestchannel #suggestions` |
| `/suggest <message>` or `?suggest <message>` | hybrid | Submit a server suggestion. | `/suggest Add weekly events` |

## Tags

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/tag <name>` or `?tag <name>` | hybrid | Fetch a saved tag. | `/tag rules` |
| `/tags list [search]` or `?tags list [search]` | hybrid group | List tags, optionally filtered by search text. | `/tags list faq` |
| `/tags create <name> <content>` | hybrid group | Create a tag. Requires Manage Messages. | `/tags create faq Read #faq` |
| `/tags edit <name> <content>` | hybrid group | Edit a tag. Requires Manage Messages. | `/tags edit faq Read #help` |
| `/tags delete <name>` | hybrid group | Delete a tag. Requires Manage Messages. | `/tags delete faq` |

## Starboard

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/starboard_info` or `?starboard_info` | hybrid | Show starboard usage tips and setup help. | `/starboard_info` |
| `/starboard` or `?starboard` | hybrid group | Show current starboard status. | `/starboard` |
| `/starboard setup <channel> [threshold] [emoji]` | hybrid group | Configure starboard channel, threshold, and emoji. | `/starboard setup #starboard 3 star` |
| `/starboard channel <channel>` | hybrid group | Change the starboard output channel. | `/starboard channel #highlights` |
| `/starboard threshold <threshold>` | hybrid group | Set required stars from 1 to 50. | `/starboard threshold 5` |
| `/starboard emoji <emoji>` | hybrid group | Set the reaction emoji used for starring. | `/starboard emoji star` |
| `/starboard toggle` | hybrid group | Enable or disable the starboard. | `/starboard toggle` |
| `/starboard stats` | hybrid group | Show starboard activity statistics. | `/starboard stats` |
| `/starboard_cleanup confirm` or `?starboard_cleanup confirm` | hybrid | Admin cleanup for invalid starboard entries. | `/starboard_cleanup confirm` |

## Tickets

For a deeper setup guide, see [TICKETS.md](./TICKETS.md).

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/ticketpanel [channel]` or `?ticketpanel [channel]` | hybrid | Create a persistent ticket panel. | `/ticketpanel #support` |
| `/ticketlog <channel>` or `?ticketlog <channel>` | hybrid | Configure ticket action logs. | `/ticketlog #ticket-logs` |
| `/ticketlog-disable` or `?ticketlog-disable` | hybrid | Disable ticket action logs. | `/ticketlog-disable` |
| `/ticketsupport [role]` or `?ticketsupport [role]` | hybrid | Set the general support role. | `/ticketsupport @Support` |
| `/ticketsupport-disable` or `?ticketsupport-disable` | hybrid | Disable the support role setting. | `/ticketsupport-disable` |
| `/ticketreport [role]` or `?ticketreport [role]` | hybrid | Set the report handling role. | `/ticketreport @Mods` |
| `/ticketreport-disable` or `?ticketreport-disable` | hybrid | Disable the report role setting. | `/ticketreport-disable` |
| `/ticketpartner [role]` or `?ticketpartner [role]` | hybrid | Set the partnership handling role. | `/ticketpartner @Partnerships` |
| `/ticketpartner-disable` or `?ticketpartner-disable` | hybrid | Disable the partnership role setting. | `/ticketpartner-disable` |
| `/tickets [status]` or `?tickets [status]` | hybrid | List open, closed, or total tickets. | `/tickets open` |
| `/ticketstats` or `?ticketstats` | hybrid | View support ticket metrics. | `/ticketstats` |
| `/forceclose [reason]` or `?forceclose [reason]` | hybrid | Staff close for the current ticket thread. | `/forceclose Resolved` |

## Text to Speech

| Command | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `/logintts <name>` or `?logintts <name>` | hybrid | Join voice and announce with a chosen TTS name. | `/logintts Alex` |
| `/leavevc` or `?leavevc` | hybrid | Leave the current voice channel. | `/leavevc` |
| `/tts <text>` or `?tts <text>` | hybrid | Speak text in the connected voice channel. | `/tts Standup starts now` |

[<- Back to README](../README.md)
