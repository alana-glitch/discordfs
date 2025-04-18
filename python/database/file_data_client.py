from database.async_data_client import AsyncDataClient
from pathlib import Path
import os
import utils
import logging
import aiofiles
import msgpack


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
fh = logging.FileHandler('usage.log', encoding='utf-8', mode='w')
fh.setFormatter(formatter)
logger.addHandler(fh)

class FileDataClient(AsyncDataClient):

    def __init__(self, db_name: str = None, logs_fp: str = "usage", commands_fp: str = "commands.msgpack"):
        self.user = None
        self.db_name = db_name
        self.logs_fp = logs_fp
        Path(logs_fp).mkdir(exist_ok=True)
        self.commands_fp = db_name + "_" + commands_fp
        self.filepath = os.path.join(logs_fp, commands_fp)

    async def log_command(self, command_type, *args, **kwargs) -> bool:
        """
        Log commands to the database.

        Args:
            command: The user command
            args: Arbitrary arguments, usually context
            kwargs: Query parameters

        Returns:
            Whether the log operation was successful
        """
        commands = ['search', 'delete', 'remove', 'export']
        for command in commands:
            if command in command_type.__name__:
                command_type = command
                break
        for key, val in kwargs.items():
            kwargs[key] = repr(val)
        interaction = args[0]
        command_info = utils.command_to_mongo_dict(command_type, interaction, kwargs)
        mode = 'wb'
        if os.path.exists(self.filepath):
            mode = 'ab'
        async with aiofiles.open(self.filepath, mode) as f:
            data = msgpack.packb(command_info)
            await f.write(data)
        return True
