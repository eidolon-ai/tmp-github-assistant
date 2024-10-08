from pathlib import Path

from components.git_command_logic_unit import GitCommandLogicUnitSpec, GitCommandLogicUnit


async def test_verify(tmp_path):
    path = str(tmp_path)
    spec = GitCommandLogicUnitSpec(owner="eidolon-ai", repo="gitHub-assistant", root=str(tmp_path))
    impl = GitCommandLogicUnit(spec=spec)
    assert not Path(path, "main", spec.repo, ".git", "HEAD").exists()
    status, msg = await impl._verify_git_repo("main")
    assert status

    status, msg = await impl._verify_git_repo('dlb/leave_here_for_test')
    assert status


async def test_pull_pulls_first_time(tmp_path):
    path = str(tmp_path)
    spec = GitCommandLogicUnitSpec(owner="eidolon-ai", repo="gitHub-assistant", root=str(tmp_path))
    impl = GitCommandLogicUnit(spec=spec)
    assert not Path(path, "main", spec.repo, ".git", "HEAD").exists()
    msg = await impl.git_pull("main")
    assert "Already up to date" in msg

    msg = await impl.git_pull("dlb/leave_here_for_test")
    assert "Already up to date" in msg


async def testGetFile(tmp_path):
    path = str(tmp_path)
    spec = GitCommandLogicUnitSpec(owner="eidolon-ai", repo="gitHub-assistant", root=str(tmp_path))
    impl = GitCommandLogicUnit(spec=spec)
    assert not Path(path, "main", spec.repo, ".git", "HEAD").exists()

    contents = await impl.get_file("main", "README.md")
    assert "Eidolon" in contents

    contents = await impl.get_file("main", "components/__init__.py")
    assert contents is ""


async def testLS(tmp_path):
    path = str(tmp_path)
    spec = GitCommandLogicUnitSpec(owner="eidolon-ai", repo="gitHub-assistant", root=str(tmp_path))
    impl = GitCommandLogicUnit(spec=spec)
    assert not Path(path, "main", spec.repo, ".git", "HEAD").exists()

    contents = await impl.ls("main", "resources")
    assert "chatbot.yaml" in contents


async def test_diff(tmp_path):
    path = str(tmp_path)
    spec = GitCommandLogicUnitSpec(owner="eidolon-ai", repo="gitHub-assistant", root=str(tmp_path))
    impl = GitCommandLogicUnit(spec=spec)
    assert not Path(path, "main", spec.repo, ".git", "HEAD").exists()

    diff = await impl.git_diff("main", ["d1c02173fbbf614b0be2218c9f5c4d764cd3807a", "434ddc3ce45262590d14e18607215a195c4a91b1", "--", "README.md"])

    assert diff == """
diff --git a/README.md b/README.md
index c79651f..f2acca4 100644
--- a/README.md
+++ b/README.md
@@ -42,7 +42,7 @@ INFO - Server Started in 1.50s
 
 ### Prerequisites
 
-WARNING: This will work for local k8s environments only. See [Readme.md in the k8s directory](./k8s/Readme.md) if you are using this against a cloud based k8s environment.
+WARNING: This will work for local k8s environments only. See [Readme.k8s.md](./Readme.k8s.md) if you are using this against a cloud based k8s environment.
 
 To use kubernetes for local development, you will need to have the following installed:
 * [Docker](https://docs.docker.com/get-docker/)
"""


async def test_log(tmp_path):
    path = str(tmp_path)
    spec = GitCommandLogicUnitSpec(owner="eidolon-ai", repo="gitHub-assistant", root=str(tmp_path))
    impl = GitCommandLogicUnit(spec=spec)
    assert not Path(path, "main", spec.repo, ".git", "HEAD").exists()

    log = await impl.git_log("main", ["README.md"])
    assert "commit 434ddc3ce45262590d14e18607215a195c4a91b1" in log
