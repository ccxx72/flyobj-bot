from datetime import datetime

from syncasync import AsyncToSync
from tortoise import Tortoise
from tortoise.exceptions import DoesNotExist

from models.api_counter import ApiCounter


class DbManager:
    def __init__(self):
        self.create_tortoise_instance()

    @AsyncToSync
    async def create_tortoise_instance(self):
        await Tortoise.init(config_file="tortoise.json")
        await Tortoise.generate_schemas(safe=True)

    @AsyncToSync
    async def has_quota_reached(self):
        now = datetime.now()
        month = f"{now.month}-{now.year}"
        try:
            row = await ApiCounter.get(month=month)
            return row.count < (row.limit - 1)
        except DoesNotExist:
            await ApiCounter.create(month=month)
            return False

    @AsyncToSync
    async def increase_counter(self):
        now = datetime.now()
        month = f"{now.month}-{now.year}"
        try:
            row = await ApiCounter.get(month=month)
            new_count = row.count + 1

            if new_count < row.limit:
                await ApiCounter.filter(month=month).update(count=new_count)
                return new_count
            else:
                return row.count
        except DoesNotExist:
            return -1
