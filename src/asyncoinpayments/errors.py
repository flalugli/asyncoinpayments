class CoinPayementsError(BaseException):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class CoinPaymentsInputError(CoinPayementsError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class FormatError(CoinPayementsError):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
