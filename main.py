import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Modal, TextInput, Select
from dotenv import load_dotenv
import webserver
import os
from datetime import timedelta, datetime, timezone
import json
import re
import asyncio
import aiohttp
import io
from discord import ui, Color, SelectMenu
from constants import PERMISSION_TIERS, VOUCH_CHANNEL_ID, MOD_LOG_CHANNEL_ID, GUILD_ID, ROLE_LADDERS, VOUCH_REQUIREMENTS, VOUCH_CHECK_CHANNEL_ID, TICKET_CATEGORY_ID, STAFF_ROLE_ID, STAFF_ROLE_BY_TICKET, WELCOME_CHANNEL_ID, BOOSTER_CHANNEL_ID, BOOSTER_ROLE_ID
# ----------------------------
# Startup
# ----------------------------
load_dotenv()
token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True



# ----------------------------
# Bot
# ----------------------------
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print(f"✅ Slash commands synced to guild {GUILD_ID}")


bot = MyBot()


# ----------------------------------------------------------------_
from discord import app_commands, ui, Interaction, SelectOption, TextStyle
import discord

# -------------------------
# VOUCH PANEL LAYOUT
# -------------------------

class VouchModal(ui.Modal, title="Vouch Form"):
    def __init__(self, action: str):
        super().__init__()
        self.action = action  # "add" or "remove"

        # User select via Dropdown in Label
        dropdown = ui.Label(
            text="Select a user",
            component=ui.UserSelect(
                placeholder="Select a user",
                min_values=1,
                max_values=1
            )
        )
        self.add_item(dropdown)

        # Amount of vouches
        self.amount_input = ui.TextInput(
            label=f"Amount to {action}",
            placeholder="Enter a number",
            required=True
        )
        self.add_item(self.amount_input)

        # Reason
        self.reason_input = ui.TextInput(
            label="Reason",
            placeholder="Why are you adding/removing vouches?",
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("❌ Guild not found.", ephemeral=True)

        # Access selected member from the dropdown
        member = self.children[0].component.values[0]  # first Label's component

        # Parse amount
        try:
            amount = int(self.amount_input.value)
        except ValueError:
            return await interaction.response.send_message("❌ Amount must be a number.", ephemeral=True)

        if self.action == "remove":
            amount = -abs(amount)
        else:
            amount = abs(amount)

        reason = self.reason_input.value

        # Log in the vouch channel
        log_channel = guild.get_channel(VOUCH_CHECK_CHANNEL_ID)
        if log_channel:
            await log_channel.send(
                f"**{'Add' if amount > 0 else 'Remove'} Vouches**\n"
                f"User: {member.mention} | ID: {member.id}\n"
                f"Amount: {abs(amount)} | Reason: {reason}\n"
            )

        await interaction.response.send_message(
            f"✅ Successfully logged {abs(amount)} vouches for {member.mention}", ephemeral=True
        )



class VouchPanel(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Add Vouches", style=discord.ButtonStyle.success)
    async def add_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(VouchModal(action="add"))

    @ui.button(label="Remove Vouches", style=discord.ButtonStyle.danger)
    async def remove_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.send_modal(VouchModal(action="remove"))


# -------------------------
# SLASH COMMAND: /vouchpanel
# -------------------------

@bot.tree.command(name="vouchpanel", description="Open the vouch panel")
async def vouchpanel(interaction: Interaction):
    view = VouchPanel()
    await interaction.response.send_message("Select an action:", view=view, ephemeral=True)

# -------------------------
 # SLASH COMMAND: /vouchcheck
# -------------------------





class RankInfoPanel(ui.LayoutView):
    def __init__(self, member: discord.Member, class_name: str, current_role: discord.Role,
                 next_role: discord.Role | None, normal_vouches: int, extra_vouches: int, required_vouches: int):
        super().__init__(timeout=None)

        total_vouches = normal_vouches + extra_vouches

        # Header
        header = ui.TextDisplay(f"## Vouch Check — {member}")

        # User info
        user_info = ui.TextDisplay(
            f"**User:** {member.display_name}\n"
            f"**Class:** {class_name}\n"
            f"**Current Role:** {current_role.mention if current_role else 'None'}\n"
            f"**Vouches:** {total_vouches} "
            f"(`Normal: {normal_vouches} + Extra: {extra_vouches}`)"
        )

        # Next role info
        if next_role:
            next_info = ui.TextDisplay(
                f"**Next Role:** {next_role.mention} — requires **{required_vouches}** total vouches\n"
                f"**Vouches Needed:** {max(required_vouches - total_vouches, 0)}"
            )
        else:
            next_info = ui.TextDisplay("**Next Role:** 🎉 Max")

        separator = ui.Separator()

        container = ui.Container(
            header,
            separator,
            user_info,
            next_info,
            accent_color=None
        )

        self.add_item(container)


# --- Slash Command ---
async def count_extra_vouches(member: discord.Member):
# Vouch check
    log_channel = member.guild.get_channel(VOUCH_CHECK_CHANNEL_ID)
    if not log_channel:
        return 0

    total = 0
    async for msg in log_channel.history(limit=None):
        content = msg.content
        if str(member.id) in content or member.mention in content:
            if "**Add Vouches**" in content:
                amount = int(content.split("Amount: ")[1].split(" |")[0])
                total += amount
            elif "**Remove Vouches**" in content:
                amount = int(content.split("Amount: ")[1].split(" |")[0])
                total -= amount
    return total


@bot.tree.command(name="vouchcheck", description="Check a user's vouches and rank")
async def vouchcheck(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    guild = interaction.guild

    class_name = get_class(member)
    if class_name is None:
        return await interaction.response.send_message(
            f"❌ {member.display_name} does not have a class role assigned.",
            ephemeral=True
        )


    # Count normal vouches in VOUCH_CHANNEL_ID
    vouch_channel = guild.get_channel(VOUCH_CHANNEL_ID)
    vouches = 0
    async for msg in vouch_channel.history(limit=None):
        if member.mention in (msg.content or ""):
            vouches += 1

    # Count extra vouches from the log channel
    extra_vouches = await count_extra_vouches(member)
    total_vouches = vouches + extra_vouches

    class_name = get_class(member)
    current_index = get_current_rank_index(member, class_name)
    current_role = get_rank_role_by_index(guild, class_name, current_index)
    next_role, required_vouches, _ = get_next_rank_and_requirement(member, class_name)

    normal_vouches = vouches
    extra_vouches = await count_extra_vouches(member)

    view = RankInfoPanel(
        member,
        class_name=class_name,
        current_role=current_role,
        next_role=next_role,
        normal_vouches=normal_vouches,
        extra_vouches=extra_vouches,
        required_vouches=required_vouches if next_role else 0
    )

    await interaction.response.send_message(view=view)



# ----------------------------
# Permissions
# ----------------------------
async def check_permissions(interaction: discord.Interaction, command_name: str) -> bool:
    member = interaction.guild.get_member(interaction.user.id)
    if member is None:
        member = await interaction.guild.fetch_member(interaction.user.id)
    user_roles = [r.id for r in member.roles]
    for role_id in user_roles:
        allowed_commands = PERMISSION_TIERS.get(role_id, [])
        if command_name in allowed_commands:
            return True
    return False


async def run_command_with_permission(interaction: discord.Interaction, command_name: str, func, *args, **kwargs):
    if not await check_permissions(interaction, command_name):
        await interaction.response.send_message("❌ You are not allowed to use this command, nice try.", ephemeral=True)
        return
    await func(interaction, *args, **kwargs)



# ----------------------------
# DM help
# ----------------------------
async def safe_dm(member: discord.Member, embed: discord.Embed):
    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        pass

# ------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------
# ----------------------------
# Message-based moderation logging
# ----------------------------
MODLOG_PREFIX = "__modlog__:"  # marker prefix
SPoILER_WRAP = ("||", "||")  # invisible spoiler wrappers


def _wrap_spoiler(s: str) -> str:
    return f"{SPoILER_WRAP[0]}{s}{SPoILER_WRAP[1]}"


def _make_modlog_content(data: dict) -> str:
    # returns a content string where JSON metadata is wrapped in spoilers and prefixed.
    return _wrap_spoiler(MODLOG_PREFIX + json.dumps(data, separators=(",", ":"), ensure_ascii=False))


def _extract_modlog_from_content(content: str):
# Spoiler bullshit 1
    if not content:
        return None
    # Find the MODLOG_PREFIX anywhere in the content (inside spoilers or not)
    m = re.search(re.escape(MODLOG_PREFIX) + r'(\{.*\})', content)
    if not m:
        # maybe content is wrapped in spoilers: remove outer ||...|| then try again
        stripped = content
        if stripped.startswith("||") and stripped.endswith("||"):
            stripped = stripped[2:-2]
            m = re.search(re.escape(MODLOG_PREFIX) + r'(\{.*\})', stripped)
            if not m:
                return None
        else:
            return None
    try:
        json_part = m.group(1)
        return json.loads(json_part)
    except Exception:
        return None


async def log_action_msg(user: discord.Member, moderator: discord.Member, action: str, reason: str,
                         duration: int = None):
# Spoiler bullshit 2

    channel = user.guild.get_channel(MOD_LOG_CHANNEL_ID)
    if not channel:
        print("⚠️ Mod log channel not found.")
        return None

    now = datetime.now(timezone.utc)
    metadata = {
        "user": user.id,
        "moderator": moderator.id,
        "action": action,
        "reason": reason,
        "timestamp": int(now.timestamp()),
        "duration": duration
    }

    # Build visible embed:
    title = f"{action.title()} | {user.display_name}"
    embed = discord.Embed(title=title, description=reason,
                          color=discord.Color.red() if action in ("ban", "kick", "timeout") else discord.Color.orange(),
                          timestamp=now)
    embed.add_field(name="Moderator", value=f"{moderator} (ID: {moderator.id})", inline=True)
    embed.add_field(name="User ID", value=str(user.id), inline=True)
    if duration:
        embed.add_field(name="Duration (minutes)", value=str(duration), inline=False)

    # Send message with invisible metadata in content
    content = _make_modlog_content(metadata)
    try:
        msg = await channel.send(content=content, embed=embed)
    except Exception as e:
        print("⚠️ Failed to send modlog message:", e)
        return None

    # Update metadata with msg_id and edit content (still hidden)
    try:
        metadata["msg_id"] = msg.id
        new_content = _make_modlog_content(metadata)
        # edit embed to include message ID in footer for convenience (visible)
        embed.set_footer(text=f"Message ID: {msg.id}")
        await msg.edit(content=new_content, embed=embed)
    except Exception as e:
        print("⚠️ Failed to update modlog message:", e)
    return msg.id
#  ------------------------------------------------------------------------------------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------------------------------------------RANK UPS!
#  ------------------------------------------------------------------------------------------------------------------------------------------------------------
def get_class(member: discord.Member):
    """Return the class name for a member (if any)."""
    for name, data in ROLE_LADDERS.items():
        if discord.utils.get(member.roles, id=data["class"]):
            return name
    return None


def get_current_rank_index(member: discord.Member, class_name: str) -> int:
    """
    Return index 0..n-1 for the member's current rank within the ladder.
    Defaults to 0 (Base) if none of the rank roles are present.
    """
    ranks = ROLE_LADDERS[class_name]["ranks"]
    for i, role_id in enumerate(ranks):
        if discord.utils.get(member.roles, id=role_id):
            return i
    return 0


def get_rank_role_by_index(guild: discord.Guild, class_name: str, index: int):
    """Return the discord.Role for a rank index, or None."""
    ranks = ROLE_LADDERS[class_name]["ranks"]
    if 0 <= index < len(ranks):
        return guild.get_role(ranks[index])
    return None


def get_next_rank_and_requirement(member: discord.Member, class_name: str):
    """
    Returns (next_role: discord.Role or None, required_total_vouches: int or None, next_index: int or None)
    next_role is None if at max.
    """
    guild = member.guild
    current_index = get_current_rank_index(member, class_name)
    ranks = ROLE_LADDERS[class_name]["ranks"]
    if current_index >= len(ranks) - 1:
        return None, None, None  # already at max
    next_index = current_index + 1
    next_role = get_rank_role_by_index(guild, class_name, next_index)
    required = VOUCH_REQUIREMENTS[class_name][next_index]
    return next_role, required, next_index








#------------------------------------------------------------------------------------------------------------------------------------------------
# ------------------------------------------------------------------------------------------------------------------------------------------------------------
# ----------------------------
# Fetch logs from mod channel (no DB)
# ----------------------------
async def fetch_mod_logs(user: discord.Member, only_warns=False, lookback_limit=1000):
    channel = user.guild.get_channel(MOD_LOG_CHANNEL_ID)
    if not channel:
        return []
    logs = []
    # iterate history (newest first) — accumulate up to lookback_limit messages checked
    checked = 0
    async for msg in channel.history(limit=None):
        checked += 1
        if checked > lookback_limit:
            break
        meta = _extract_modlog_from_content(msg.content)
        if not meta:
            continue
        # filter by user
        if meta.get("user") != user.id:
            continue
        # filter warns / non-warns
        if only_warns and meta.get("action") != "warn":
            continue
        if (not only_warns) and meta.get("action") == "warn":
            continue
        # ensure msg_id present
        meta["msg_id"] = meta.get("msg_id", msg.id)
        logs.append(meta)
    # sort newest -> oldest by timestamp (some messages could be out of order)
    logs.sort(key=lambda d: d.get("timestamp", 0), reverse=True)
    return logs


# ----------------------------
# LogView (pagination) - 5 per page, newest -> oldest
# ----------------------------
class LogView(View):
    def __init__(self, entries, member, interaction):
        super().__init__(timeout=None)
        self.entries = entries
        self.member = member
        self.interaction = interaction
        self.index = 0
        self.per_page = 5
        self.max_index = max(0, (len(entries) - 1) // self.per_page)

        # create buttons and assign callbacks
        self.first_button = Button(label="⏮️ First", style=discord.ButtonStyle.gray)
        self.prev_button = Button(label="◀️ Prev", style=discord.ButtonStyle.gray)
        self.next_button = Button(label="▶️ Next", style=discord.ButtonStyle.gray)
        self.last_button = Button(label="⏭️ Last", style=discord.ButtonStyle.gray)

        for btn in (self.first_button, self.prev_button, self.next_button, self.last_button):
            self.add_item(btn)

        self.first_button.callback = self.first_page
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.last_button.callback = self.last_page

    def get_page_embed(self):
        start = self.index * self.per_page
        end = start + self.per_page
        page_entries = self.entries[start:end]
        if not page_entries:
            desc = "No entries on this page."
        else:
            parts = []
            for e in page_entries:
                ts = f"<t:{e['timestamp']}:f>" if e.get("timestamp") else "Unknown time"
                duration = f" ({e['duration']} min)" if e.get("duration") else ""
                parts.append(
                    f"**{e['action'].title()}**{duration} — Moderator: <@{e['moderator']}> — Time: {ts}\n"
                    f"Reason: {e.get('reason', 'No reason')}\nMessage ID: `{e.get('msg_id')}`"
                )
            desc = "\n\n".join(parts)
        embed = discord.Embed(title=f"Logs for {self.member.display_name}", description=desc,
                              color=discord.Color.dark_theme())
        embed.set_footer(text=f"Page {self.index + 1}/{self.max_index + 1} — {len(self.entries)} entries total")
        return embed

    async def send_initial(self):
        await self.interaction.response.send_message(embed=self.get_page_embed(), view=self, ephemeral=True)

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.get_page_embed(), view=self)

    async def first_page(self, interaction: discord.Interaction):
        self.index = 0
        await self.update_message(interaction)

    async def prev_page(self, interaction: discord.Interaction):
        self.index = max(0, self.index - 1)
        await self.update_message(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.index = min(self.max_index, self.index + 1)
        await self.update_message(interaction)

    async def last_page(self, interaction: discord.Interaction):
        self.index = self.max_index
        await self.update_message(interaction)


# ----------------------------
# Moderation coms (log via mod channel message)
# ----------------------------
@bot.tree.command(name="kick", description="Kick a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member", reason="Reason")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):

    async def func(interaction, member, reason):
        try:
            await member.kick(reason=reason)
            msg_id = await log_action_msg(member, interaction.user, "kick", reason)

            dm_embed = discord.Embed(
                title="🚨 You were kicked",
                description=(
                    f"**Server:** {interaction.guild.name}\n"
                    f"**Moderator:** {interaction.user}\n"
                    f"**Reason:** {reason}\n"
                    f"**Log ID:** `{msg_id}`"
                ),
                color=discord.Color.red()
            )

            await safe_dm(member, dm_embed)

            confirm = discord.Embed(
                title="Member Kicked",
                description=f"{member.mention} was kicked.\n**Log ID:** `{msg_id}`",
                color=discord.Color.red()
            )

            await interaction.followup.send(embed=confirm_embed, ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("❌ Cannot kick this member.", ephemeral=True)

    await run_command_with_permission(interaction, "kick", func, member, reason)

#----------------------------------------------------------------------------------------------------------
@bot.tree.command(name="ban", description="Ban a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member", reason="Reason")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):

    async def func(interaction, member, reason):
        try:

            await interaction.response.defer(ephemeral=True)


            await member.ban(reason=reason)


            msg_id = await log_action_msg(member, interaction.user, "ban", reason)





            confirm = discord.Embed(
                title="Member Banned",
                description=f"{member.mention} was banned.\n**Log ID:** `{msg_id}`",
                color=discord.Color.dark_red()
            )
            await interaction.followup.send(embed=confirm, ephemeral=True)

        except discord.Forbidden:

            await interaction.followup.send("❌ Cannot ban this member.", ephemeral=True)
        except discord.NotFound:

            print(f"❌ Interaction webhook not found for banning {member}")
        except Exception as e:
            await interaction.followup.send(f"❌ An unexpected error occurred: {e}", ephemeral=True)


    await run_command_with_permission(interaction, "ban", func, member, reason)

#-----------------------------------------------------------------------------------------------------------

@bot.tree.command(name="timeout", description="Timeout a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member", duration="In minutes", reason="Reason")
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    duration: int,
    reason: str = "No reason provided"
):
    async def func(interaction, member, duration, reason):
        try:
            # Defer the response because we might take some time
            await interaction.response.defer(ephemeral=True)

            until = discord.utils.utcnow() + timedelta(minutes=duration)
            await member.timeout(until, reason=reason)

            msg_id = await log_action_msg(member, interaction.user, "timeout", reason, duration)

            dm_embed = discord.Embed(
                title="⏱️ You were timed out",
                description=(
                    f"**Server:** {interaction.guild.name}\n"
                    f"**Duration:** {duration} minutes\n"
                    f"**Reason:** {reason}\n"
                    f"**Log ID:** `{msg_id}`\n"
                    f"**Ends:** <t:{int(until.timestamp())}:f>"
                ),
                color=discord.Color.orange()
            )
            await safe_dm(member, dm_embed)

            # Use followup.send since we deferred
            confirm = discord.Embed(
                title="Member Timed Out",
                description=(
                    f"{member.mention} timed out for **{duration} minute(s)**.\n"
                    f"**Log ID:** `{msg_id}`"
                ),
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=confirm, ephemeral=True)

        except discord.Forbidden:
            # If deferring, still need followup.send
            await interaction.followup.send("❌ Cannot timeout this member.", ephemeral=True)

    await run_command_with_permission(interaction, "timeout", func, member, duration, reason)

#-----------------------------------------------------------------------------------------------------------------------


@bot.tree.command(
    name="warn",
    description="Warn a member",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(member="Member", reason="Reason")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):

    msg_id = await log_action_msg(member, interaction.user, "warn", reason)

    dm_embed = discord.Embed(
        title="⚠️ Warning Issued",
        description=(
            f"You were warned in **{interaction.guild.name}**\n\n"
            f"**Reason:** {reason}\n"
            f"**Warn ID:** `{msg_id}`"
        ),
        color=discord.Color.orange()
    )

    await safe_dm(member, dm_embed)

    # --- Confirmation Embed (Ephemeral) ---
    confirm_embed = discord.Embed(
        title="Member Warned",
        description=(
            f"{member.mention} has been warned.\n"
            f"**Warn ID:** `{msg_id}`"
        ),
        color=discord.Color.orange()
    )

    await interaction.response.send_message(
        embed=confirm_embed,
        ephemeral=True
    )

#------------------------------------------------------------------------------------------------------------------

@bot.tree.command(name="warndelete", description="Delete a warning by Message ID", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(message_id="Message ID of the warning")
async def warndelete(interaction: discord.Interaction, message_id: str):  # <-- str here
    try:
        message_id = int(message_id)  # convert manually
    except ValueError:
        return await interaction.response.send_message("❌ Invalid message ID.", ephemeral=True)

    async def func(interaction, message_id):
        channel = interaction.guild.get_channel(MOD_LOG_CHANNEL_ID)
        if not channel:
            await interaction.response.send_message("❌ Mod log channel not found.", ephemeral=True)
            return
        try:
            msg = await channel.fetch_message(message_id)
        except discord.NotFound:
            await interaction.response.send_message(f"❌ Message ID {message_id} not found in mod log channel.",
                                                    ephemeral=True)
            return
        meta = _extract_modlog_from_content(msg.content)
        if not meta or meta.get("action") != "warn":
            await interaction.response.send_message("❌ That message is not a warn log.", ephemeral=True)
            return
        try:
            await msg.delete()
            await interaction.response.send_message(f"✅ Warning message {message_id} deleted.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to delete message: {e}", ephemeral=True)

    await run_command_with_permission(interaction, "warndelete", func, message_id)



@bot.tree.command(name="warnlog", description="Show warnings for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member")
async def warnlog(interaction: discord.Interaction, member: discord.Member):
    async def func(interaction, member):
        logs = await fetch_mod_logs(member, only_warns=True)
        if not logs:
            await interaction.response.send_message(f"ℹ️ {member.mention} has no warnings.", ephemeral=True)
            return
        view = LogView(logs, member, interaction)
        await view.send_initial()

    await run_command_with_permission(interaction, "warnlog", func, member)


@bot.tree.command(name="log", description="Show moderation logs for a user (excluding warns)",
                  guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member")
async def log(interaction: discord.Interaction, member: discord.Member):
    async def func(interaction, member):
        logs = await fetch_mod_logs(member, only_warns=False)
        if not logs:
            await interaction.response.send_message(f"ℹ️ No logs found for {member.mention}.", ephemeral=True)
            return
        view = LogView(logs, member, interaction)
        await view.send_initial()

    await run_command_with_permission(interaction, "log", func, member)

@bot.tree.command(
    name="userinfo",
    description="Show information about a member",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.describe(member="The member to get info for (leave blank for yourself)")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user

    # Join date
    joined = member.joined_at
    joined_str = f"<t:{int(joined.timestamp())}:f>" if joined else "Unknown"

    # Class info
    class_name = get_class(member) or "No class"

    # Warnings and timeouts
    warns = await fetch_mod_logs(member, only_warns=True)
    timeouts = await fetch_mod_logs(member, only_warns=False)
    timeout_count = len([t for t in timeouts if t.get("action") == "timeout"])

    # Build embed
    embed = discord.Embed(
        title=f"User Info — {member}",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Username", value=str(member), inline=True)
    embed.add_field(name="Join Date", value=joined_str, inline=True)
    embed.add_field(name="Class", value=class_name, inline=True)
    embed.add_field(name="Warns", value=str(len(warns)), inline=True)
    embed.add_field(name="Timeouts", value=str(timeout_count), inline=True)

    await interaction.response.send_message(embed=embed, ephemeral=False)


from discord.ui import View, Button, Select, Modal, TextInput
import discord
import aiohttp
import io
from datetime import datetime, timezone

# ----------------------------
# ----------------------------
# MODALS for panel command
# ----------------------------
class MessageModal(Modal, title="Send Message"):
    message = TextInput(label="Message", style=discord.TextStyle.paragraph, required=True, max_length=2000)

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.channel.send(self.message.value)
            await interaction.response.send_message("✅ Message sent!", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bot lacks permission to send messages.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


class ReplyModal(Modal, title="Reply to Message ID"):
    message_id = TextInput(label="Message ID", required=True)
    content = TextInput(label="Reply Content", style=discord.TextStyle.paragraph, required=True, max_length=2000)

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            msg_id = int(self.message_id.value.strip())
            msg = await self.channel.fetch_message(msg_id)
            await msg.reply(self.content.value)
            await interaction.response.send_message(f"✅ Replied to message `{msg_id}`", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Invalid Message ID.", ephemeral=True)
        except discord.NotFound:
            await interaction.response.send_message("❌ Message not found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


class AttachmentModal(Modal, title="Send Attachment via URL"):
    file_url = TextInput(label="File URL (http/https)", required=True)
    filename = TextInput(label="Filename to save as (optional)", required=False, placeholder="example.png")

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        url = self.file_url.value.strip()
        fname = self.filename.value.strip() or None
        if not url.lower().startswith(("http://", "https://")):
            await interaction.response.send_message("❌ URL must start with http:// or https://", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send(f"Failed to download HTTP, make sure to copy the link right. {resp.status}", ephemeral=True)
                        return
                    data = await resp.read()
            fp = io.BytesIO(data)
            if not fname:
                fname = url.split("/")[-1].split("?")[0] or "file"
            fp.seek(0)
            discord_file = discord.File(fp, filename=fname)
            await self.channel.send(file=discord_file)
            await interaction.followup.send("✅ Attachment sent!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Bot lacks permission to send attachments.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error sending attachment, (i dont know myself): {e}", ephemeral=True)


class PurgeModal(Modal, title="Purge Messages"):
    count = TextInput(label="Number of messages to purge", required=True, placeholder="e.g., 50")

    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        try:
            n = int(self.count.value.strip())
            if n < 1:
                raise ValueError
            deleted = await self.channel.purge(limit=n)
            await interaction.response.send_message(f"✅ Purged {len(deleted)} messages.", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Enter a valid number.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Bot lacks permission to purge messages.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)


# ----------------------------
# ----------------------------
# CHANNEL ACTIONS VIEW
# ----------------------------
class ChannelActions(View):
    def __init__(self, channel: discord.TextChannel, user_id: int):
        super().__init__(timeout=None)
        self.channel = channel
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only the user who opened the panel can interact
        return interaction.user.id == self.user_id

    # ---------------- Send Message ----------------
    @discord.ui.button(label="Send Message", style=discord.ButtonStyle.primary)
    async def send_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MessageModal(self.channel))

    # ---------------- Send Attachment ----------------
    @discord.ui.button(label="Send Attachment (URL)", style=discord.ButtonStyle.primary)
    async def send_attachment_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AttachmentModal(self.channel))

    # ---------------- Reply to Command ----------------
    @discord.ui.button(label="Reply to", style=discord.ButtonStyle.primary)
    async def reply_command_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        class ReplyModal(Modal, title="Reply to Command"):
            message_id = TextInput(label="Message ID", required=True)
            content = TextInput(label="Reply Content", style=discord.TextStyle.paragraph, required=True)

            def __init__(self, channel: discord.TextChannel):
                super().__init__()
                self.channel = channel

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    msg = await self.channel.fetch_message(int(self.message_id.value.strip()))
                    await msg.reply(self.content.value)
                    await interaction.response.send_message("✅ Replied successfully!", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

        await interaction.response.send_modal(ReplyModal(self.channel))

    # ---------------- Role All (Bulk) ----------------
    @discord.ui.button(label="Role All (Bulk)", style=discord.ButtonStyle.primary)
    async def role_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        class RoleAllModal(Modal, title="Assign Role to Everyone"):
            role_id = TextInput(label="Role ID to Assign", required=True)

            def __init__(self, guild: discord.Guild):
                super().__init__()
                self.guild = guild

            async def on_submit(self, interaction: discord.Interaction):
                role = self.guild.get_role(int(self.role_id.value.strip()))
                if not role:
                    return await interaction.response.send_message("❌ Invalid role ID.", ephemeral=True)
                count = 0
                for member in self.guild.members:
                    try:
                        await member.add_roles(role)
                        count += 1
                    except:
                        continue
                await interaction.response.send_message(f"✅ Assigned {role.name} to {count} members.", ephemeral=True)

        await interaction.response.send_modal(RoleAllModal(interaction.guild))

    # ---------------- Role Specific ----------------
    @discord.ui.button(label="Role Specific (2 ids)", style=discord.ButtonStyle.primary)
    async def role_specific_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        class RoleSpecificModal(Modal, title="Role Specific"):
            from_role_id = TextInput(label="From Role ID (users with this role)", required=True)
            to_role_id = TextInput(label="To Role ID (assign this role)", required=True)

            def __init__(self, guild: discord.Guild):
                super().__init__()
                self.guild = guild

            async def on_submit(self, interaction: discord.Interaction):
                from_role = self.guild.get_role(int(self.from_role_id.value.strip()))
                to_role = self.guild.get_role(int(self.to_role_id.value.strip()))
                if not from_role or not to_role:
                    return await interaction.response.send_message("❌ Invalid role IDs.", ephemeral=True)
                count = 0
                for member in self.guild.members:
                    if from_role in member.roles:
                        try:
                            await member.add_roles(to_role)
                            count += 1
                        except:
                            continue
                await interaction.response.send_message(f"✅ Assigned {to_role.name} to {count} members with {from_role.name}.", ephemeral=True)

        await interaction.response.send_modal(RoleSpecificModal(interaction.guild))


    # ---------------- Purge Messages ----------------
    @discord.ui.button(label="Purge Messages", style=discord.ButtonStyle.primary)
    async def purge_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        class PurgeModal(Modal, title="Purge Messages"):
            amount = TextInput(label="Number of messages to delete", required=True)

            def __init__(self, channel: discord.TextChannel):
                super().__init__()
                self.channel = channel

            async def on_submit(self, interaction: discord.Interaction):
                try:
                    num = int(self.amount.value.strip())
                    deleted = await self.channel.purge(limit=num)
                    await interaction.response.send_message(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

        await interaction.response.send_modal(PurgeModal(self.channel))


# ----------------------------
# CHANNEL SELECT VIEW
# ----------------------------
class ChannelSelect(Select):
    def __init__(self):
        super().__init__(placeholder="Select a text channel...", min_values=1, max_values=1, options=[])

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("❌ Invalid channel selected.", ephemeral=True)
            return
        view = ChannelActions(channel, interaction.user.id)
        await interaction.response.send_message(f"🛠 Control Panel — {channel.mention}", view=view, ephemeral=True)


class ControlPanelView(View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.add_item(ChannelSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id


# ----------------------------
# PANEL COMMAND
# ----------------------------
@bot.tree.command(name="panel", description="Open panel", guild=discord.Object(id=GUILD_ID))
async def panel(interaction: discord.Interaction):
    text_channels = [ch for ch in interaction.guild.text_channels if ch.permissions_for(interaction.user).view_channel]
    if not text_channels:
        await interaction.response.send_message("❌ No accessible text channels found.", ephemeral=True)
        return

    view = ControlPanelView(interaction.user.id)
    select: ChannelSelect = view.children[0]
    for ch in text_channels[:25]:
        select.options.append(discord.SelectOption(label=f"#{ch.name}", value=str(ch.id)))

    await interaction.response.send_message("Choose a channel", view=view, ephemeral=True)


#--------------------SYNC

@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)

    try:
        # Remove all GLOBAL commands (old ones)
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()

        # Now sync ONLY to your guild (fast updates)
        await bot.tree.sync(guild=guild)

        print(f"✔ Slash commands synced to guild {GUILD_ID}")
    except Exception as e:
        print(f"❌ Slash command sync error: {e}")

    print(f"Logged in as {bot.user}")

#--------------------------------------------------------------------
# Role panel bullshit
# -----------------------------------------------------------------------------------

# ------------------ CLOSE TICKET BUTTON ------------------

class CloseTicketRow(ui.ActionRow):
    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger)
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message(
            "🗑️ Closing ticket in 3 seconds...",
            ephemeral=True
        )
        await asyncio.sleep(3)
        await interaction.channel.delete()


# ------------------ CREATE TICKET ------------------

async def create_ticket(interaction: discord.Interaction, role_name: str):
    guild = interaction.guild
    category = guild.get_channel(TICKET_CATEGORY_ID)

    # Pick staff role based on ticket type
    staff_role_id = STAFF_ROLE_BY_TICKET.get(role_name)
    staff_role = guild.get_role(staff_role_id) if staff_role_id else None

    # ---------------- COPY CATEGORY PERMISSIONS ----------------
    # Copy the category's permissions (inherit everything)
    overwrites = dict(category.overwrites)

    # Ensure user has access
    overwrites[interaction.user] = discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        attach_files=True
    )

    # Ensure bot has access
    overwrites[guild.me] = discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True
    )

    # Add support for multiple staff roles or a single one
    staff_role_id = STAFF_ROLE_BY_TICKET.get(role_name)

    if isinstance(staff_role_id, list):
        staff_role_ids = staff_role_id
    elif isinstance(staff_role_id, int):
        staff_role_ids = [staff_role_id]
    else:
        staff_role_ids = []

    for rid in staff_role_ids:
        role = guild.get_role(rid)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )

    channel_name = f"{role_name.lower().replace(' ', '-')}-ticket-{interaction.user.name}"

    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,
        overwrites=overwrites
    )

    # Ticket UI
    title = ui.TextDisplay(f"🎫 **{role_name} Application**")
    info = ui.TextDisplay(
        f"{interaction.user.mention}\n\n"
        "Please provide the required information.\n"
        "A staff member will review your application."
    )

    accessory = ui.Button(
        label="Ticket Controls",
        style=discord.ButtonStyle.secondary,
        disabled=True
    )

    section = ui.Section(title, info, accessory=accessory)
    close_row = CloseTicketRow()

    container = ui.Container(
        section,
        close_row,
        accent_color=discord.Color.red()
    )

    view = ui.LayoutView()
    view.add_item(container)

    await channel.send(view=view)

    await interaction.response.send_message(
        f"✅ Ticket created: {channel.mention}",
        ephemeral=True
    )


# ------------------ ROLE APPLY BUTTON ------------------

class RoleApplyButton(ui.Button):
    def __init__(self, role_name: str):
        super().__init__(
            label="Apply",
            style=discord.ButtonStyle.primary
        )
        self.role_name = role_name

    async def callback(self, interaction: discord.Interaction):
        await create_ticket(interaction, self.role_name)


# ------------------ ROLE SECTION HELPER ------------------

def role_section(title: str, description: str) -> ui.Section:
    title_text = ui.TextDisplay(f"**{title}**")
    desc_text = ui.TextDisplay(description)

    return ui.Section(
        title_text,
        desc_text,
        accessory=RoleApplyButton(title)
    )


# ------------------ PANEL VIEW ------------------

class RoleTicketPanel(ui.LayoutView):
    def __init__(self):
        super().__init__()

        nigger = ui.TextDisplay("## **Other**")
        header = ui.TextDisplay("## **EWS Tickets**")
        intro = ui.TextDisplay("These are the tickets we offer.")
        separator = ui.Separator()
        spacer = ui.TextDisplay("\n")  # 1 empty line
        container = ui.Container(
            header,
            intro,
            separator,


            role_section(
                "👑 Enmity Hoster",
                "Become one of our **Enmity Hosters** that will provide Enmity Hosts.\n\n"
                "**Requirements:**\n"
                "- A **clip** parrying Enmity to show your skill.\n\n"
                "-# **PS:** A clip should be around **2–3 minutes long**."
            ),

            separator,

            role_section(
                "🔱 Titus Hoster",
                "Become one of our **Titus Hosters** that will provide Titus Hosts.\n\n"
                "**Requirements:**\n"
                "- A **clip** of being able to solo titus to show your skill.\n\n"

            ),

            separator,


            role_section(
                "⚔️ Depths Force",
                "Become one of our **Depths Forces** to help protect Enmities.\n\n"
                "**Requirements:**\n"
                "- A tryout by one of our **Force Tryouters**.\n\n"


            ),

            separator,



            role_section(
                "❤️ Support | 🛡️ Parry",
                "Become one of our **Supports** or **Parriers** who will provide help to Hosters.\n\n"
                "**Requirements:**\n"
                "- A vouch from a Hoster saying you're fit for Parry/Support\n\n"
                " "
            ),


            separator,
            nigger,

            role_section(
                "Complaints | Roles",
                "Got a complaint for us about a warn or server problem? Or you want to rank up your role?\n\n"
            ),





            accent_color=None
        )

        self.add_item(container)


# ------------------ SLASH COMMAND ------------------

@bot.tree.command(name="roletickets", description="Show role ticket panel")
@app_commands.checks.has_permissions(administrator=True)
async def roletickets(interaction: discord.Interaction):
    await interaction.response.send_message(view=RoleTicketPanel())

#---------------------------------------------------------------------------------------------------------------------------------------------# \# Helper function: returns a list of items for LayoutView\class WelcomePanel(ui.LayoutView):


# --- Welcome Panel using LayoutView ---
class WelcomePanel(ui.LayoutView):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)

        # Header with mention
        header = ui.TextDisplay(f"## Welcome to EWS, {member.mention}!")

        # User info
        user_info = ui.TextDisplay(
            f"**Joined At:** {member.joined_at.strftime('%Y-%m-%d %H:%M:%S') if member.joined_at else 'Unknown'}\n\n"
        )

        # Rules section
        rules_section = ui.TextDisplay(
            f"**Rules:** Please read our server rules in <#{rules_channel_id}>\n\n"
        )


        # Welcome note
        welcome_note = ui.TextDisplay(
            "We're glad to have you here! Make sure to check the rules and enjoy your stay."
        )

        # Visual separator
        separator = ui.Separator()

        # Container groups all text displays
        container = ui.Container(
            header,
            separator,
            user_info,
            rules_section,
            welcome_note,
            accent_color=None
        )

        # Add container to the layout
        self.add_item(container)


# --- Event: Member Join ---
@bot.event
async def on_member_join(member: discord.Member):
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return

    view = WelcomePanel(member)

    # ❌ Do NOT use content= here; include mention inside TextDisplay
    await channel.send(
        view=view
    )


rules_channel_id = 1362884136460616023

#------------------------------------------------------------------
class BoosterPanel(ui.LayoutView):
    def __init__(self, member: discord.Member):
        super().__init__(timeout=None)

        # --- Header ---
        header = ui.TextDisplay(f"## Thank you for boosting, {member.mention}!")

        # --- Separator ---
        separator1 = ui.Separator()






        perks_section = ui.TextDisplay(
            "**Booster Perks:**\n"
            "- Colored Booster Role\n"
            "- Img Perms\n"
            "- Able To Skip Waiting Room\n\n"
            "We appreciate your support! - The EWS Mod Team."
        )


        container = ui.Container(
            header,
            separator1,
            separator2,
            perks_section,
            accent_color=None
        )

        self.add_item(container)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    # Check if member just became a booster
    if not before.premium_since and after.premium_since:
        channel = after.guild.get_channel(BOOSTER_CHANNEL_ID)  # Booster/announcement channel
        if not channel:
            return

        view = BoosterPanel(after)
        await channel.send(view=view)



# ----------------------------
# Run the bot
# ----------------------------
webserver.keep_alive()
bot.run(token)
