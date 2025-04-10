from pydantic import AwareDatetime

from unpage.models import LogLine


class HasLogs:
    """A mixin for nodes that support retrieving logs."""

    async def get_logs(
        self,
        time_range_start: AwareDatetime,
        time_range_end: AwareDatetime,
    ) -> list[LogLine]:
        """Retrieve the node's logs for a given time range."""
        raise NotImplementedError
