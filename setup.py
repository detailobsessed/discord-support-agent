"""Interactive setup for discord-support-agent.

Usage:
    uv run setup.py
"""

import os
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path


def run_command(
    cmd: list[str],
    *,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    return subprocess.run(cmd, capture_output=capture, text=True, check=False)  # noqa: S603


def check_gh_cli() -> bool:
    """Check if gh CLI is available and authenticated."""
    if not shutil.which("gh"):
        return False
    result = run_command(["gh", "auth", "status"])
    return result.returncode == 0


def get_gh_username() -> str | None:
    """Get the authenticated GitHub username."""
    result = run_command(["gh", "api", "user", "--jq", ".login"])
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def get_gh_orgs() -> list[str]:
    """Get list of organizations the user belongs to."""
    result = run_command(["gh", "api", "user/orgs", "--jq", ".[].login"])
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split("\n")
    return []


def repo_exists(repo: str) -> bool:
    """Check if a repository exists."""
    result = run_command(["gh", "repo", "view", repo])
    return result.returncode == 0


def create_repo(repo: str, *, private: bool = True) -> bool:
    """Create a new GitHub repository."""
    visibility = "--private" if private else "--public"
    result = run_command(
        [
            "gh",
            "repo",
            "create",
            repo,
            visibility,
            "--description",
            "Support issues from Discord (auto-created by discord-support-agent)",
        ],
        capture=False,
    )
    return result.returncode == 0


def prompt_yes_no(question: str, *, default: bool = False) -> bool:
    """Prompt for yes/no answer."""
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        answer = input(question + suffix).strip().lower()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer 'y' or 'n'")


def prompt_choice(question: str, choices: list[str], *, default: int = 0) -> str:
    """Prompt for a choice from a list."""
    if not choices:
        raise ValueError("choices cannot be empty")
    print(question)
    for i, choice in enumerate(choices):
        marker = ">" if i == default else " "
        print(f"  {marker} [{i + 1}] {choice}")
    while True:
        answer = input(f"Choice [1-{len(choices)}] (default: {default + 1}): ").strip()
        if not answer:
            return choices[default]
        try:
            idx = int(answer) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(choices)}")


def update_env_file(key: str, value: str) -> None:
    """Update or add a key in .env file."""
    env_path = Path(".env")
    lines: list[str] = []

    if env_path.exists():
        lines = env_path.read_text().splitlines()

    # Find and update existing key, or prepare to append
    found = False
    for i, line in enumerate(lines):
        # Handle both "KEY=value" and "# KEY=value" (commented out)
        if "=" not in line:
            continue
        # Extract key: strip whitespace, then # chars, then whitespace again
        line_key = line.lstrip().lstrip("#").lstrip().split("=", 1)[0]
        if line_key == key:
            lines[i] = f"{key}={value}"
            found = True
            break

    if not found:
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n")


def setup_github_issues() -> None:
    """Interactive setup for GitHub issue tracking."""
    print("\n" + "=" * 60)
    print("GitHub Issue Tracking Setup")
    print("=" * 60)

    # Check gh CLI
    if not check_gh_cli():
        print("\n❌ GitHub CLI (gh) is not installed or not authenticated.")
        print("   Install: https://cli.github.com/")
        print("   Then run: gh auth login")
        return

    username = get_gh_username()
    if not username:
        print("\n❌ Could not determine GitHub username.")
        return

    print(f"\n✓ Authenticated as: {username}")

    # Get owner (user or org)
    orgs = get_gh_orgs()
    owners = [username, *orgs]

    owner = prompt_choice("\nWhere should the support repo be created?", owners) if len(owners) > 1 else username

    # Get repo name
    default_name = "discord-support-issues"
    repo_name = input(f"\nRepository name [{default_name}]: ").strip() or default_name
    full_repo = f"{owner}/{repo_name}"

    # Check if exists
    if repo_exists(full_repo):
        print(f"\n✓ Repository {full_repo} already exists.")
        if not prompt_yes_no("Use this repository?", default=True):
            return
    else:
        print(f"\nWill create: {full_repo}")
        private = prompt_yes_no("Make it private?", default=True)

        if not prompt_yes_no(f"Create {full_repo}?", default=True):
            return

        print(f"\nCreating {full_repo}...")
        if not create_repo(full_repo, private=private):
            print("❌ Failed to create repository.")
            return
        print(f"✓ Created {full_repo}")

    # Update .env
    print("\n" + "-" * 40)
    print("Updating .env file...")

    update_env_file("ISSUE_TRACKER", "github")
    update_env_file("GITHUB_REPO", full_repo)
    print("✓ Set ISSUE_TRACKER=github")
    print(f"✓ Set GITHUB_REPO={full_repo}")

    # Token setup
    print("\n" + "-" * 40)
    print("GitHub Token Setup")
    print("-" * 40)

    env_token = os.environ.get("GITHUB_TOKEN", "")
    if env_token:
        print("✓ GITHUB_TOKEN is already set in environment.")
    else:
        print("\nYou need a GitHub token with 'Issues: Read and write' permission.")
        print(f"The token only needs access to: {full_repo}")

        if prompt_yes_no("\nOpen GitHub token creation page in browser?", default=True):
            # Open fine-grained PAT page directly
            webbrowser.open("https://github.com/settings/personal-access-tokens/new")
            print("\nCreate a fine-grained PAT with these settings:")
            print("  - Required permissions: Issues → Read and write")
            print(f"  - Repository access: Only select repositories → {full_repo}")

        print("\nAfter creating the token, add it to .env:")
        print("  GITHUB_TOKEN=ghp_your_token_here")

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print("\nRun the bot with: uv run main.py")
    print(f"Issues will be created in: https://github.com/{full_repo}/issues")


def main() -> None:
    """Run interactive setup."""
    print("discord-support-agent setup")
    print("-" * 40)

    # Check for .env
    if not Path(".env").exists():
        if Path(".env.example").exists():
            print("\nNo .env file found. Creating from .env.example...")
            shutil.copy(".env.example", ".env")
            print("✓ Created .env from .env.example")
        else:
            print("\n⚠ No .env file found. Creating empty .env...")
            Path(".env").touch()

    print("\nWhat would you like to set up?")
    print("  [1] GitHub issue tracking")
    print("  [2] Exit")

    choice = input("\nChoice [1-2]: ").strip()

    if choice == "1":
        setup_github_issues()
    else:
        print("Goodbye!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(1)
