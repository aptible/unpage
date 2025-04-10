import re
from typing import Self

from pydantic import BaseModel

_arn_base_pattern = re.compile(
    r"^arn:"
    r"(?P<partition>.+?):"
    r"(?P<service>.+?):"
    r"(?P<region>.*?):"
    r"(?P<account>.*?):"
    r"(?P<rest>.*)$"
)


class AwsArn(BaseModel):
    partition: str
    service: str
    region: str | None = None
    account_id: str | None = None
    rest: str | None = None

    @classmethod
    def parse(cls, arn: str) -> Self:
        base_match = _arn_base_pattern.match(arn)
        if not base_match:
            raise ValueError(f"Invalid ARN format: {arn}")
        return cls(
            partition=base_match.group("partition"),
            service=base_match.group("service"),
            region=base_match.group("region"),
            account_id=base_match.group("account"),
            rest=base_match.group("rest"),
        )
