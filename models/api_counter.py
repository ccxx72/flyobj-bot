from tortoise.models import Model
from tortoise import fields


class ApiCounter(Model):
    count = fields.IntField(default=0)
    limit = fields.IntField(default=350)
    month = fields.CharField(max_length=7, unique=True)

    def __str__(self):
        return f"{self.month}: [{self.count} / {self.limit}]"
