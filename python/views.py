from typing import List, Dict
import discord

# Define a simple View that gives us a counter button
class FileDropDown(discord.ui.Select):

    def __init__(self, files):
        self.value_to_name = {self.build_select_value(file): file['filename'] for file in files}

        options = self.produce_options()
        super().__init__(placeholder="Choose your files here!", options=options)

    def build_select_value(self, file: Dict):
        return ','.join(map(str, [file['channel_id'], file['message_id'], file['objectID']]))

    def produce_options(self):
        options = []
        for value, name in self.value_to_name.items():
            if len(name) >= 100:
                name = name[:97] + '...'
            option = discord.SelectOption(label=name, value=value)
            options.append(option)
        return options

    async def callback(self, interaction: discord.Interaction):
        # edit the embed here
        value = self.values[0]
        name = self.value_to_name[value]
        message = interaction.message
        embed = message.embeds[0]
        channel_id, message_id, file_id = value.split(',')
        if interaction.guild is not None:
            jump_url = f"https://discord.com/channels/{interaction.guild.id}/{channel_id}/{message_id}"
            media_url = f"https://cdn.discordapp.com/attachments/{channel_id}/{file_id}/{name}"
        embed.set_field_at(index=0, name=name[:256], value=jump_url)
        embed.set_image(url=media_url)
        await interaction.response.edit_message(embed=embed)


class FileButton(discord.ui.Button):
    def __init__(self, file: Dict):
        super().__init__(style=discord.ButtonStyle.url, label=file['filename'][:80], url=file['jump_url'])

# Define a View that will give us our own personal counter button
class FileView(discord.ui.View):
    def __init__(self, files: List[Dict]):
        super().__init__()
        if len(files) <= 5:
            for file in files:
                self.add_item(FileButton(file))
        else:
            self.add_item(FileDropDown(files))
