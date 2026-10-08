import discord
from discord.ext import commands
import datetime
import asyncio
import os
from collections import defaultdict, deque

# إعدادات البوت والصلاحيات (Intents)
intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.moderation = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- الآي دي الخاص بالروم (Channels IDs) ---
LOG_INVITE = 1557691413666471987      # لوج الدعوات
LOG_MESSAGES = 1557690879572058145    # لوج الرسايل (والصور/الإيموجي/الاستيكرات)
LOG_LINKS = 1557699350480560128       # لوج الروابط
LOG_MUTE = 1557690705596522496        # لوج الكتم
LOG_CHANNELS = 1557700403154395228    # لوج القنوات
LOG_ROLES = 1557691659414937700       # لوج الرولات
LOG_KICK = 1557691161605316690        # لوج الطرد
LOG_BAN = 1557691284024463430         # لوج البان

# متغيرات لتتبع الحماية (Anti-Spam & Anti-Nuke)
channel_deletions = defaultdict(deque)
user_mentions = defaultdict(deque)
user_messages = defaultdict(deque)

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح باسم: {bot.user.name}")
    print("بوت الحماية جاهز للعمل بكامل الكفاءة!")

# ----------------------------------------------------
# 1. نظام تتبع الدعوات (Invite Tracking)
# ----------------------------------------------------
invites_cache = {}

@bot.event
async def on_guild_join(guild):
    try:
        invites_cache[guild.id] = await guild.invites()
    except Exception:
        pass

@bot.event
async def on_invite_create(invite):
    try:
        invites_cache[invite.guild.id] = await invite.guild.invites()
    except Exception:
        pass

@bot.event
async def on_invite_delete(invite):
    try:
        invites_cache[invite.guild.id] = await invite.guild.invites()
    except Exception:
        pass

@bot.event
async def on_member_join(member):
    guild = member.guild
    log_channel = guild.get_channel(LOG_INVITE)
    if not log_channel:
        return

    try:
        old_invites = invites_cache.get(guild.id, [])
        new_invites = await guild.invites()
        invites_cache[guild.id] = new_invites
        
        inviter = None
        for new_inv in new_invites:
            for old_inv in old_invites:
                if new_inv.code == old_inv.code and new_inv.uses > old_inv.uses:
                    inviter = new_inv.inviter
                    break
            if inviter:
                break

        embed = discord.Embed(
            title="📥 انضمام عضو جديد",
            description=f"العضو الجديد: {member.mention}\nتم دعوته بواسطة: {inviter.mention if inviter else 'غير معروف (رابط مباشر أو مجهول)'}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"خطأ في تتبع الدعوات: {e}")

# ----------------------------------------------------
# 2 & 9. مراقبة تعديل/حذف الرسائل وإعادة توجيه الوسائط
# ----------------------------------------------------
@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    log_channel = message.guild.get_channel(LOG_MESSAGES)
    if not log_channel:
        return

    embed = discord.Embed(
        title="🗑️ حذف رسالة",
        description=f"**المستخدم:** {message.author.mention}\n**الروم:** {message.channel.mention}\n**الرسالة المحذوفة:**\n{message.content or '*بدون نص (ميديا فقط)*'}",
        color=discord.Color.red(),
        timestamp=datetime.datetime.utcnow()
    )
    await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.content == after.content:
        return
    log_channel = before.guild.get_channel(LOG_MESSAGES)
    if not log_channel:
        return

    embed = discord.Embed(
        title="✏️ تعديل رسالة",
        description=f"**المستخدم:** {before.author.mention}\n**الروم:** {before.channel.mention}\n**قبل التعديل:**\n{before.content}\n\n**بعد التعديل:**\n{after.content}",
        color=discord.Color.orange(),
        timestamp=datetime.datetime.utcnow()
    )
    await log_channel.send(embed=embed)

# ----------------------------------------------------
# 3, 7, 8 & 10. نظام منع الروابط، المنشنات، التكرار، والوسائط (Mute & Logging)
# ----------------------------------------------------
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    guild = message.guild
    author = message.author
    now = datetime.datetime.utcnow()

    # أ. إعادة توجيه الصور، الإيموجي، والاستيكرات
    if message.attachments or message.stickers or len(message.raw_emojis) > 0:
        media_log = guild.get_channel(LOG_MESSAGES)
        if media_log:
            embed = discord.Embed(
                title="🖼️ إعادة توجيه ميديا / استيكر / إيموجي",
                description=f"**المسترسل:** {author.mention}\n**الروم:** {message.channel.mention}",
                color=discord.Color.blue(),
                timestamp=now
            )
            if message.content:
                embed.add_field(name="النص المرافق:", value=message.content, inline=False)
            await media_log.send(embed=embed)

    # ب. فلتر الروابط (باستثناء رابط السيرفر)
    if "http://" in message.content or "https://" in message.content or "discord.gg/" in message.content:
        guild_invites = []
        try:
            guild_invites = [inv.code for inv in await guild.invites()]
        except:
            pass
        
        is_server_link = any(code in message.content for code in guild_invites) or str(guild.id) in message.content
        
        if not is_server_link:
            try:
                await message.delete()
            except:
                pass

            duration = datetime.timedelta(hours=1)
            try:
                await author.timeout(duration, reason="إرسال روابط خارجية ممنوعة")
            except:
                pass

            link_log = guild.get_channel(LOG_LINKS)
            if link_log:
                embed = discord.Embed(
                    title="🔗 مخالفة: إرسال رابط",
                    description=f"**العضو:** {author.mention}\n**الروم:** {message.channel.mention}\n**الرابط المحذوف:**\n{message.content}",
                    color=discord.Color.dark_red(),
                    timestamp=now
                )
                await link_log.send(embed=embed)

            mute_log = guild.get_channel(LOG_MUTE)
            if mute_log:
                embed = discord.Embed(
                    title="🔇 تم كتم عضو (روابط)",
                    description=f"**العضو:** {author.mention}\n**المسؤول:** نظام الحماية التلقائي\n**المدة:** ساعة واحدة",
                    color=discord.Color.dark_purple(),
                    timestamp=now
                )
                await mute_log.send(embed=embed)

            await message.channel.send(f"⚠️ {author.mention} تم كتمه تلقائياً لمخالفة قوانين السيرفر (إرسال روابط).")
            return

    # ج. منع المنشنات الجماعية (> 3 منشنات في 10 ثوانٍ)
    if len(message.mentions) >= 3:
        user_mentions[author.id].append(now)
        while user_mentions[author.id] and (now - user_mentions[author.id][0]).total_seconds() > 10:
            user_mentions[author.id].popleft()

        if len(user_mentions[author.id]) >= 3:
            duration = datetime.timedelta(hours=1)
            try:
                await author.timeout(duration, reason="سبام منشنات جماعية")
            except:
                pass

            mute_log = guild.get_channel(LOG_MUTE)
            if mute_log:
                embed = discord.Embed(
                    title="🔇 مخالفة: سبام منشن",
                    description=f"**العضو:** {author.mention}\n**السبب:** عمل أكثر من 3 منشنات في وقت قصير\n**المدة:** ساعة واحدة",
                    color=discord.Color.dark_purple(),
                    timestamp=now
                )
                await mute_log.send(embed=embed)

            await message.channel.send(f"⚠️ {author.mention} تم كتمه تلقائياً لمخالفة قوانين السيرفر (سبام منشن).")
            user_mentions[author.id].clear()
            return

    # د. منع تكرار الرسائل (3 رسائل ورا بعض في أقل من 10 ثواني)
    user_messages[author.id].append(now)
    while user_messages[author.id] and (now - user_messages[author.id][0]).total_seconds() > 10:
        user_messages[author.id].popleft()

    if len(user_messages[author.id]) >= 3:
        duration = datetime.timedelta(hours=1)
        try:
            await author.timeout(duration, reason="سبام رسائل متكررة وسريعة")
        except:
            pass

        mute_log = guild.get_channel(LOG_MUTE)
        if mute_log:
            embed = discord.Embed(
                title="🔇 مخالفة: سبام رسائل",
                description=f"**العضو:** {author.mention}\n**السبب:** إرسال رسائل متعددة وسريعة بشكل متكرر\n**المدة:** ساعة واحدة",
                color=discord.Color.dark_purple(),
                timestamp=now
            )
            await mute_log.send(embed=embed)

        await message.channel.send(f"⚠️ {author.mention} تم كتمه تلقائياً لمخالفة قوانين السيرفر (سبام رسائل).")
        user_messages[author.id].clear()
        return

    await bot.process_commands(message)

# ----------------------------------------------------
# 4. مراقبة القنوات وحماية السيرفر (Anti-Mass Channel Delete)
# ----------------------------------------------------
@bot.event
async def on_guild_channel_create(channel):
    guild = channel.guild
    log_channel = guild.get_channel(LOG_CHANNELS)
    if not log_channel:
        return

    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_create):
        user = entry.user
        embed = discord.Embed(
            title="📁 إنشاء روم جديدة",
            description=f"**المسؤول:** {user.mention}\n**اسم الروم:** {channel.name}\n**الرابط:** {channel.jump_url}",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.utcnow()
        )
        await log_channel.send(embed=embed)
        break

@bot.event
async def on_guild_channel_delete(channel):
    guild = channel.guild
    log_channel = guild.get_channel(LOG_CHANNELS)
    if not log_channel:
        return

    now = datetime.datetime.utcnow()
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        user = entry.user
        
        embed = discord.Embed(
            title="🗑️ حذف روم",
            description=f"**المسؤول:** {user.mention}\n**اسم الروم المحذوفة:** {channel.name}",
            color=discord.Color.dark_red(),
            timestamp=now
        )
        await log_channel.send(embed=embed)

        channel_deletions[user.id].append(now)
        while channel_deletions[user.id] and (now - channel_deletions[user.id][0]).total_seconds() > 60:
            channel_deletions[user.id].popleft()

        if len(channel_deletions[user.id]) > 3:
            member = guild.get_member(user.id)
            if member:
                try:
                    for role in member.roles:
                        if role.permissions.administrator or role.permissions.manage_channels:
                            await member.remove_roles(role, reason="تخريب السيرفر: حذف رومات متعددة")
                    
                    if log_channel:
                        await log_channel.send(f"🚨 **تحذير أمني خطير!** تم سحب الصلاحيات فوراً من {member.mention} لتخطيه الحد المسموح لحذف الرومات.")
                except Exception as e:
                    print(f"خطأ في سحب الصلاحيات: {e}")
        break

# ----------------------------------------------------
# 5. مراقبة تعديلات الرولات والصلاحيات (Roles Logging)
# ----------------------------------------------------
@bot.event
async def on_guild_role_create(role):
    log_channel = role.guild.get_channel(LOG_ROLES)
    if not log_channel:
        return
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_create):
        embed = discord.Embed(
            title="✨ إنشاء رول جديد",
            description=f"**المسؤول:** {entry.user.mention}\n**اسم الرول:** {role.name}",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        await log_channel.send(embed=embed)
        break

@bot.event
async def on_guild_role_delete(role):
    log_channel = role.guild.get_channel(LOG_ROLES)
    if not log_channel:
        return
    async for entry in role.guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
        embed = discord.Embed(
            title="🗑️ حذف رول",
            description=f"**المسؤول:** {entry.user.mention}\n**اسم الرول المحذوف:** {role.name}",
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        await log_channel.send(embed=embed)
        break

# ----------------------------------------------------
# 6. لوج العقوبات الإدارية اليدوية (Mute, Kick, Ban)
# ----------------------------------------------------
@bot.event
async def on_member_update(before, after):
    # 1. مراقبة تعديل رولات عضو
    log_channel_roles = after.guild.get_channel(LOG_ROLES)
    if log_channel_roles and before.roles != after.roles:
        added_roles = [r for r in after.roles if r not in before.roles]
        removed_roles = [r for r in before.roles if r not in after.roles]

        async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
            user = entry.user
            desc = f"**العضو:** {after.mention}\n**المسؤول:** {user.mention}\n"
            if added_roles:
                desc += f"**تمت إضافة رول:** {', '.join([r.name for r in added_roles])}\n"
            if removed_roles:
                desc += f"**تمت إزالة رول:** {', '.join([r.name for r in removed_roles])}\n"

            embed = discord.Embed(
                title="🔄 تعديل رولات عضو",
                description=desc,
                color=discord.Color.gold(),
                timestamp=datetime.datetime.utcnow()
            )
            await log_channel_roles.send(embed=embed)
            break

    # 2. مراقبة الكتم اليدوي (Timeout)
    if before.timed_out_until != after.timed_out_until and after.timed_out_until is not None:
        guild = after.guild
        log_channel_mute = guild.get_channel(LOG_MUTE)
        if log_channel_mute:
            async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                if entry.target.id == after.id:
                    embed = discord.Embed(
                        title="🔇 كتم إداري لعضو",
                        description=f"**العضو المكتوم:** {after.mention}\n**المسؤول:** {entry.user.mention}\n**حتى تاريخ/وقت:** {after.timed_out_until}",
                        color=discord.Color.purple(),
                        timestamp=datetime.datetime.utcnow()
                    )
                    await log_channel_mute.send(embed=embed)
                    break

@bot.event
async def on_member_remove(member):
    guild = member.guild
    log_channel = guild.get_channel(LOG_KICK)
    if not log_channel:
        return
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
        if entry.target.id == member.id:
            embed = discord.Embed(
                title="👢 طرد عضو (Kick)",
                description=f"**العضو المطرود:** {member.mention}\n**المسؤول:** {entry.user.mention}",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            await log_channel.send(embed=embed)
            break

@bot.event
async def on_member_ban(guild, user):
    log_channel = guild.get_channel(LOG_BAN)
    if not log_channel:
        return
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        if entry.target.id == user.id:
            embed = discord.Embed(
                title="🔨 حظر عضو (Ban)",
                description=f"**العضو المحظور:** {user.mention}\n**المسؤول:** {entry.user.mention}",
                color=discord.Color.dark_red(),
                timestamp=datetime.datetime.utcnow()
            )
            await log_channel.send(embed=embed)
            break

# تشغيل البوت باستخدام متغير البيئة بأمان تام
bot.run(os.getenv("DISCORD_TOKEN"))
