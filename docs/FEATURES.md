# Full Feature Library

This document contains the complete list of utility, fun, and community modules.

## Starboard System
Automatically highlight high-quality community content.
- `?starboard setup` : Define channel, emoji, and reaction threshold.
- `?starboard cleanup` : Admin tool to remove invalid or deleted entries.

## Tag System
Store and retrieve custom text snippets.
- `?tags create <name> <content>` : Save a reusable snippet.
- `?tag <name>` : Fetch a saved tag.

## Election & Voting
- `?election create <title> <candidates>` : Start a democratic vote.
- Supports **Weighted Voting** based on user roles or tenure.

## Utility & Community
- **AFK**: `?afk [reason]` - Auto-responds to mentions when you're away.
- **Birthdays**: `?setbirthday <DD/MM>` - Automated birthday wishes.
- **Suggestions**: `/suggest <text>` - Creates an embed with voting reactions and a discussion thread.
- **Disboard Tracker**: `/bumplb` - View the leaderboard for users who bump the server.
- **Migrate Conversation**: `/migrate-conversation <destination> [count]` - Move the last few messages to another channel via webhook (requires Manage Messages).

[← Back to README](../README.md)
