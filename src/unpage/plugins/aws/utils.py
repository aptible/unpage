import asyncio
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aioboto3 import Session
from botocore.exceptions import ClientError, SSOTokenLoadError, TokenRetrievalError


async def list_accessible_regions_for_service(session: Session, service_name: str) -> list[str]:
    """Return a list of regions that the current credentials can access."""

    async def _check_region(region: str) -> tuple[str, bool]:
        """Attempt to call an API in the given region. Return True if accessible."""
        try:
            async with session.client("sts", region_name=region) as client:
                await client.get_caller_identity()
            return region, True
        except ClientError:
            return region, False

    # Now, check access to each region (concurrently)
    results = await asyncio.gather(
        *(_check_region(region) for region in await session.get_available_regions(service_name))
    )

    return [region for region, success in results if success]


@asynccontextmanager
async def swallow_boto_client_access_errors(
    service_name: str | None = None, region: str | None = None
) -> AsyncIterator[None]:
    try:
        yield
    except ClientError as e:
        err = e.response.get("Error", {})
        error_code = err.get("Code", None)
        error_msg = err.get("Message", "Unknown Message")
        if error_code in [
            "AccessDenied",
            "AccessDeniedException",
            "AuthorizationError",
            "UnauthorizedOperation",
        ]:
            print(
                f"Ignoring access denied ({error_code}) for {f'{service_name}.' if service_name else ''}{e.operation_name}{f' in {region}' if region else ''}: {error_msg}",
                file=sys.stderr,
            )
            return
        raise


@asynccontextmanager
async def hide_traceback_for_failed_sso_logins() -> AsyncIterator[None]:
    aiologger = logging.getLogger("aiobotocore")
    original_aiologger_level = aiologger.level
    try:
        aiologger.setLevel(logging.ERROR)
        yield
    finally:
        aiologger.setLevel(original_aiologger_level)


async def run_sso_login(profile: str | None = None) -> None:
    """Run the AWS SSO login command for the configured profile."""
    try:
        print(f"Attempting to login using AWS SSO for profile '{profile}'")
        print(f"Running 'aws sso login --profile {profile}'")
        print("Please complete the SSO authentication in your browser...")

        cmd = ["aws", "sso", "login"]
        if profile:
            cmd.extend(["--profile", profile])

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            print(f"Error during SSO login: {error_msg}")
            raise RuntimeError(f"Failed to authenticate with AWS SSO: {error_msg}")

    except Exception as e:
        print(f"Unexpected error during SSO login: {e}")
        raise
    else:
        print("SSO login successful")


async def ensure_aws_session(session: Session) -> None:
    async with hide_traceback_for_failed_sso_logins(), session.client("sts") as client:
        try:
            await client.get_caller_identity()
        except (SSOTokenLoadError, TokenRetrievalError):
            await run_sso_login(session.profile_name)
            await client.get_caller_identity()
        except Exception as e:
            print(f"Error using session to call STS GetCallerIdentity: {e}")
            raise
