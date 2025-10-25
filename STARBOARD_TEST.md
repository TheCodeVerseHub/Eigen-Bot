# 🎯 Starboard Testing Guide

## ✅ Fixed Issues:
1. **No more spam logging** - Only logs star emoji reactions now
2. **Performance optimized** - Filters reactions before processing
3. **Detailed debugging** - Shows exactly what's happening at each step

## 📋 Step-by-Step Testing:

### 1️⃣ Run Setup Command
```
f?starboard setup #starboard-channel 1 ⭐
```
**Replace `#starboard-channel` with your actual channel name!**

**Expected console output:**
```
✅ Settings saved to database
```

### 2️⃣ Verify Setup
```
f?starboard
```
**Should show:**
- ✅ Status: Enabled
- Channel: #your-channel
- Threshold: 1
- Emoji: ⭐

### 3️⃣ Test Star Reaction

**Action:** React with ⭐ to ANY message in your server

**Expected console output:**
```
⭐ Starboard: Star reaction added by YourName on message 123456
💫 Starboard: Star added to DB for message 123456 by user 789012
📊 Starboard: Message 123456 now has 1 stars (threshold: 1)
⭐ Starboard: Creating new starboard message for 123456 with 1 stars (threshold: 1)
📤 Starboard: Sending starboard embed to starboard-channel
✅ Starboard: Successfully posted message 987654 to starboard
```

**Expected result in Discord:**
- Message appears in your starboard channel
- Shows "⭐ 1 | Starred Message"
- Has author info and jump link

### 4️⃣ If It Doesn't Work

**Check console for these error messages:**

❌ **"No settings found"**
→ Run `f?starboard setup` again

❌ **"Channel not found"**
→ Bot can't see the channel, check permissions

❌ **"Channel is not a text channel"**
→ Make sure you're using a text channel, not voice/forum

❌ **"Error creating starboard message: Forbidden"**
→ Bot needs "Send Messages" and "Embed Links" permissions in starboard channel

### 5️⃣ Common Issues

**Issue:** No console output at all
**Fix:** Make sure bot is running and starboard cog loaded

**Issue:** "Star already exists" in console
**Fix:** Normal - means you already starred that message

**Issue:** Reactions from other emojis are logged
**Fix:** Restart bot with new code - old version logged everything

## 🔍 Database Check

Run this to see if settings exist:
```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('data/starboard.db')
cursor = conn.cursor()
cursor.execute('SELECT guild_id, channel_id, threshold, star_emoji FROM starboard_settings')
print('Settings:', cursor.fetchall())
cursor.execute('SELECT message_id, COUNT(*) FROM user_stars GROUP BY message_id')
print('Stars:', cursor.fetchall())
conn.close()
"
```

## 🎉 Success Indicators:
- ✅ Only star reactions logged in console
- ✅ Message appears in starboard channel immediately
- ✅ Star count updates when more people react
- ✅ No spam from other emoji reactions

## 🆘 Still Not Working?

Share the **exact console output** you see, including:
1. What command you ran
2. What emoji you used
3. All console messages (or lack of them)
