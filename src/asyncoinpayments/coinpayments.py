import aiohttp
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import hmac
import hashlib
from typing import Union
from tenacity import retry, stop_after_attempt
from .errors import CoinPayementsError,CoinPaymentsInputError,FormatError 
from .utils import ResponseFormat, JsonResponse, ApiResponseJson


class AsynCoinPayments:
    
    REQUEST_TRIES=3

    def __init__(self,private_key:str,public_key:str,version:str='1', _format:ResponseFormat = ResponseFormat.JSON, _proxy:str = None, _proxy_auth:str = None) -> None:
        
        self._private_key = private_key
        self._public_key = public_key
        self._version = version

        self.proxy=_proxy
        self._proxy_auth=_proxy_auth
        
        self.base_url='https://www.coinpayments.net/api.php'
        self._format=_format #the format of the http response can be json/xml


    def create_hmac(self, **params):
        """
        create hmac for api requests
        """
        
        encoded = urllib.parse.urlencode(params).encode('utf-8')
        #print(encoded) #to fix tx and multiple calls at once
        h=hmac.new(bytearray(self._private_key, 'utf-8'), encoded, hashlib.sha512).hexdigest()

        return encoded, h

    @retry(stop=stop_after_attempt(3)) #TODO ADD WAIT TIME MAYBE? -> hard with async and tenacity
    async def request(self, method, **params):
        """
        request handler
        """
        
        encoded, h = self.create_hmac(**params)
        headers = {'hmac' : h}
        
        async with aiohttp.ClientSession() as session:
            #TODO
            #ERROR HANDLING
            if method == 'get':
                r = await session.get(url = self.base_url, headers = headers, proxy=self.proxy, proxy_auth=self._proxy_auth)
            elif method == 'post':
                headers['Content-Type'] = 'application/x-www-form-urlencoded'
                r = await session.post(url = self.base_url, headers = headers, data = encoded, proxy=self.proxy, proxy_auth=self._proxy_auth)
            #ERRORS
            if r.status != 200:
                r.raise_for_status()
            #FORMATS
            if self._format == "json":
                response_formatted = await r.json()
            elif self._format == "xml": 
                response_formatted = await r.text()
        
        return response_formatted

    async def get(self, **params):
        """Performs a get request"""

        return await self.request(method='get',**params)

    async def post(self, **params):
        """Performs a post request"""

        return await self.request(method='post',**params)


    async def api_call(self, cmd:str, **params) -> Union[JsonResponse, str]:
        """
        perform an api call given a cmd and its parameters
        """

        base_params={
            'cmd' : cmd,
            'key':self._public_key,
            'version': self._version,
            'format': self._format
            }
        if self._format == "json":
            data : ApiResponseJson = await self.post(**base_params,**params)
            response : JsonResponse = JsonResponse(data=data)
        else:
            response: str = await self.post(**base_params,**params)
        
        return response

    ### INFORMATION COMMANDS
    async def get_basic_info(self) -> Union[JsonResponse, str]:
        """
        retrieves basic user info from the CoinPayments api

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the basic user info
        """

        cmd = 'get_basic_info'

        return await self.api_call(cmd)
    
    async def rates(self, short:bool = True, specify_accepted:bool = True, only_accepted:bool = True) -> Union[JsonResponse, str]:
        """
        retrieves rates informations from the CoinPayments api

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the currency rates informations
        """

        cmd = 'rates'

        if specify_accepted and only_accepted:
            accepted_option = 2  
        elif specify_accepted: 
            accepted_option = 1
        else: 
            accepted_option = 0

        params = {
            'short' : 1 if short else 0, 
            'accepted' : accepted_option
            }
        
        return await self.api_call(cmd, **params)
    
    ### RECEIVING PAYMENTS
    async def create_transaction(self, amount:float, buyer_email:str, receive_currency:str, base_currency:str = 'USD', ipn_url:str = None, **params) -> Union[JsonResponse, str]:
        """
        creates a cryptocurrency transaction to receive client funds

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the transaction informations
        """

        cmd='create_transaction'

        necessary_params = { 
            'amount' : amount, 
            'currency1' : base_currency,
            'currency2' : receive_currency,
            'buyer_email' : buyer_email,
            }
        
        if ipn_url:
            necessary_params |= {'ipn_url' : ipn_url}

        return await self.api_call(cmd, **necessary_params, **params)
    
    async def get_callback_address(self, currency, ipn_url:str = None, **params) -> Union[JsonResponse, str]:
        """
        retrieves basic user info from the CoinPayments api

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the callback address
        """

        necessary_params = {
            'currency' : currency,
            'ipn_url' : ipn_url
        }

        cmd = 'get_callback_address'

        return await self.api_call(cmd, **necessary_params, **params)
    
    async def get_tx_info_multi(self, txid): ...
        # TODO FIX THIS 	Lets you query up to 25 payment ID(s) (API key must belong to the seller.) 
        # Payment IDs should be separated with a | (pipe symbol.) 
    
    async def get_tx_info(self, txid:str, full:bool = False) -> Union[JsonResponse, str]:
        """
        retrieves transaction informations from the CoinPayments api

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the transaction informations
        """

        cmd = 'get_tx_info'

        params = {
            'txid' : txid,
            'full' : 1 if full else 0
        }

        return await self.api_call(cmd, **params)
    
    async def get_tx_ids(self, limit:int=25, newer_than:int = 0, **params) -> Union[JsonResponse, str]:
        """
        retrieves the ids of from your transaction history using the CoinPayments api

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the callback address
        """

        if limit > 100: limit = 100

        cmd = 'get_tx_ids'
        
        aux_params={
            'limit' : limit,
            'newer' : newer_than
        }

        return await self.api_call(cmd, **aux_params,**params)
    
    ## WALLET

    async def balances(self, all_coins:bool = False) -> Union[JsonResponse, str]:
        """
        # Retrieve the balances of your CoinPayments account

        if all_coins is set to True it will return all balances, even if they are equal to 0
        """
        cmd = 'balances'

        #api accepts only 1/0 as True/False
        params = {'all': 1 if all_coins else 0}

        return await self.api_call(cmd, **params)
    
    #EXTRA
    async def coin_balance(self, coin:str) -> Union[JsonResponse, str]:
        """
        get the current balance of a certain currency, this only works with json format

        Parameters
        ----------
        coin : str
            the currency of which the balance will be returned

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the coin balance informations

        Raises
        ------
        FormatError
            the format passed is not json
        CoinPaymentsInputError
            the user input is incorrect, the coin passed does not exists
        """

        if self._format != ResponseFormat.JSON:
            raise FormatError
        
        user_balance = await self.balances(True)
        #TODO ADD TRY BLOCK
        result = user_balance.result

        try:
            coin_balance = {'error' : 'ok', 'result' : result[coin.upper()]}
        except KeyError:
            raise CoinPaymentsInputError("This coin is not currently supported")
        else:
            return coin_balance
        
    async def get_deposit_address(self, currency:str):
        """
        get the merchant deposit address for a currency  
        currency :: str : the currency the buyer will be sending.
        """

        cmd = 'get_deposit_address'

        return await self.api_call(cmd, currency=currency)
    
    async def create_transfer(self, amount:float, currency:str , merchant_id:int, auto_confirm:bool = False, **params) -> Union[JsonResponse, str]:
        """
        create a withdrawal to another CoinPayments user

        Parameters
        ----------
        amount : float
            the amount to transfer
        currency : str
            the currency to transfer
        merchant_id : int
            the merchant id to send the funds to
        auto_confirm : bool, optional
            if set to True no 2fa will be required to confirm the command, by default False

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the transfer informations
        """

        cmd = 'create_transfer'

        necessary_params = {
            'amount' : amount,
            'currency' : currency,
            'merchant' : merchant_id,
            'auto_confirm' : auto_confirm
        }

        return await self.api_call(cmd, **necessary_params, **params)

    async def create_withdrawal(self, amount:float, receive_currency:str, base_currency:str = None, address:str = None, ipn_url: str = None, auto_confirm:bool = False, **params) -> Union[JsonResponse, str]:
        """
        create a withdrawal and send or transfer your funds to others

        Parameters
        ----------
        amount : float
            amount of base_currency to send
        receive_currency : str
            the currency the merchant will receive
        base_currency : str, optional
            the currency that determines the amount to send worth of receive_currency, by default None
        address : str, optional
            the receive_currency address, by default None
        ipn_url : str, optional
            the ipn url where the notifications will be sent, by default None
        auto_confirm : bool, optional
            if set to True 2fa won't be required, by default False

        Returns
        -------
        Union[JsonResponse, str]
            api response containing containing the withdrawal info

        Example
        -------
            `to send 18$ worth of btc, 'btc' is the receive_currency and 'usd' is the base_currency`
        """

        cmd='create_withdrawal'

        necessary_params = {
            'amount' : amount, 
            'currency' : receive_currency,
            'currency2' : base_currency,
            'ipn_url' : ipn_url,
            'auto_confirm' : 1 if auto_confirm else 0
            }

        if address != None:
            necessary_params |= {'address' : address}
        
        return await self.api_call(cmd, **necessary_params)
    
    async def create_mass_withdrawal(self, withdrawals:list):

        cmd='create_mass_withdrawal'

        # withdrawals is an associative array

    
    async def cancel_withdrawal(self, withdrawal_id:int):
        """
        Cancel a withdrawal given its id
        """

        cmd = 'cancel_withdrawal'

        return await self.api_call(cmd, id=withdrawal_id)
    
    async def convert(self, amount:float, from_currency:str, to_currency:str, to_address:str = None, **params) -> Union[JsonResponse, str]:
        """
        convert a currency to another and if passed, send it to another address

        Parameters
        ----------
        amount : float
            the amount of from_currency to convert 
        from_currency : str
            the currency to conver
        to_currency : str
            the currency to convert to
        to_address : str, optional
            the address that will receive the amount of to_currency, by default None

        Returns
        -------
        Union[JsonResponse, str]
            api response containing the convertion informations
        """

        cmd = 'convert'

        necessary_params = {
            'amount' : amount,
            'from' : from_currency,
            'to' : to_currency,
            'address' : to_address,
        }

        return await self.api_call(cmd, **necessary_params, **params)
    
    async def convert_limits(self, from_currency:str, to_currency:str):

        cmd = 'convert_limits'
        
        params={
            'from' : from_currency,
            'to' : to_currency
        }

        return await self.api_call(cmd, **params)
    
    async def get_withdrawal_history(self, limit:int = 25, newer_than:int = 0, **params):

        cmd = 'get_withdrawal_history'
    
        aux_params = {
            'limit' : limit,
            'newer' : newer_than
        }

        return await self.api_call(cmd, **aux_params, **params)
    
    async def get_withdrawal_info(self, withdrawal_id:int):

        cmd = 'get_withdrawal_info'

        return await self.api_call(cmd, id=withdrawal_id)

    async def get_conversion_info(self, conversion_id):

        cmd = 'get_conversion_info'

        return await self.api_call(cmd, id=conversion_id)
    
    ## $PayByName

    async def get_pbn_info(self, pbntag:str):
        """pbntag : tag to get information for, such as $CoinPayments or $Alex. Can be with or without a $ at the beginning."""

        cmd = 'get_pbn_info'

        return await self.api_call(cmd, pbntag = pbntag)
    
    async def get_pbn_list(self):

        cmd = 'get_pbn_list'

        return await self.api_call(cmd)
    
    async def buy_pbn_tags(self, coin:str, num:int = 1):
        """
        # Buy $PayByName Tag(s)
        Buy 1 or more pbn tags

        coin : the coin to buy the tags with
        num : the number of tags to buy, if not passed is set to 1
        """

        cmd = 'buy_pbn_tags'

        params = {
            'coin' : coin,
            'num' : num
        }

        return await self.api_call(cmd, **params)
    
    async def claim_pbn_tag(self, tag_id:int, name:str):

        cmd = 'claim_pbn_tag'

        params = {
            'tagid' : tag_id,
            'name' : name
        }
    
        return await self.api_call(cmd, **params)
    
    async def update_pbn_tag(self,tag_id:int, **params):
        """
        # Update your pbn tag info
        Update a pbn tag given its id

        In the params you can pass 
        - name : Name for the profile. If field is not supplied the current name will be unchanged.
        - email	: email for the profile. If field is not supplied the current email will be unchanged.
        - url : website URL for the profile. If field is not supplied the current URL will be unchanged.
        - image	: JPG or PNG image 250KB or smaller, the image data should be base64 encoded.
        Use an empty string to remove profile image. If field is not supplied the current image will be unchanged.
        """

        cmd = 'update_pbn_tag'

        return await self.api_call(cmd, tagid=tag_id, **params)
    
    async def renew_pbn_tag(self, tag_id:int, coin:str, years:int = 1):

        cmd = 'renew_pbn_tag'

        params = {
            'tagid' : tag_id,
            'coin' : coin,
            'years' : years
        }

        return await self.api_call(cmd, **params)
    
    async def delete_pbn_tag(self, tag_id:int):

        cmd = 'delete_pbn_tag'

        return await self.api_call(cmd, tagid=tag_id)

    async def claim_pbn_coupon(self, coupon:str):

        cmd = 'claim_pbn_coupon'

        return await self.api_call(cmd, coupon=coupon) 
   
    #EXTRA
    async def get_accepted_list(self, fiat_included:bool = True) -> list:

        api_response = await self.rates()
        accepted_currencies = self.json_to_result(api_response)

        if not fiat_included:
            accepted_list = [c for c in accepted_currencies if accepted_currencies[c]['is_fiat'] == 0]
        else:
            accepted_list = [c for c in accepted_currencies]
        
        return accepted_list

    async def is_accepted(self, currency:str, fiat_included: bool = True) -> bool:
        """
        Check if a currency is accepted by the merchant 

        Parameters
        ----------
        currency : str
            The currency that needs to be checked
        fiat_included : bool, optional
            If the command should accept fiat currencies as an input, by default True

        Returns
        -------
        bool
            True if the currency passed is accepted by the merchant else False
        """
        currency = currency.upper()
        api_response = await self.rates()
        accepted_currencies = self.json_to_result(api_response)

        if not fiat_included:
            accepted_currencies = {c : 'accepted' for c in accepted_currencies if accepted_currencies[c]['is_fiat'] == 0}
        
        try:
            accepted_currencies[currency]
            return True
        except KeyError:
            return False

    async def get_balance_accepted(self) -> dict:
        """
        Get the balance of the accepted currencies by the merchant

        Returns
        -------
        dict
            a dictionary cointaining the currency as the key and its balance as the value

        """

        accepted = await self.get_accepted_list()
        balances = self.json_to_result(await self.balances())
        accepted_balances = {}

        for coin in accepted:
            
            balance = balances[coin]['balancef']    
            accepted_balances |= {coin: balance}
        
        return accepted_balances
    
    async def conversion_fiat(self, coin1:str, base_currency:str, from_data:dict = None) -> float:
        """
        Get the conversion rate in a fiat currency of any currency accepted by CoinPayments

        Parameters
        ----------
        coin1 : str
            The coin that we want the conversion rate of 
        base_currency : str
            The currency, should be fiat, against which we want to compare coin1
        from_data : dict, optional
            A previous cached call of the rates endpoint if not passed an api call to said endpoint will be made, by default None

        Returns
        -------
        float
            The exchange rate 

        Raises
        ------
        CoinPaymentsInputError
            If the currencies passed do not exist or are not accepted by CoinPayments
        """
        if from_data:
            rates = from_data
        else:
            rates = self.json_to_result(await self.rates())
        
        coin1 = coin1.upper()
        base_currency = base_currency.upper()

        try:
            coin1_btc = float(rates[coin1]['rate_btc'])
            base_currency_btc = float(rates[base_currency]['rate_btc'])
        except KeyError:
            raise CoinPaymentsInputError("User input is incorrect")
        
        rate = coin1_btc/base_currency_btc
        return rate
    
    async def balances_fiat(self, base_currency:str = 'USD', only_accepted:bool = False, all_coins:bool = False) -> dict:
        """
        Get the merchant's balances converted in a set base currency

        Parameters
        ----------
        base_currency : str, optional
            The currency in which the merchant balance will be returned, by default 'USD'
        only_accepted : bool, optional
            If set to True the function will return only the balances of the merchant's accepted coins, by default False
        all_coins : bool, optional
            If set to True the function will return all balances, even if empty, by default False

        Returns
        -------
        dict
            A dictionary containing the merchant's coin balances converted in the base currency
        """

        new_balances = {}

        balances = self.json_to_result(await self.balances(all_coins = all_coins))
        #we call this function once and cache the result
        rates = self.json_to_result(await self.rates(only_accepted = only_accepted))

        for coin in rates:
            
            try:
                exchangerate = await self.conversion_fiat(coin1 = coin, base_currency = base_currency, from_data = rates)
                coin_balance = float(balances[coin]['balancef'])
            except KeyError:
                continue
            except CoinPayementsError:
                continue
            else:
                new_balances |= {coin : exchangerate*coin_balance}

        return new_balances

