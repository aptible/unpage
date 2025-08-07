import asyncio

import sentry_sdk


async def init() -> None:
    sentry_sdk.init(
        dsn="https://355c313b713086f073fc60c6527f9db8@o12041.ingest.us.sentry.io/4509431193272320",
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
    )


# Only run if not in an existing event loop
if not asyncio.get_event_loop_policy():
    asyncio.run(init())
