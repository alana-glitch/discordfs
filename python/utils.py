"""Commonly used utility functions."""
from typing import List, Dict
from io import BytesIO
import requests
import discord
from discord.ext.commands import Bot
from datetime import datetime
from database.mongo_client import MgClient

CONTENT_TYPE_CHOICES = sorted([
    {"name": "mp4", "value": "video/mp4"},
    {"name": "gif", "value": "image/gif"},
    {"name": "jpg/jpeg", "value": "image/jpeg"},
    {"name": "pdf", "value": "application/pdf"},
    {"name": "png", "value": "image/png"},
    {"name": "image", "value": "image"},
    {"name": "audio", "value": "audio"},
    {"name": "zip", "value": "application/zip"},
    {"name": "mp3/m4a", "value": "audio/mpeg"},
], key=lambda x: x['name'])
CONTENT_TYPE_CHOICES = list(map(lambda opt: discord.app_commands.Choice(**opt), CONTENT_TYPE_CHOICES))

dm_option = {
    "name":"dm",
    "description":"If `True`, I'll dm you what I find. Otherwise, I'll send it to this channel",
    "option_type": discord.AppCommandOptionType.boolean,
    "required": False
}

search_options = [
    {
        "name":"filename",
        "description":"Even a partial name of your file will do :)",
        "option_type":discord.AppCommandOptionType.string,
        "required":False,
},
{
        "name":"filetype",
        "description":"You can choose a filetype here. Use `custom filetype` to specify a different one",
        "option_type":discord.AppCommandOptionType.string,
        "required":False,
        "choices":CONTENT_TYPE_CHOICES
},
{
        "name":"custom_filetype",
        "description":"Searches for files of a custom file type",
        "option_type":discord.AppCommandOptionType.string,
        "required":False,
},
{
        "name":"author",
        "description":"Searches for files uploaded by a user",
        "option_type":discord.AppCommandOptionType.user,
        "required":False
},
{
        "name":"channel",
        "description":"Searches for files in a channel",
        "option_type":discord.AppCommandOptionType.channel,
        "required":False
},
{
        "name":"content",
        "description":"Search for files in messages by message content",
        "option_type":discord.AppCommandOptionType.string,
        "required":False
},
{
        "name":"after",
        "description":"Search for files after a date. Use the `before` option to specify a range of dates",
        "option_type":discord.AppCommandOptionType.string,
        "required":False
},
{
        "name":"before",
        "description":"Search for files before a date. Use the `after` option to specify a range of dates",
        "option_type":discord.AppCommandOptionType.string,
        "required":False
},
    dm_option
]

search_opts = {opt['name']: opt['description'] for opt in search_options}


def filter_messages_with_permissions(author: discord.User, files: List[Dict], perm: discord.Permissions, bot: Bot) -> List[Dict]:
    """
    Filter messages that the `author` can view.

    Args:
        author: The discord.User querying for files
        files: A list of dicts returned from ElasticSearch.
        perm: The permission you're filtering with.

    Returns:
        A list of dicts of files from ElasticSearch that the author can view.
    """
    viewable_files = []
    for file in files:
        file_chan_id = int(file['channel_id'])
        file_message_chan = bot.get_channel(file_chan_id)
        if isinstance(file_message_chan, discord.DMChannel):
            viewable_files.append(file)
            continue
        authorperms = file_message_chan.permissions_for(author)
        # Question: What happens when a user is invited to a channel and has
        # the `read_messages` permission?
        # The user could only view messages posted *after* they were added.
        # If their query has images posted both before *and* after the user was
        # invited, what should we return?
        if authorperms.is_superset(perm):
            viewable_files.append(file)
    return viewable_files


async def download(files: List[Dict], mg_client: MgClient) -> List[discord.File]:
    """
    Download files from their urls (discord cdn).

    Args:
        files: A list of dicts of files from ElasticSearch.

    Returns:
        A list of discord.File objects of the files retrieved.
    """
    for file in files:
        url = file.get('url')
        filename = file.get('filename')
        if not url:
            file_id = file['objectID']
            try:
                res = await mg_client.get_file(file_id)
                if not res:
                    print("Empty response from Mongo")
                    continue
                url = res['url']
                filename = res['filename']
            except BaseException as e:
                print(e)
        response = requests.get(url, stream=True)
        if not response.ok:
            print(response)
        file_buf = BytesIO()
        for blk in response.iter_content(1024):
            if not blk:
                break
            file_buf.write(blk)
        file_buf.seek(0)
        yield discord.File(file_buf, filename)
        file_buf.close()


def attachment_to_search_dict(message: discord.Message, file: discord.Attachment) -> Dict:
    """
    Convert a discord.Attachment to the dict metadata format.

    The dict metadata format only contains searchable fields:
    - author id
    - message content
    - filetype
    - message_id
    - channel_id

    Args:
        message: The discord.Message that contains this attachment
        file: The discord.Attachment to convert to a dict.

    Returns:
        A dict that contains metadata about the attachment.
    """
    if '.' in file.filename:
        filetype = file.filename[file.filename.rindex('.') + 1:]
    else:
        filetype = "unknown"
    return {
        "objectID": file.id,
        "author_id": message.author.id,
        "content": message.content,
        "filename": file.filename,
        "content_type": file.content_type,
        "filetype": filetype,
        "channel_id": message.channel.id,
        "message_id": message.id,
        "url": file.url,
        "jump_url": message.jump_url,
        "created_at": message.created_at.isoformat()
    }


def server_to_mongo_dict(server: discord.Guild or discord.DMChannel) -> Dict:
    """
    Convert a discord.Attachment to the dict metadata format.

    The dict metadata format only contains searchable fields:
    - author id
    - message content
    - created_at
    - filetype
    - message_id

    Args:
        message: The discord.Message that contains this attachment
        file: The discord.Attachment to convert

    Returns:
        A dict that contains metadata about the attachment.
    """
    if not server.owner:
        owner_name = "UNKNOWN"
    else:
        owner_name = f"{server.owner.name}#{server.owner.discriminator}"

    return {
        "_id": server.id,
        "created_at": server.created_at,
        "owner_id": server.owner_id,
        "owner_name": owner_name,
        "members": server.member_count,
        "max_members": server.max_members,
        "description": server.description,
        "large": server.large,
        "name": server.name,
        "filesize_limit": server.filesize_limit,
        "icon": server.icon,
        "region": server.region,
        "timestamp": datetime.now(),
        "bot_in_server": True,
        "verified": False
    }


def attachment_to_mongo_dict(message: discord.Message, file: discord.Attachment) -> Dict:
    """
    Convert a discord.Attachment to the dict metadata format.

    The dict metadata format only contains searchable fields:
    - author id
    - message content
    - created_at
    - filetype
    - message_id

    Args:
        message: The discord.Message that contains this attachment
        file: The discord.Attachment to convert

    Returns:
        A dict that contains metadata about the attachment.
    """
    return {
        "_id": file.id,
        "author": message.author.id,
        "author_name": message.author.name + '#' + str(message.author.discriminator),
        "channel_id": message.channel.id,
        "guild_id": message.guild.id if message.guild.id is not None else -1,
        "content": message.content,
        "created_at": message.created_at,
        "file_name": file.filename,
        "mimetype": file.content_type,
        "message_id": message.id,
        "size": file.size,
        "url": file.url,
        "height": file.height if file.height else -1,
        "width": file.width if file.width else -1,
        "timestamp": datetime.now()}


def command_to_mongo_dict(command_type: str, interaction: discord.Interaction, query: dict) -> Dict:
    """
    Convert a command to a dict.

    Args:
        command: The command.

    Returns:
        A dict that summarizes the command.
    """
    channel = interaction.channel

    source = channel.id
    if channel.guild is not None:
        source = channel.guild.id
    return {
        "caller": interaction.user.name + '#' + interaction.user.discriminator,
        "query": query,
        "source": source,
        "type": command_type,
        "timestamp": datetime.now().isoformat(),
    }
