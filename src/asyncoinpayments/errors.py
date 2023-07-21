class CoinPayementsError(Exception):
    pass

class CoinPaymentsInputError(CoinPayementsError): 
    pass

class FormatError(CoinPayementsError):
    pass