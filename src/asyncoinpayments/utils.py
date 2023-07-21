from typing import TypedDict
from .errors import CoinPayementsError 

class ResponseFormat:
    JSON="json"
    XML='xml'

class ApiResponseJson(TypedDict):
    error : str
    result : dict

class JsonResponse:
    
    def __init__(self, data : ApiResponseJson) -> None:

        self.error = data['error']
        self.result = data['result']

    def __str__(self):
        return f"(error: {self.error}, result: {self.error})"

    def raise_for_errors(self) -> None:
        """
        If an error accours it will be raised as CoinPaymentsError
        """
        if self.error != "ok":
            raise CoinPayementsError(self.error)