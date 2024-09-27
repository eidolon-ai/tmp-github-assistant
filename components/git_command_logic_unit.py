import asyncio
import os
from pathlib import Path
from typing import List, Optional, Tuple

from eidolon_ai_sdk.apu.logic_unit import LogicUnit, llm_function
from eidolon_ai_sdk.system.reference_model import Specable
from eidolon_ai_sdk.util.str_utils import replace_env_var_in_string
from pydantic import BaseModel, Field, field_validator


class GitCommandLogicUnitSpec(BaseModel):
    owner: str
    repo: str
    root: str = Field(
        "${EIDOLON_DATA_DIR}/git_repo",
        description="The file location of the .git directory.",
        validate_default=True,
    )
    token: Optional[str] = Field(
        default_factory=lambda: os.environ.get("GITHUB_TOKEN"),
        description="Github token, can also be set via envar 'GITHUB_TOKEN'",
    )

    # noinspection PyMethodParameters,HttpUrlsUsage
    @field_validator("root")
    def validate_root(cls, path):
        if len(path) == 0:
            raise ValueError("path must be a valid path")

        # validate path is a file on disk
        value = replace_env_var_in_string(path, EIDOLON_DATA_DIR="/tmp/eidolon_data_dir")
        # Convert the string to a Path object
        path = Path(value).resolve()

        # Check if the path is absolute
        if not path.is_absolute():
            raise ValueError(f"The root_dir must be an absolute path. Received: {path}->{value}")

        return path.absolute()


# noinspection PyMethodMayBeStatic
class GitCommandLogicUnit(LogicUnit, Specable[GitCommandLogicUnitSpec]):
    """
    A LogicUnit that runs git commands. Use this to interact with git repositories.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Specable.__init__(self, **kwargs)

    async def _run_git_command(self, branch: str, command: List[str], is_clone: bool = False) -> Tuple[bool, str]:
        """
        Run a git command
        :param branch: the branch to run the command on
        :param command: the command to run
        :return: the output of the command
        """
        path = Path(self.spec.root, branch)
        if not is_clone:
            path = Path(path, self.spec.repo)
        print("running command ", "git", *command)
        proc = await asyncio.create_subprocess_exec("git", *command,
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE,
                                                    cwd=path,
                                                    )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return False, "Error: " + stderr.decode() + '\n' + stdout.decode()

        output = stderr.decode() + '\n' + stdout.decode()
        if output and len(output) > 100000:
            return True, "The command returned too much output to display. Please run a different comand."
        return True, output

    async def _verify_git_repo(self, branch: str) -> Tuple[bool, str]:
        """
        Verify the git repo
        :return: True if the repo is valid, False otherwise
        """
        path = Path(self.spec.root, branch)
        if not path.exists():
            print("It does not")
            try:
                path.mkdir(parents=True)
            except Exception as e:
                return False, f"Failed to create directory {path}; {e}"
        if not Path(path, self.spec.repo, ".git", "HEAD").exists():
            # clone the repo
            status, msg = await self._run_git_command(branch, ["clone", f"https://{self.spec.token}@github.com/{self.spec.owner}/{self.spec.repo}.git", ], True)
            if not status:
                return False, msg

        return await self._run_git_command(branch, ["checkout", branch])

    @llm_function(title="pull", sub_title="git pull <args>")
    async def git_pull(self, branch: str) -> str:
        """
        Pull the latest changes from the git repo on the specified branch. Use this to update the repo or as a first step to get the repo.
        :param branch: the name of the branch to pull from. Use main for the default branch.
        :return: response message from git
        """
        verify_ok, verify_msg = await self._verify_git_repo(branch)
        if not verify_ok:
            return f"Internal Error: Failed to clone repo. DO NOT CONTINUE: {verify_msg}"
        status, msg = await self._run_git_command(branch, ["pull"])
        return msg

    @llm_function(title="diff", sub_title="git diff <args>")
    async def git_diff(self, branch: str, args: List[str]) -> str:
        """
        Get add diff of a file or files on the git repo. The branch will act as the working directory for the diff.
        :param branch: the branch to get the diff from
        :param args: the arguments to pass to the diff command. Each argument should be a separate string in the list.
        """
        verify_ok, verify_msg = await self._verify_git_repo(branch)
        if not verify_ok:
            return f"Internal Error: Failed to clone repo. DO NOT CONTINUE: {verify_msg}"
        status, msg = await self._run_git_command(branch, ["diff", *args])
        return msg

    @llm_function(title="log", sub_title="git log <args>")
    async def git_log(self, branch: str, args: List[str]) -> str:
        """
        Get the log of the git repo. The branch will act as the working directory for the log.
        """
        verify_ok, verify_msg = await self._verify_git_repo(branch)
        if not verify_ok:
            return f"Internal Error: Failed to clone repo. DO NOT CONTINUE: {verify_msg}"
        status, msg = await self._run_git_command(branch, ["log", *args])
        return msg

    @llm_function(title="Get file", sub_title="Get the contents of a file")
    async def get_file(self, branch: str, file: str) -> str:
        """
        Get the contents of a file
        :param branch: the branch to get the file from
        :param file: the file to get including the full path to the file.
        :return: the contents of the file
        """
        verify_ok, verify_msg = await self._verify_git_repo(branch)
        if not verify_ok:
            return f"Internal Error: Failed to clone repo. DO NOT CONTINUE: {verify_msg}"
        root = Path(self.spec.root, branch, self.spec.repo)
        file_path = Path(root, file).absolute()
        if not file_path.exists():
            return f"File '{file}' not found"
        return file_path.read_text()

    @llm_function(title="LS path", sub_title="List the contents of a path")
    async def ls(self, branch: str, path: str) -> str:
        """
        Get the contents of a path
        :param branch: the branch to get the file from
        :param path: the path you want to list
        :return: the metadata of the path
        """
        verify_ok, verify_msg = await self._verify_git_repo(branch)
        if not verify_ok:
            return f"Internal Error: Failed to clone repo. DO NOT CONTINUE: {verify_msg}"
        root = Path(self.spec.root, branch, self.spec.repo)
        file_path = Path(root, path).absolute()
        try:
            ret = ""
            # Get all entries in the directory
            entries = os.listdir(file_path)

            # Sort entries alphabetically
            entries.sort(key=lambda x: x.lower())

            for entry in entries:
                full_path = os.path.join(file_path, entry)

                # Get file stats
                stats = os.stat(full_path)

                # Format file mode (permissions)
                mode = self.format_mode(stats.st_mode)
                dir_bit = 'd' if os.path.isdir(full_path) else '-'

                size = stats.st_size

                ret += f"{dir_bit}{mode} {size:8d} {entry}\n"

            return ret
        except OSError as e:
            return f"Error accessing {path}: {e}"

    def format_mode(self, mode: int):
        """Convert a file's mode to a string representation."""
        return ''.join([
            'r' if mode & 0o400 else '-',
            'w' if mode & 0o200 else '-',
            'x' if mode & 0o100 else '-',
            'r' if mode & 0o040 else '-',
            'w' if mode & 0o020 else '-',
            'x' if mode & 0o010 else '-',
            'r' if mode & 0o004 else '-',
            'w' if mode & 0o002 else '-',
            'x' if mode & 0o001 else '-',
        ])
