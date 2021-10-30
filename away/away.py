import discord
from redbot.core import Config, commands, checks
from typing import Optional, Literal
import datetime
import re

IMAGE_LINKS = re.compile(r"(http[s]?:\/\/[^\"\']*\.(?:png|jpg|jpeg|gif|png))")


class Away(commands.Cog):
    """Le away cog"""

    default_global_settings = {"ign_servers": []}
    default_guild_settings = {"TEXT_ONLY": False, "BLACKLISTED_MEMBERS": []}
    default_away_settings = {"MESSAGE": None}

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 8423491260, force_registration=True)
        self.config.register_global(**self.default_global_settings)
        self.config.register_guild(**self.default_guild_settings)
        self.config.init_custom("AwayGroup", 1)
        self.config.register_custom("AwayGroup", **self.default_away_settings)

    def _draw_play(self, song):
        song_start_time = song.start
        total_time = song.duration
        current_time = datetime.datetime.utcnow()
        elapsed_time = current_time - song_start_time
        sections = 12
        loc_time = round((elapsed_time / total_time) * sections)  # 10 sections

        bar_char = "\N{BOX DRAWINGS HEAVY HORIZONTAL}"
        seek_char = "\N{RADIO BUTTON}"
        play_char = "\N{BLACK RIGHT-POINTING TRIANGLE}"
        msg = "\n" + play_char + " "

        for i in range(sections):
            msg += seek_char if i == loc_time else bar_char
        msg += " `{:.7}`/`{:.7}`".format(str(elapsed_time), str(total_time))
        return msg

    async def make_embed_message(self, author, message):
        """
        Makes the embed reply
        """
        avatar = (
            author.avatar_url_as()
        )  # This will return default avatar if no avatar is present
        color = author.color
        if message:
            link = IMAGE_LINKS.search(message)
            if link:
                message = message.replace(link.group(0), " ")

        em = discord.Embed(description=message, color=color)
        em.set_author(name=f"{author.display_name} is currently away", icon_url=avatar)
        return em

    async def find_user_mention(self, message):
        """
        Replaces user mentions with their username
        """
        for word in message.split():
            match = re.search(r"<@!?([0-9]+)>", word)
            if match:
                user = await self.bot.fetch_user(int(match.group(1)))
                message = re.sub(match.re, "@" + user.name, message)
        return message

    async def make_text_message(self, author, message):
        """
        Makes the message to display if embeds aren't available
        """
        message = await self.find_user_mention(message)
        msg = f"{author.display_name} is currently away"
        return message or msg

    async def is_mod_or_admin(self, member: discord.Member):
        guild = member.guild
        if member == guild.owner:
            return True
        if await self.bot.is_owner(member):
            return True
        if await self.bot.is_admin(member):
            return True
        if await self.bot.is_mod(member):
            return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        guild = message.guild
        if not guild or not message.mentions or message.author.bot:
            return
        if not message.channel.permissions_for(guild.me).send_messages:
            return

        blocked_guilds = await self.config.ign_servers()
        guild_config = await self.config.guild(guild).all()
        for author in message.mentions:
            if (
                guild.id in blocked_guilds and not await self.is_mod_or_admin(author)
            ) or author.id in guild_config["BLACKLISTED_MEMBERS"]:
                continue
            user_data = await self.config.custom("AwayGroup", guild.id, author.id).all()
            embed_links = message.channel.permissions_for(guild.me).embed_links

            away_msg = user_data["MESSAGE"]
            # Convert possible `delete_after` of < 5s of before PR#212
            if (
                isinstance(away_msg, list)
                and away_msg[1] is not None
                and away_msg[1] < 5
            ):
                await self.config.custom("AwayGroup", guild.id, author.id).MESSAGE.set(
                    (away_msg[0], 5)
                )
                away_msg = away_msg[0], 5
            if away_msg:
                if type(away_msg) in [tuple, list]:
                    # This is just to keep backwards compatibility
                    away_msg, delete_after = away_msg
                else:
                    delete_after = None
                if embed_links and not guild_config["TEXT_ONLY"]:
                    em = await self.make_embed_message(author, away_msg)
                    await message.channel.send(embed=em, delete_after=delete_after)
                elif (embed_links and guild_config["TEXT_ONLY"]) or not embed_links:
                    msg = await self.make_text_message(author, away_msg)
                    await message.channel.send(msg, delete_after=delete_after)
                continue

    @commands.command(name="away")
    @commands.guild_only()
    async def away_(
        self, ctx, delete_after: Optional[int] = None, *, message: str = None
    ):
        """
        Tell the bot you're away or back.

        `delete_after` Optional seconds to delete the automatic reply. Must be minimum 5 seconds
        `message` The custom message to display when you're mentioned
        """
        if delete_after is not None and delete_after < 5:
            return await ctx.send(
                "Please set a time longer than 5 seconds for the `delete_after` argument"
            )

        author_id = ctx.author.id
        mess = await self.config.custom("AwayGroup", ctx.guild.id, author_id).MESSAGE()
        if mess:
            await self.config.custom("AwayGroup", ctx.guild.id, author_id).MESSAGE.set(
                False
            )
            msg = "You're now back."
        else:
            if message is None:
                await self.config.custom(
                    "AwayGroup", ctx.guild.id, author_id
                ).MESSAGE.set((" ", delete_after))
            else:
                await self.config.custom(
                    "AwayGroup", ctx.guild.id, author_id
                ).MESSAGE.set((message, delete_after))

            msg = "You're now set as away."
        await ctx.send(msg)
