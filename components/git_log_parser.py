import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import aiohttp
from eidolon_ai_sdk.apu.logic_unit import LogicUnit, llm_function
from eidolon_ai_sdk.system.reference_model import Specable
from pydantic import BaseModel, Field


class GitLogLogicUnitSpec(BaseModel):
    token: Optional[str] = Field(
        default_factory=lambda: os.environ.get("GITHUB_TOKEN"),
        description="Github token, can also be set via envar 'GITHUB_TOKEN'",
    )


# noinspection PyMethodMayBeStatic
class GitLogLogicUnit(LogicUnit, Specable[GitLogLogicUnitSpec]):
    """
    A LogicUnit that runs git commands. Use this to interact with git repositories.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Specable.__init__(self, **kwargs)

    @llm_function(title="action_logs", sub_title="Get GitHub Workflow Job Log Failures")
    async def get_job_failure_logs(self, owner: str, repo: str, job_id: str, step_number: int, start_char: Optional[int] = 0, end_char: Optional[int] = -1) -> str:
        """
        Get the logs of a step of a job. The logs are filtered to only include the logs for the step.
        :param owner: the owner of the repository
        :param repo: the repository name
        :param job_id: the job id
        :param step_number: the step number to retrieve the logs for.
        :param start_char: the starting character. Defaults to 0 and is only required if the log is too large
        :param end_char: the ending character. Defaults to -1 and is only required if the log is too large. -1 means the end of the log.
        :return: the logs for the step
        """

        # First get the job
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}"

        # Set up headers for authentication
        headers = {
            "Authorization": f"token {self.spec.token}",
            "Accept": "application/vnd.github.v3+json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return f"Error: Unable to fetch logs. Status code: {response.status}"

                job_info = await response.json()

        try:
            step = next(step for step in job_info["steps"] if step["number"] == step_number)
        except StopIteration:
            return f"Error: Step number {step_number} not found in job info"

        start_time = step["started_at"]
        end_time = step["completed_at"]
        start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00')) + timedelta(seconds=1)

        print(f"Getting logs for step {step['name']}", start_datetime, end_datetime)
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return f"Error: Unable to fetch logs. Status code: {response.status}"

                log_lines = []
                async for line in response.content:
                    line = line.decode('utf-8').rstrip()

                    timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)', line)
                    if timestamp_match:
                        timestamp_str = timestamp_match.group(1)
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        if start_datetime <= timestamp <= end_datetime:
                            log_lines.append(line)
                    else:
                        # If there's no timestamp, we include the line if we're within the time range
                        if start_datetime <= datetime.now(timezone.utc) <= end_datetime:
                            log_lines.append(line)

        return ("\n".join(log_lines))
