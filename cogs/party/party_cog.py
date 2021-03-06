# party_cog.py
#
# The party cog contains the definition of all the party-related management
# that the bot can perform. The party functionality allows users to create
# an embed message that allows other users to add themselves as a member in
# similar to an in-game lobby.

import os

import discord
from discord.ext import commands
from discord.ext import tasks
from dotenv import load_dotenv

from cogs.party import party_class as party
from utility import utility


load_dotenv()
COMMAND_PREFIX = os.getenv('COMMAND_PREFIX')
LFG_CHANNEL = os.getenv('LFG_CHANNEL')
BACKGROUND_LOOP_TIME = os.getenv('BACKGROUND_LOOP_TIME')


parties = []


class Party(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_parties.start()

    # party
    #
    # The party command provides the user a way to create an individual
    # embed message that holds a list of members and waitlist. The message can
    # be of a preset type or a custom type. Preset types mention the role while
    # custom types do not. When a user creates a the embed message, other users
    # can interact with the default reactions added by the bot to add
    # themselves or remove themselves from the party. Party leaders have the
    # additional option to close the party early.

    @commands.command(name='party', brief='Creates a party people can join',
                      description=f'\"{COMMAND_PREFIX}party Role\" - '
                      'Creates party creator for specific Role with presets\n'
                      f'\"{COMMAND_PREFIX}party SomeName OptionalSize\" - '
                      'Creates a custom party of SomeName and OptionalSize '
                      '(default size will be 4)')
    async def createParty(self, context, *args):
        # For valid parties, the embed message should go into a specified
        # channel so that regular channels are not moving the embed message
        # from chatter
        lfgChannel = discord.utils.get(self.bot.get_all_channels(),
                                       guild__name=context.guild.name,
                                       name=LFG_CHANNEL)

        if lfgChannel is None:
            return await context.channel.send(f'This server has not set up a'
                                              'LFG Channel (default:'
                                              f' {LFG_CHANNEL})')

        if len(args) == 0:
            return await context.channel.send(
                f'{context.author.name}, please include a party name and '
                f'optional party size (default size is '
                f'{party.DEFAULT_PARTY_SIZE} or preset)')

        name = args[0]

        if name.isspace() or len(name) == 0:
            return await context.channel.send('Please type a valid party name')

        try:
            size = int(args[1]) if len(args) >= 2 else None
        except ValueError:
            return await context.channel.send('Ensure that party size is a'
                                              'number')

        if len(name) > 256:
            return await context.channel.send('Your party name is too long. '
                                              '(256 characters please)')

        if size is not None and size <= 0:
            return await context.channel.send('Your party size is too small.')

        role = utility.getRole(context.guild.roles, name)

        try:
            if role is not None and utility.isGamesRole(role):
                message = await lfgChannel.send(role.mention)
            else:
                message = await lfgChannel.send(embed=discord.Embed())
        except discord.Forbidden:
            return await context.channel.send(f'I do not have permissions in'
                                              f' {LFG_CHANNEL}')

        newParty = (party.Party(message, context.author, name) if
                    size is None
                    else party.Party(message, context.author, name, size))
        parties.append(newParty)

        await message.edit(embed=newParty.getEmbed())
        await message.add_reaction(newParty.joinEmoji)
        await message.add_reaction(newParty.closeEmoji)

    # on_reaction_add
    #
    # The party cog looks for users reacting to the party embed messages so
    # when a user clicks on one of the two reactions, the bot can perform
    # the appropriate action. When the user adds a join reaction, they are
    # added to the party or waitlist. If the party leader adds a "close"
    # reaction, it closes the party.

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        for p in parties:
            if user.name == self.bot.user.name:
                continue
            if p.isMatchJoinEmoji(reaction):
                p.addMember(user.name)
                await reaction.message.edit(embed=p.getEmbed())
                break
            if p.isMatchCloseEmoji(reaction, user):
                p.close()
                await reaction.message.edit(embed=p.getEmbed())
                parties.remove(p)
                break

    # on_reaction_remove
    #
    # The party cog looks for users reacting to the party embed messages so
    # when a user clicks on one of the two reactions, the bot can perform
    # the appropriate action. When the user removes a join reaction, they are
    # removed from the party or waitlist.

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        for p in parties:
            if p.isMatchJoinEmoji(reaction):
                p.removeMember(user.name)
                await reaction.message.edit(embed=p.getEmbed())
                break

    # update_parties
    #
    # This function checks if parties are inactive and cleans up them up if
    # they are. The loop checks according to the BACKGROUND_LOOP_TIME and
    # they are labeled inactive based on ACTIVE_DURATION_SECONDS in the
    # Party class
    @tasks.loop(seconds=int(BACKGROUND_LOOP_TIME))
    async def update_parties(self):
        for p in parties:
            if p.isInactive():
                await p.message.edit(embed=p.getEmbed())
                parties.remove(p)
