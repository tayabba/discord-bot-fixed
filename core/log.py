class Logger:
    @staticmethod
    def success(message: str):
        print(f"[SUCCESS] {message}")

    @staticmethod
    def error(message: str):
        print(f"[ERROR] {message}")

    @staticmethod
    def info(message: str):
        print(f"[INFO] {message}")
