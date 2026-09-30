import os
import random
import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")  # optional, official Anthropic key for !ask

# Optional: use a third-party OpenAI-compatible provider instead (e.g. a key from another site)
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL")  # e.g. https://api.example.com/v1
AI_MODEL = os.getenv("AI_MODEL")  # a model name that provider supports
WELCOME_CHANNEL = os.getenv("WELCOME_CHANNEL", "welcome")  # channel name
AUTO_ROLE = os.getenv("AUTO_ROLE", "Member")  # role given to new members

# Optional AI chat (only enabled if a key is set)
ai_client = None
ai_mode = None
if AI_API_KEY and AI_BASE_URL and AI_MODEL:
    from openai import AsyncOpenAI
    ai_client = AsyncOpenAI(api_key=AI_API_KEY, base_url=AI_BASE_URL)
    ai_mode = "openai"
elif ANTHROPIC_KEY:
    from anthropic import AsyncAnthropic
    ai_client = AsyncAnthropic(api_key=ANTHROPIC_KEY)
    ai_mode = "anthropic"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


# ---------------------------------------------------------------- events
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (id: {bot.user.id})")
    await bot.change_presence(activity=discord.Game(name="!help"))


@bot.event
async def on_member_join(member: discord.Member):
    # Auto role
    role = discord.utils.get(member.guild.roles, name=AUTO_ROLE)
    if role:
        try:
            await member.add_roles(role, reason="Auto role on join")
        except discord.Forbidden:
            print("Missing permission or role is above the bot's role.")

    # Welcome message
    channel = discord.utils.get(member.guild.text_channels, name=WELCOME_CHANNEL)
    channel = channel or member.guild.system_channel
    if channel:
        embed = discord.Embed(
            title=f"Welcome to {member.guild.name}!",
            description=f"Hey {member.mention}, glad you're here. Say hi and have fun!",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count}")
        await channel.send(embed=embed)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use that command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing argument: `{error.param.name}`. Try `!help`.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("I couldn't find that member.")
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await ctx.send("Something went wrong running that command.")
        print(f"Error in {ctx.command}: {error}")


# ---------------------------------------------------------------- help
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Alex Bot commands", color=discord.Color.blurple())
    embed.add_field(
        name="Moderation",
        value="`!kick @user [reason]`\n`!ban @user [reason]`\n"
              "`!mute @user [minutes] [reason]`\n`!unmute @user`\n`!clear [amount]`",
        inline=False,
    )
    embed.add_field(
        name="Roles",
        value="`!giverole @user RoleName`\n`!removerole @user RoleName`",
        inline=False,
    )
    embed.add_field(
        name="Fun",
        value="`!8ball question`\n`!coinflip`\n`!roll [sides]`\n"
              "`!rps rock|paper|scissors`\n`!guess`\n`!joke`",
        inline=False,
    )
    embed.add_field(name="AI", value="`!ask your question`", inline=False)
    embed.add_field(name="Info", value="`!ping`\n`!userinfo [@user]`", inline=False)
    await ctx.send(embed=embed)


# ---------------------------------------------------------------- info
@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency * 1000)}ms")


@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=str(member), color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined server", value=discord.utils.format_dt(member.joined_at, "R"))
    embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
    await ctx.send(embed=embed)


# ---------------------------------------------------------------- moderation
@bot.command()
@commands.has_permissions(kick_members=True)
@commands.bot_has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason="No reason given"):
    await member.kick(reason=reason)
    await ctx.send(f"Kicked {member} | {reason}")


@bot.command()
@commands.has_permissions(ban_members=True)
@commands.bot_has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason given"):
    await member.ban(reason=reason)
    await ctx.send(f"Banned {member} | {reason}")


@bot.command()
@commands.has_permissions(moderate_members=True)
@commands.bot_has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason="No reason given"):
    until = discord.utils.utcnow() + datetime.timedelta(minutes=minutes)
    await member.timeout(until, reason=reason)
    await ctx.send(f"Muted {member} for {minutes} min | {reason}")


@bot.command()
@commands.has_permissions(moderate_members=True)
@commands.bot_has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"Unmuted {member}")


@bot.command()
@commands.has_permissions(manage_messages=True)
@commands.bot_has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 5):
    amount = max(1, min(amount, 100))
    deleted = await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"Deleted {len(deleted) - 1} messages.", delete_after=3)


# ---------------------------------------------------------------- roles
@bot.command()
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True)
async def giverole(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        return await ctx.send("Role not found. Names are case-sensitive.")
    await member.add_roles(role)
    await ctx.send(f"Gave **{role.name}** to {member.mention}")


@bot.command()
@commands.has_permissions(manage_roles=True)
@commands.bot_has_permissions(manage_roles=True)
async def removerole(ctx, member: discord.Member, *, role_name: str):
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        return await ctx.send("Role not found. Names are case-sensitive.")
    await member.remove_roles(role)
    await ctx.send(f"Removed **{role.name}** from {member.mention}")


# ---------------------------------------------------------------- fun
@bot.command(name="8ball")
async def eight_ball(ctx, *, question: str):
    answers = [
        "Yes.", "No.", "Definitely!", "Not a chance.", "Ask again later.",
        "Probably.", "I wouldn't count on it.", "Signs point to yes.",
    ]
    await ctx.send(f"🎱 {random.choice(answers)}")


@bot.command()
async def coinflip(ctx):
    await ctx.send(f"🪙 {random.choice(['Heads', 'Tails'])}!")


@bot.command()
async def roll(ctx, sides: int = 6):
    sides = max(2, sides)
    await ctx.send(f"🎲 You rolled a **{random.randint(1, sides)}** (d{sides})")


@bot.command()
async def rps(ctx, choice: str):
    options = ["rock", "paper", "scissors"]
    choice = choice.lower()
    if choice not in options:
        return await ctx.send("Pick rock, paper, or scissors.")
    bot_choice = random.choice(options)
    wins = {("rock", "scissors"), ("paper", "rock"), ("scissors", "paper")}
    if choice == bot_choice:
        result = "It's a tie!"
    elif (choice, bot_choice) in wins:
        result = "You win!"
    else:
        result = "I win!"
    await ctx.send(f"You: **{choice}** | Me: **{bot_choice}**\n{result}")


@bot.command()
async def guess(ctx):
    number = random.randint(1, 10)
    await ctx.send("I'm thinking of a number from 1 to 10. You have 15 seconds!")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()

    try:
        msg = await bot.wait_for("message", check=check, timeout=15)
    except Exception:
        return await ctx.send(f"Time's up! It was {number}.")
    if int(msg.content) == number:
        await ctx.send("🎉 Correct!")
    else:
        await ctx.send(f"Nope, it was {number}.")


@bot.command()
async def joke(ctx):
    jokes = [
        "Why do programmers prefer dark mode? Because light attracts bugs.",
        "Why did the Roblox player cross the road? To get to the other obby.",
        "I would tell you a UDP joke, but you might not get it.",
    ]
    await ctx.send(random.choice(jokes))


# ---------------------------------------------------------------- AI chat
@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def ask(ctx, *, question: str):
    if not ai_client:
        return await ctx.send("AI chat isn't set up. Add ANTHROPIC_API_KEY to the .env file.")
    async with ctx.typing():
        try:
            system_prompt = ("You are Alex Bot, a friendly Discord bot. Keep answers short "
                             "(under 1500 characters) and casual.")
            if ai_mode == "openai":
                response = await ai_client.chat.completions.create(
                    model=AI_MODEL,
                    max_tokens=500,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                )
                text = response.choices[0].message.content or "(empty reply)"
            else:
                response = await ai_client.messages.create(
                    model="claude-sonnet-5-5",
                    max_tokens=500,
                    system=system_prompt,
                    messages=[{"role": "user", "content": question}],
                )
                text = "".join(b.text for b in response.content if b.type == "text")
        except Exception as e:
            print(f"AI error: {e}")
            return await ctx.send("Sorry, the AI request failed.")
    await ctx.send(text[:1900])


if not TOKEN:
    raise SystemExit("DISCORD_TOKEN is missing. Add it to your .env file.")
bot.run(TOKEN)
