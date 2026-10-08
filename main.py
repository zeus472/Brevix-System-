import discord
from discord.ext import commands
import datetime
import random
import os

intents = discord.Intents.default()
intents.members = True
intents.messages = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --- الـ IDs المطلوبة بدقة ---
# فئات التذاكر
CAT_STORE = 1557847161645961226
CAT_COMPLAINTS = 1557846007226830929
CAT_INQUIRIES = 1557846392565670040

# رومات لوج اللوحات الخاصة بالتحكم
LOG_STORE_PANEL = 1557856431615774820
LOG_INQUIRY_PANEL = 1557856512720769024
LOG_COMPLAINT_PANEL = 1557856586251112610

# روم الاقتراحات
SUGGESTIONS_CHANNEL = 1557855702473769050

# روم التقرير الشامل للإغلاق
LOG_CLOSE_REPORT = 1557690531541159957

# رولات الإداريين لكل قسم
ROLES_STORE = [1557686249693782036, 1549802988498063524]
ROLES_COMPLAINT = [1549802988498063524, 1549803238084051055, 1549804378586882058]
ROLES_INQUIRY = [1549804378586882058, 1549806844112011384]

# رول تحويل التذاكر العامة
ROLE_TRANSFER_TARGET = 1557736356762091540

# تخزين مؤقت لبيانات التذاكر النشطة
active_tickets = {}

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح باسم: {bot.user.name}")
    print("بوت التذاكر جاهز للعمل بكامل الكفاءة!")


# ==========================================
# 1. نافذة إدخال بيانات التذاكر والاقتراحات
# ==========================================
class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_type):
        super().setTitle("قسم التذاكر والدعم الفني")
        self.ticket_type = ticket_type

        self.name_input = discord.ui.TextInput(
            label="اسمك",
            placeholder="اكتب اسمك هنا...",
            required=True,
            max_length=100
        )
        self.add_item(self.name_input)

        if ticket_type == "المتجر":
            label_text = "سبب إنشاء التذكرة"
        elif ticket_type == "شكوي":
            label_text = "تفاصيل الشكوى"
        elif ticket_type == "إستفسار":
            label_text = "تفاصيل الاستفسار"
        else:
            label_text = "التفاصيل"

        self.detail_input = discord.ui.TextInput(
            label=label_text,
            style=discord.TextStyle.paragraph,
            placeholder="اكتب التفاصيل هنا...",
            required=True,
            max_length=1000
        )
        self.add_item(self.detail_input)

    async def on_submit(self, interaction: discord.Interaction):
        # الرد الفوري لمنع مهلة الـ 3 ثواني من ديسكورد
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user
        now = datetime.datetime.utcnow()

        user_name = self.name_input.value
        user_details = self.detail_input.value
        ticket_id = str(random.randint(100000, 999999))

        # أ. التعامل مع قسم الاقتراحات (بدون فتح روم)
        if self.ticket_type == "إقتراح":
            sug_channel = guild.get_channel(SUGGESTIONS_CHANNEL)
            if sug_channel:
                embed = discord.Embed(
                    title="💡 إقتراح جديد",
                    description=f"**مقدم الإقتراح:** {user.mention}\n\n**العنوان:** {user_name}\n**الشرح والتفاصيل:**\n{user_details}",
                    color=discord.Color.gold(),
                    timestamp=now
                )
                await sug_channel.send(embed=embed)
            
            # إرسال رسالة في الخاص للاعب
            try:
                await user.send(f"نشكرك {user.mention} علي تقديم إقتراحك وسعيك المستمر في نجاح السيرفر 👑")
            except:
                pass

            await interaction.followup.send("✅ تم إرسال اقتراحك بنجاح، شكراً لك!", ephemeral=True)
            return

        # ب. تحديد الفئة ورولات الإداريين حسب نوع التذكرة
        if self.ticket_type == "المتجر":
            category_id = CAT_STORE
            panel_log_id = LOG_STORE_PANEL
            roles_list = ROLES_STORE
        elif self.ticket_type == "شكوي":
            category_id = CAT_COMPLAINTS
            panel_log_id = LOG_COMPLAINT_PANEL
            roles_list = ROLES_COMPLAINT
        else: # إستفسار
            category_id = CAT_INQUIRIES
            panel_log_id = LOG_INQUIRY_PANEL
            roles_list = ROLES_INQUIRY

        category = guild.get_channel(category_id)
        
        # صلاحيات الروم الجديدة
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        for r_id in roles_list:
            role = guild.get_role(r_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # إنشاء روم التيكت باسم الرقم العشوائي
        ticket_channel = await guild.create_text_channel(
            name=f"ticket-{ticket_id}",
            category=category,
            overwrites=overwrites
        )

        # تنسيق منشن الجهات المختصة تحت بعضها
        mentions_str = "\n".join([f"<@&{r_id}>" for r_id in roles_list])

        # رسالة داخل روم التيكت
        embed_ticket = discord.Embed(
            title="🎟️ تذكرة جديدة",
            description=f"قام {user.mention} بإنشاء تذكرة للتو!\n\n"
                        f"**التفاصيل المقدمة:**\n{user_details}\n**الاسم:** {user_name}\n\n"
                        f"**رقم التذكرة:** `{ticket_id}`\n"
                        f"**وقت وتاريخ الإنشاء:** {now.strftime('%Y-%m-%d | %H:%M:%S')}\n\n"
                        f"**الجهات المختصة:**\n{mentions_str}",
            color=discord.Color.blue(),
            timestamp=now
        )
        await ticket_channel.send(embed=embed_ticket)

        # حفظ بيانات التذكرة في الذاكرة المؤقتة
        active_tickets[ticket_channel.id] = {
            "ticket_id": ticket_id,
            "user_id": user.id,
            "ticket_type": self.ticket_type,
            "user_name": user_name,
            "user_details": user_details,
            "created_at": now.strftime('%Y-%m-%d | %H:%M:%S'),
            "claimed_by": None,
            "claimed_at": None,
            "transferred_to": None,
            "roles_list": roles_list
        }

        # إرسال لوحة التحكم المستقلة في الروم المخصصة لها
        panel_log_channel = guild.get_channel(panel_log_id)
        if panel_log_channel:
            embed_panel = discord.Embed(
                title=f"🎛️ لوحة تحكم تذكرة: {ticket_id}",
                description=f"**اللاعب:** {user.mention}\n**نوع التذكرة:** {self.ticket_type}\n**رقم التذكرة:** `{ticket_id}`",
                color=discord.Color.dark_theme(),
                timestamp=now
            )
            view = TicketControlView()
            panel_msg = await panel_log_channel.send(embed=embed_panel, view=view)
            active_tickets[ticket_channel.id]["panel_msg_id"] = panel_msg.id
            active_tickets[ticket_channel.id]["panel_channel_id"] = panel_log_channel.id

        await interaction.followup.send(f"✅ تم فتح تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)


# ==========================================
# 2. القائمة المنسدلة للواجهة الأساسية
# ==========================================
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="المتجر", description="لشراء الخدمات والمنتجات", emoji="🛍"),
            discord.SelectOption(label="شكوي", description="تقديم شكوى ضد لاعب أو إداري", emoji="📕"),
            discord.SelectOption(label="إستفسار", description="طرح الأسئلة والاستفسارات العامة", emoji="📘"),
            discord.SelectOption(label="إقتراح", description="تقديم اقتراحات لتطوير السيرفر", emoji="💡")
        ]
        super().__init__(placeholder="يرجى اختيار الموضوع المناسب", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketModal(self.values[0]))

class TicketSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ==========================================
# 3. قائمة اختيار الإداري عند التحويل
# ==========================================
class AdminSelect(discord.ui.Select):
    def __init__(self, guild):
        role = guild.get_role(ROLE_TRANSFER_TARGET)
        options = []
        if role:
            for member in role.members[:25]: 
                options.append(discord.SelectOption(label=member.display_name, value=str(member.id)))
        
        if not options:
            options.append(discord.SelectOption(label="لا يوجد إداريين متاحين", value="none"))

        super().__init__(placeholder="اختر الإداري المراد تحويل التذكرة إليه", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.send_message("❌ لا يوجد إداريين متاحين في هذه الرول حالياً.", ephemeral=True)
            return

        admin_id = int(self.values[0])
        guild = interaction.guild
        admin_member = guild.get_member(admin_id)
        
        ticket_data = active_tickets.get(interaction.channel.id)
        if ticket_data:
            ticket_data["transferred_to"] = admin_member.mention
            await interaction.channel.send(f"تم تحويل تذكرتك للإداري {admin_member.mention}")
            await interaction.response.send_message(f"✅ تم تحويل التذكرة بنجاح إلى {admin_member.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ حدث خطأ، لم يتم العثور على بيانات هذه التذكرة.", ephemeral=True)

class AdminSelectView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=60)
        self.add_item(AdminSelect(guild))


# ==========================================
# 4. نموذج سبب إغلاق التذكرة
# ==========================================
class CloseReasonModal(discord.ui.Modal):
    def __init__(self, ticket_channel, panel_message, ticket_data):
        super().setTitle("إغلاق التذكرة")
        self.ticket_channel = ticket_channel
        self.panel_message = panel_message
        self.ticket_data = ticket_data

        self.reason_input = discord.ui.TextInput(
            label="ملخص الشكوى أو سبب الغلق",
            style=discord.TextStyle.paragraph,
            placeholder="اكتب ملخص ما حدث أو سبب إغلاق التذكرة...",
            required=True,
            max_length=1000
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        close_summary = self.reason_input.value
        guild = interaction.guild
        now = datetime.datetime.utcnow()

        t_data = self.ticket_data
        opener = guild.get_member(t_data["user_id"])

        # 1. إرسال التقرير الشامل لروم لوج الإدارة
        report_channel = guild.get_channel(LOG_CLOSE_REPORT)
        if report_channel:
            embed_report = discord.Embed(
                title="📋 تقرير إغلاق تذكرة شامل",
                description=f"**صاحب التذكرة:** {opener.mention if opener else 'مستخدم مغادر'}\n"
                            f"**رقم التذكرة:** `{t_data['ticket_id']}`\n"
                            f"**نوع التذكرة:** {t_data['ticket_type']}\n"
                            f"**وقت وتاريخ الإنشاء:** {t_data['created_at']}\n"
                            f"**وقت وتاريخ الاستلام:** {t_data['claimed_at'] or 'لم يتم الاستلام'}\n"
                            f"**المسؤول (المستلم):** {t_data['claimed_by'] or 'لا يوجد'}\n"
                            f"**المسؤول (المحول إليه):** {t_data['transferred_to'] or 'لم يتم التحويل'}\n\n"
                            f"**تفاصيل اللاعب الأساسية:**\n{t_data['user_details']}\n\n"
                            f"**ملخص الإغلاق / الشكوى:**\n{close_summary}",
                color=discord.Color.red(),
                timestamp=now
            )
            await report_channel.send(embed=embed_report)

        # 2. إرسال التقرير الخاص للاعب في الخاص
        if opener:
            try:
                embed_dm = discord.Embed(
                    title="🔒 تم إغلاق تذكرتك",
                    description=f"**منشئ التذكرة:** {opener.mention}\n"
                                f"**نوع التذكرة:** {t_data['ticket_type']}\n"
                                f"**رقم التذكرة:** `{t_data['ticket_id']}`\n"
                                f"**الإداري المسؤول:** {t_data['claimed_by'] or 'فريق الإدارة'}\n\n"
                                f"**ملخص الشكوى / الختام:**\n{close_summary}",
                    color=discord.Color.purple(),
                    timestamp=now
                )
                await opener.send(embed=embed_dm)
            except:
                pass

        # حذف رسالة لوحة التحكم والتهيئة
        if self.panel_message:
            try:
                await self.panel_message.delete()
            except:
                pass

        # حذف روم التذكرة
        if self.ticket_channel in active_tickets:
            del active_tickets[self.ticket_channel.id]

        await interaction.response.send_message("🔒 جاري إغلاق الحذف وحذف الروم...", ephemeral=True)
        await self.ticket_channel.delete()


# ==========================================
# 5. أزرار التحكم في اللوحة (استلام، تحويل، غلق)
# ==========================================
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="استلام", style=discord.ButtonStyle.green, emoji="📥", custom_id="claim_ticket_btn")
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = None
        for cid, data in active_tickets.items():
            if data.get("panel_msg_id") == interaction.message.id:
                channel_id = cid
                break

        if not channel_id:
            await interaction.response.send_message("❌ عذراً، لم يتم العثور على روم هذه التذكرة.", ephemeral=True)
            return

        ticket_channel = interaction.guild.get_channel(channel_id)
        now_str = datetime.datetime.utcnow().strftime('%Y-%m-%d | %H:%M:%S')

        active_tickets[channel_id]["claimed_by"] = interaction.user.mention
        active_tickets[channel_id]["claimed_at"] = now_str

        if ticket_channel:
            await ticket_channel.send(f"قام الإداري {interaction.user.mention} بإستلام تذكرتك الآن")

        await interaction.response.send_message(f"✅ تم استلام التذكرة بنجاح بواسطة {interaction.user.mention}", ephemeral=True)

    @discord.ui.button(label="تحويل", style=discord.ButtonStyle.blurple, emoji="🔄", custom_id="transfer_ticket_btn")
    async def transfer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = None
        for cid, data in active_tickets.items():
            if data.get("panel_msg_id") == interaction.message.id:
                channel_id = cid
                break

        if not channel_id:
            await interaction.response.send_message("❌ عذراً، لم يتم العثور على روم هذه التذكرة.", ephemeral=True)
            return

        view = AdminSelectView(interaction.guild)
        await interaction.response.send_message("اختر الإداري للتحويل:", view=view, ephemeral=True)

    @discord.ui.button(label="غلق", style=discord.ButtonStyle.red, emoji="🔒", custom_id="close_ticket_btn")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_id = None
        for cid, data in active_tickets.items():
            if data.get("panel_msg_id") == interaction.message.id:
                channel_id = cid
                break

        if not channel_id:
            await interaction.response.send_message("❌ عذراً، هذه التذكرة غير مسجلة أو مغلقة مسبقاً.", ephemeral=True)
            return

        ticket_channel = interaction.guild.get_channel(channel_id)
        ticket_data = active_tickets[channel_id]

        await interaction.response.send_modal(CloseReasonModal(ticket_channel, interaction.message, ticket_data))


# ==========================================
# 6. أمر إعداد اللوحة الأساسية
# ==========================================
@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup_panel(ctx):
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="**قسم التذاكر والدعم الفني**",
        description="مرحباً بك في قسم التذاكر والدعم الفني يرجي اختيار الموضوع المناسب لنساعدك في اقرب وقت ممكن",
        color=discord.Color.from_rgb(30, 30, 30)
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1557691888012632094/1557692056434905108/1791452190631.jpg?ex=6ac8b946&is=6ac767c6&hm=d42158f136fa773b6dc4874f1e1dd0fbabfa145f665af2791ef03311abcd93e5&")
    
    view = TicketSelectView()
    await ctx.send(embed=embed, view=view)


# تشغيل البوت بأمان باستخدام المتغير البيئي
bot.run(os.getenv("DISCORD_TOKEN"))
