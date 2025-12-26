from typing import List

class SafetyLayer:
    SENSITIVE_KEYWORDS = ["hack", "exploit", "ignore instructions"]

    @classmethod
    def check_input(cls, text: str) -> bool:
        """
        Returns True if safe, False if unsafe.
        """
        for keyword in cls.SENSITIVE_KEYWORDS:
            if keyword in text.lower():
                return False
        return True

    @classmethod
    def check_output(cls, text: str) -> bool:
        return True
