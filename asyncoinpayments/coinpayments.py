import aiohttp
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import hmac
import hashlib
from tenacity import retry, stop_after_attempt
from .errors import CoinPayementsError,CoinPaymentsInputError,FormatError 
from .utils import ResponseFormat


class AsyncCoinPayments:
    
    REQUEST_TRIES=3

    def __init__(self,_private_key:str,_public_key:str,_version:str='1', _format:ResponseFormat = ResponseFormat.JSON, _proxy:str = None, _proxy_auth:str = None) -> None:
        
        self._private_key = _private_key
        self._public_key = _public_key
        self._version = _version

        self.proxy=_proxy
        self._proxy_auth=_proxy_auth
        
        self.base_url='https://www.coinpayments.net/api.php'
        self._format=_format #the format of the http response can be json/xml


    def create_hmac(self, **params):
        """ ## Generate an HMAC from the url arguments
            
            ### Note  

            hmac on both sides depends from the order of the parameters, any
            change in the order and the hmacs wouldn't match hence the api request would be invalid
        """
        encoded = urllib.parse.urlencode(params).encode('utf-8')
        #print(encoded) #to fix tx and multiple calls at once
        h=hmac.new(bytearray(self._private_key, 'utf-8'), encoded, hashlib.sha512).hexdigest()

        return encoded, h

    @retry(stop=stop_after_attempt(3)) #TODO ADD WAIT TIME MAYBE? -> hard with async and tenacity
    async def request(self, method, **params):
        
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

    def json_to_result(self, json_response:dict):
        """
        Pass a json response from the api

        ## Raises 
        CoinPayementsError
        """

        error=json_response['error']
        if error == 'ok':
            return json_response['result']
        else:
            raise CoinPayementsError(error)

    async def api_call(self, cmd:str, **params):

        base_params={
            'cmd' : cmd,
            'key':self._public_key,
            'version': self._version,
            'format': self._format
            }
        
        return await self.post(**base_params,**params)


    ### INFORMATION COMMANDS
    async def get_basic_info(self):
        """# Get basic informations"""

        cmd = 'get_basic_info'

        return await self.api_call(cmd)
    
    async def rates(self, short:bool = True, specify_accepted:bool = True, only_accepted:bool = True):
        """specify_accepted	: 
        - The response will include if you have the coin enabled for acceptance on your Coin Acceptance Settings page.

        only_accepted:
        - The response will include all fiat coins but only cryptocurrencies enabled for acceptance on your Coin Acceptance Settings page."""

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
    async def create_transaction(self, amount:float, buyer_email:str, receive_currency:str, base_currency:str = 'USD', ipn_url:str = None, **params):
        """# Create a CoinPayment transaction
        
        receive_currency : the currency you will receive   
        if you want to handle refund yourself set buyer_email to your own email
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
    
    async def get_callback_address(self, currency, ipn_url:str = None, **params):
        """add docu"""

        necessary_params = {
            'currency' : currency,
            'ipn_url' : ipn_url
        }

        cmd = 'get_callback_address'

        return await self.api_call(cmd, **necessary_params, **params)
    
    async def get_tx_info_multi(self, txid): ...
        # TODO FIX THIS 	Lets you query up to 25 payment ID(s) (API key must belong to the seller.) 
        # Payment IDs should be separated with a | (pipe symbol.) 
    
    async def get_tx_info(self, txid:str, full:bool = False):
        """add docu"""

        cmd = 'get_tx_info'

        params = {
            'txid' : txid,
            'full' : 1 if full else 0
        }

        return await self.api_call(cmd, **params)
    
    async def get_tx_ids(self, limit:int=25, newer_than:int = 0, **params):
        """
        max limit is 100, if greater than that it will be set to 100
        newer_than return payments started at the given Unix timestamp or later
        """

        if limit > 100: limit = 100

        cmd = 'get_tx_ids'
        
        aux_params={
            'limit' : limit,
            'newer' : newer_than
        }

        return await self.api_call(cmd, **aux_params,**params)
    
    ## WALLET

    async def balances(self, all_coins:bool = False):
        """
        # Retrieve the balances of your CoinPayments account

        if all_coins is set to True it will return all balances, even if they are equal to 0
        """
        cmd = 'balances'

        #api accepts only 1/0 as True/False
        params = {'all': 1 if all_coins else 0}

        return await self.api_call(cmd, **params)
    
    #EXTRA
    async def coin_balance(self, coin:str):

        if self._format != ResponseFormat.JSON:
            raise FormatError
        
        user_balance = await self.balances(True)
        #TODO ADD TRY BLOCK
        result = self.json_to_result(user_balance)

        try:
            coin_balance = {'error' : 'ok', 'result' : result[coin.upper()]}
        except KeyError:
            raise CoinPaymentsInputError("This coin is not currently supported")
        else:
            return coin_balance
        
    async def get_deposit_address(self, currency:str):
        """currency : the currency the buyer will be sending."""

        cmd = 'get_deposit_address'

        return await self.api_call(cmd, currency=currency)
    
    async def create_transfer(self, amount:float, currency:str , merchant_id:int, auto_confirm:bool = False, **params):

        cmd = 'create_transfer'

        necessary_params = {
            'amount' : amount,
            'currency' : currency,
            'merchant' : merchant_id,
            'auto_confirm' : auto_confirm
        }

        return await self.api_call(cmd, **necessary_params, **params)

    async def create_withdrawal(self, amount:float, receive_currency:str, base_currency:str = None, address:str = None, ipn_url: str = None, auto_confirm:bool = False, **params):
        """
        # Create a withdrawal from your funds
    
        if you do not pass the address you need to pass a paytag or an Unstoppable Domain
        to send your funds to

        receive_currency is the currency you will receive, while if you set a base currency 
        'amount' of 'base_currency' will be sent in 'currency' 

        Example: `to send 18$ worth of btc, 'btc' is the receive_currency and 'usd' is the base_currency`

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
        # Cancel a withdrawal
        Cancel a withdrawal given its id
        """

        cmd = 'cancel_withdrawal'

        return await self.api_call(cmd, id=withdrawal_id)
    
    async def convert(self, amount:float, from_currency:str, to_currency:str, to_address:str = None, **params):
        """
        # Convert coins
        Convert your coins and send them to a new address or your own if to_address is set to None
        """

        cmd = 'convert'

        necessary_params = {
            'amount' : amount,
            'from' : from_currency,
            'to' : to_address,
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

    async def get_balance_accepted(self):
        """get the balance as a floating of your accepted currencies"""

        accepted = await self.get_accepted_list()
        balances = self.json_to_result(await self.balances())
        accepted_balances = {}

        for coin in accepted:
            try:
                balance = balances[coin]['balancef']    
                accepted_balances |= {coin: balance}
            except KeyError:
                raise CoinPaymentsInputError("User input is incorrect")
        
        return accepted_balances
    
    async def conversion_fiat(self, coin1:str, base_currency:str, from_data:dict = None):
        """
        Returns the conversion rate of any available currency on the site. This is recomended to use only if needed.
        ### Note
        The conversion rate might be a bit imprecise depending on how recently the rates endpoint has been updated
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
    
    async def balances_fiat(self, base_currency:str = 'USD', only_accepted:bool = False, all_coins:bool = False):
        "Returns the amount of cryptocurrency in your wallet against the base coin"

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

