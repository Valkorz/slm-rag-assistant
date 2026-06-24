from src.ui.app import AssistantApp
from src.utils.logger import logger


def main() -> None:
    app = AssistantApp()
    app.mainloop()
    logger.dump()


if __name__ == "__main__":
    main()
