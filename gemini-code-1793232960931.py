import asyncio
import datetime
import sqlite3
from threading import Thread
from flask import Flask
import discord
from discord.ext import commands
from discord.ui import Button, Select, View

# --- 🌐 خادم الحفاظ على نشاط البوت 24/7 ---
app = Flask("")


@app.route("/")
def home():
    return "🎫 بوت التكتات العميق الشامل شغال 24/7!"


def run():
    app.run(host="0.0.0.0", port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()


# --- 🤖 إعدادات البوت وقاعدة البيانات ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

RED_COLOR = 0x8B0000  # أحمر داكن عناب
EMBED_FOOTER = "⚙️ نظام التكتات الاحترافي الشامل | Advanced Ticket System"

SUPPORT_ROLE_NAME = "Support Team"
LOG_CHANNEL_NAME = "ticket-logs"
RATING_LOG_NAME = "rating-logs"

# قاعدة بيانات لحفظ المحظورين من التكتات
conn = sqlite3.connect("tickets_database.db")
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS blacklist (
    user_id INTEGER PRIMARY KEY
)
""")
conn.commit()


def is_blacklisted(user_id):
    cursor.execute("SELECT user_id FROM blacklist WHERE user_id = ?", (user_id,))
    return cursor.fetchone() is not None


# --- 1️⃣ نظام التقييم (1 إلى 5 نجوم) ---
class RatingView(View):

    def __init__(self, staff_member=None):
        super().__init__(timeout=180)
        self.staff_member = staff_member

    async def send_rating(self, interaction: discord.Interaction, stars: int):
        await interaction.response.send_message(
            f"شُكراً لتقييمك! تم تسجيل ({stars}⭐) بنجاح.", ephemeral=True
        )

        guild = interaction.guild
        rating_log = discord.utils.get(
            guild.text_channels, name=RATING_LOG_NAME
        )
        if rating_log:
            embed = discord.Embed(
                title="⭐ تقييم خدمة جديد",
                description=(
                    f"**المقيّم:** {interaction.user.mention}\n"
                    f"**التقييم:** {'⭐' * stars} ({stars}/5)\n"
                    f"**المسؤول عن التكت:** {self.staff_member.mention if self.staff_member else 'غير محدد'}"
                ),
                color=RED_COLOR,
                timestamp=datetime.datetime.now(),
            )
            embed.set_footer(text=EMBED_FOOTER)
            await rating_log.send(embed=embed)

    @discord.ui.button(label="1⭐", style=discord.ButtonStyle.secondary)
    async def star1(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 1)

    @discord.ui.button(label="2⭐", style=discord.ButtonStyle.secondary)
    async def star2(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 2)

    @discord.ui.button(label="3⭐", style=discord.ButtonStyle.secondary)
    async def star3(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 3)

    @discord.ui.button(label="4⭐", style=discord.ButtonStyle.secondary)
    async def star4(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 4)

    @discord.ui.button(label="5⭐", style=discord.ButtonStyle.success)
    async def star5(self, interaction: discord.Interaction, button: Button):
        await self.send_rating(interaction, 5)


# --- 2️⃣ واجهة اختيار قسم التكت ---
class TicketSelect(Select):

    def __init__(self):
        options = [
            discord.SelectOption(
                label="دعم فني عام",
                description="استفسارات ومشاكل عامة داخل السيرفر",
                emoji="🛠️",
                value="دعم فني",
            ),
            discord.SelectOption(
                label="تقديم على رتبة",
                description="طلب الانضمام لفرق العمل والرتب",
                emoji="👑",
                value="تقديم رتبة",
            ),
            discord.SelectOption(
                label="بلاغ عن عضو",
                description="تقديم شكوى على مخالفات المشتركين",
                emoji="🚨",
                value="بلاغ",
            ),
            discord.SelectOption(
                label="استفسار مالي وخاص",
                description="استفسارات المتجر والبنوك",
                emoji="💳",
                value="استفسار مالي",
            ),
        ]
        super().__init__(
            placeholder="اختر قسم التكت المطلوب...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        # فحص الحظر من التكتات
        if is_blacklisted(user.id):
            return await interaction.response.send_message(
                "❌ أنت محظور من استخدام نظام التكتات في هذا السيرفر!",
                ephemeral=True,
            )

        category = discord.utils.get(guild.categories, name="TICKETS")
        if not category:
            category = await guild.create_category("TICKETS")

        channel_name = f"ticket-{user.name}".lower()
        if discord.utils.get(category.channels, name=channel_name):
            return await interaction.response.send_message(
                "❌ لديك تكت مفتوح بالفعل! لا يمكنك فتح أكثر من تكت في نفس الوقت.",
                ephemeral=True,
            )

        support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE_NAME)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            ),
            user: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True
            ),
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            )

        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"صاحب التكت: {user.display_name} ({user.id}) | القسم: {self.values[0]}",
        )

        embed = discord.Embed(
            title=f"🎫 تكت {self.values[0]} جديد",
            description=(
                f"مرحباً بك {user.mention}!\n\n"
                f"📌 **القسم:** {self.values[0]}\n"
                f"اكتب استفسارك بالتفصيل وسيقوم أحد المسؤولين بالرد عليك قريباً.\n\n"
                f"⚠️ *ملاحظة:* اضغط على **استلام التكت (Claim)** من قبل الإدارة لمباشرة الطلب."
            ),
            color=RED_COLOR,
        )
        embed.set_footer(text=EMBED_FOOTER)

        ping_msg = (
            f"{user.mention} | {support_role.mention if support_role else ''}"
        )
        await ticket_channel.send(
            content=ping_msg, embed=embed, view=TicketControlView()
        )
        await interaction.response.send_message(
            f"✅ تم إنشاء التكت: {ticket_channel.mention}", ephemeral=True
        )

        log_channel = discord.utils.get(
            guild.text_channels, name=LOG_CHANNEL_NAME
        )
        if log_channel:
            log_embed = discord.Embed(
                title="📥 تم فتح تكت جديد",
                description=f"**صاحب التكت:** {user.mention}\n**القناة:** {ticket_channel.mention}\n**القسم:** {self.values[0]}",
                color=RED_COLOR,
                timestamp=datetime.datetime.now(),
            )
            await log_channel.send(embed=log_embed)


class TicketLaunchView(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# --- 3️⃣ أزرار التحكم والتأكيد والحذف ---
class TicketControlView(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.claimed_by = None

    @discord.ui.button(
        label="استلام التكت",
        style=discord.ButtonStyle.primary,
        emoji="🙋‍♂️",
        custom_id="claim_ticket",
    )
    async def claim_ticket(
        self, interaction: discord.Interaction, button: Button
    ):
        support_role = discord.utils.get(
            interaction.guild.roles, name=SUPPORT_ROLE_NAME
        )
        if (
            support_role not in interaction.user.roles
            and not interaction.user.guild_permissions.administrator
        ):
            return await interaction.response.send_message(
                "❌ هذا الزر مخصص لفريق الدعم الفني فقط!", ephemeral=True
            )

        if self.claimed_by:
            return await interaction.response.send_message(
                f"❌ التكت مستلم بالفعل بواسطة: {self.claimed_by.mention}",
                ephemeral=True,
            )

        self.claimed_by = interaction.user
        button.disabled = True
        button.label = f"مستلم بواسطة {interaction.user.display_name}"
        await interaction.message.edit(view=self)

        await interaction.channel.edit(
            topic=f"{interaction.channel.topic} | المستلم: {interaction.user.display_name}"
        )

        embed = discord.Embed(
            description=f"🙋‍♂️ قام {interaction.user.mention} باستلام هذا التكت وسيقوم بمساعدتك الآن.",
            color=RED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(
        label="إغلاق التكت",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket",
    )
    async def close_ticket(
        self, interaction: discord.Interaction, button: Button
    ):
        channel = interaction.channel
        overwrites = channel.overwrites
        for target in overwrites:
            if isinstance(target, discord.Member):
                overwrites[target].send_messages = False
        await channel.edit(overwrites=overwrites)

        embed = discord.Embed(
            title="🔒 تم إغلاق التكت",
            description="تم سحب صلاحيات الكتابة. اضغط زر التأكيد بالأسفل لحذف التكت نهائياً وتأكيده.",
            color=RED_COLOR,
        )
        await interaction.response.send_message(
            embed=embed, view=TicketClosedView(claimed_by=self.claimed_by)
        )


class ConfirmDeleteView(View):

    def __init__(self, claimed_by=None):
        super().__init__(timeout=60)
        self.claimed_by = claimed_by

    @discord.ui.button(
        label="تأكيد الحذف النهائي",
        style=discord.ButtonStyle.danger,
        emoji="⚠️",
    )
    async def confirm_delete(
        self, interaction: discord.Interaction, button: Button
    ):
        channel = interaction.channel
        guild = interaction.guild

        # حفظ وترحيل اللوجات والتسجيلات تلقائياً قبل المسح
        messages = [
            m
            async for m in channel.history(limit=500, oldest_first=True)
        ]
        text = f"=== سجل المحادثة للتكت: {channel.name} ===\n\n"
        for msg in messages:
            text += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author}: {msg.content}\n"

        filename = f"{channel.name}-transcript.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(text)

        log_channel = discord.utils.get(
            guild.text_channels, name=LOG_CHANNEL_NAME
        )
        if log_channel:
            log_embed = discord.Embed(
                title="🗑️ تم حذف تكت",
                description=f"**القناة:** `{channel.name}`\n**المسؤول:** {self.claimed_by.mention if self.claimed_by else 'غير محدد'}",
                color=RED_COLOR,
                timestamp=datetime.datetime.now(),
            )
            await log_channel.send(
                embed=log_embed, file=discord.File(filename)
            )

        # طلب التقييم من صاحب التكت
        for member in channel.members:
            if (
                not member.bot
                and not member.guild_permissions.administrator
            ):
                try:
                    embed = discord.Embed(
                        title="⭐ كيف كانت تجربتك مع الدعم الفني؟",
                        description="يرجى اختيار تقييم للخدمة التي تلقيتها بالضغط على أحد الأزرار أدناه:",
                        color=RED_COLOR,
                    )
                    await member.send(
                        embed=embed, view=RatingView(staff_member=self.claimed_by)
                    )
                except Exception:
                    pass

        await interaction.response.send_message(
            "🛑 جاري مسح القناة نهائياً خلال 3 ثوانٍ..."
        )
        await asyncio.sleep(3)
        await channel.delete()


class TicketClosedView(View):

    def __init__(self, claimed_by=None):
        super().__init__(timeout=None)
        self.claimed_by = claimed_by

    @discord.ui.button(
        label="حذف التكت النهائي",
        style=discord.ButtonStyle.danger,
        emoji="⛔",
        custom_id="delete_ticket",
    )
    async def delete_ticket(
        self, interaction: discord.Interaction, button: Button
    ):
        embed = discord.Embed(
            title="⚠️ هل أنت تأكد من رغبتك في حذف التكت نهائياً؟",
            description="سيتم إغلاق القناة ومسحها وإرسال السجل لروم اللوجات.",
            color=RED_COLOR,
        )
        await interaction.response.send_message(
            embed=embed,
            view=ConfirmDeleteView(claimed_by=self.claimed_by),
            ephemeral=True,
        )


# --- 4️⃣ أوامر إدارة التكتات المتقدمة ---


# أمر إضافة عضو
@bot.command(name="اضافة", aliases=["add"])
async def add_member(ctx, member: discord.Member):
    if "ticket-" in ctx.channel.name:
        await ctx.channel.set_permissions(
            member, read_messages=True, send_messages=True, attach_files=True
        )
        await ctx.send(
            embed=discord.Embed(
                description=f"✅ تم إضافة {member.mention} للتكت.", color=RED_COLOR
            )
        )


# أمر طرد عضو
@bot.command(name="طرد", aliases=["remove"])
async def remove_member(ctx, member: discord.Member):
    if "ticket-" in ctx.channel.name:
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(
            embed=discord.Embed(
                description=f"❌ تم إزالة {member.mention} من التكت.",
                color=RED_COLOR,
            )
        )


# أمر تغيير اسم التكت
@bot.command(name="تسمية", aliases=["rename"])
async def rename_ticket(ctx, *, new_name: str):
    if "ticket-" in ctx.channel.name:
        await ctx.channel.edit(name=f"ticket-{new_name}")
        await ctx.send(
            embed=discord.Embed(
                description=f"⚙️ تم تغيير اسم القناة إلى: `ticket-{new_name}`",
                color=RED_COLOR,
            )
        )


# أمر إضافة ملاحظة مخفية للإدارة
@bot.command(name="ملاحظة", aliases=["note"])
async def admin_note(ctx, *, note_text: str):
    await ctx.message.delete()
    embed = discord.Embed(
        title="📝 ملاحظة إدارية مخفية",
        description=f"**الكاتب:** {ctx.author.mention}\n**الملاحظة:** {note_text}",
        color=RED_COLOR,
    )
    await ctx.send(embed=embed)


# أمر حظر عضو من فتح التكتات
@bot.command(name="حظر_تكت")
@commands.has_permissions(administrator=True)
async def block_user(ctx, member: discord.Member):
    cursor.execute(
        "INSERT OR REPLACE INTO blacklist (user_id) VALUES (?)", (member.id,)
    )
    conn.commit()
    await ctx.send(
        embed=discord.Embed(
            description=f"🚫 تم حظر {member.mention} من فتح التكتات بنجاح.",
            color=RED_COLOR,
        )
    )


# أمر فك الحظر
@bot.command(name="فك_حظر_تكت")
@commands.has_permissions(administrator=True)
async def unblock_user(ctx, member: discord.Member):
    cursor.execute("DELETE FROM blacklist WHERE user_id = ?", (member.id,))
    conn.commit()
    await ctx.send(
        embed=discord.Embed(
            description=f"✅ تم فك حظر التكتات عن {member.mention}.", color=RED_COLOR
        )
    )


# أمر تنبيه عدم الرد
@bot.command(name="تنبيه_الرد", aliases=["remind"])
async def remind_user(ctx, member: discord.Member):
    embed = discord.Embed(
        title="🔔 تنبيه عدم الرد",
        description=f"مرحباً {member.mention}، يرجى الرد على استفسارات فريق الدعم الفني لإكمال تكتك أو سيتم إغلاقه.",
        color=RED_COLOR,
    )
    await ctx.send(content=member.mention, embed=embed)


# --- 5️⃣ أمر إنشاء اللوحة الرئيسية ---
@bot.command(name="تكت_لوحة", aliases=["setup_tickets"])
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    await ctx.message.delete()

    embed = discord.Embed(
        title="🔻 مركز الدعم الفني والتكتات | Support Center",
        description=(
            "أهلاً بكم في مركز الخدمة والمساعدة.\n\n"
            "📌 **خطوات فتح تكت:**\n"
            "اختر القسم المناسب لمشكلتك من القائمة المنسدلة بالأسفل، وسيتم إنشاء قناة خاصة للرد عليك من قِبل طاقم الدعم الفني.\n\n"
            "⚠️ *الرجاء عدم فتح تكت بدون سبب لعدم التعرض للمخالفات.*"
        ),
        color=RED_COLOR,
    )
    embed.set_footer(text=EMBED_FOOTER)

    await ctx.send(embed=embed, view=TicketLaunchView())


# --- 🚀 تشغيل البوت والـ Keep Alive ---
keep_alive()
bot.run("YOUR_BOT_TOKEN_HERE")