"""Command-line interface bootstrap for the Regulatory Knowledge Base."""

import logging

import click
from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
load_dotenv()

from . import __version__
from .commands.core import register_core_commands
from .commands.intel import intel
from .commands.lifecycle import register_lifecycle_commands
from .config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def setup_file_logging() -> None:
    """Set up file logging if enabled."""
    if config.get("logging.file_enabled", True):
        log_file = config.logs_dir / "regkb.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(config.get("logging.format")))
        logging.getLogger().addHandler(file_handler)


@click.group()
@click.version_option(version=__version__, prog_name="regkb")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
def cli(verbose: bool) -> None:
    """Regulatory Knowledge Base - Manage and search regulatory documents."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    setup_file_logging()


cli.add_command(intel)
register_core_commands(cli)
register_lifecycle_commands(cli)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
