# !/usr/bin/env python
# coding: utf-8

import hashlib
import hmac
import json
import logging
import time
import sys
import gate_api
from gate_api.exceptions import ApiException, GateApiException
from threading import Thread

# pip install -U websocket_client
from websocket import WebSocketApp

class GateWebSocketApp(WebSocketApp):

    def __init__(self, url, api_key, api_secret, **kwargs):
        super(GateWebSocketApp, self).__init__(url, **kwargs)

        self._api_key = api_key
        self._api_secret = api_secret

    def _send_ping(self, interval, event, payload):
        while not event.wait(interval):
            self.last_ping_tm = time.time()
            if self.sock:
                try:
                    self.sock.ping(payload)
                except Exception as ex:
                    print("send_ping routine terminated: {}".format(ex))
                    break
                try:
                    self._request("spot.ping", auth_required=False)
                except Exception as e:
                    raise e

    def _request(self, channel, event=None, payload=None, auth_required=True):
        current_time = int(time.time())
        data = {
            "time": current_time,
            "channel": channel,
            "event": event,
            "payload": payload,
        }
        if auth_required:
            message = 'channel=%s&event=%s&time=%d' % (channel, event, current_time)
            data['auth'] = {
                "method": "api_key",
                "KEY": self._api_key,
                "SIGN": self.get_sign(message),
            }
        data = json.dumps(data)
        print('request: %s', data)
        self.send(data)

    def get_sign(self, message):
        h = hmac.new(self._api_secret.encode("utf8"), message.encode("utf8"), hashlib.sha512)
        return h.hexdigest()

    def subscribe(self, channel, payload=None, auth_required=True):
        self._request(channel, "subscribe", payload, auth_required)

    def unsubscribe(self, channel, payload=None, auth_required=True):
        self._request(channel, "unsubscribe", payload, auth_required)

class ConfigBot:

    def __init__(self):
        #CHAGED
        self._key = ''
        self._secret = ''
        self._currency_pair = ''
        self._type_using = 'price'

        self._number_attempt_buy = 5
        self._buy_price = 5 # price u want invist
        self._buy_price_percent = 0.09
        self._buy_price_percent_loop = 0.1
        self._sell_enable = False
        self._sell_price_percent = 0.01
        self._delay_between_buy_sell = 1.2

        #NOT CHAGED
        self._is_buy = False
        self._max_buy_price = 0
        self._amount_buyed = 0
        self._sell_info = None
        self._thread = None

        self._api_client = gate_api.ApiClient(gate_api.Configuration(
            host = "https://api.gateio.ws/api/v4",
            key = self._key,
            secret = self._secret,
        ))
        self._api_spot = gate_api.SpotApi(self._api_client)
        
        currency_buy = self._api_spot.get_currency_pair(self._currency_pair)
        if(currency_buy.buy_start == 0):
            sys.exit("this currency pair deja started!")
        self._buy_time_start = currency_buy.buy_start
        self._precision = "{:."+str(currency_buy.precision)+"f}"
        
        self._time_to_sell = self._delay_between_buy_sell + self._buy_time_start


    def get_currency_pair(self):
        return self._currency_pair

    def sell_enable(self):
        return self._sell_enable

    def number_attempt_buy(self):
        return self._number_attempt_buy

    def buy_price_percent_loop(self):
        return self._buy_price_percent_loop

    def increment_percent(self,number):
        self._buy_price_percent = self._buy_price_percent + number

    def price_for_buy(self,price):
        return price + (price * float(self._buy_price_percent))

    def price_for_sell(self,price):
        return price - (price * float(self._sell_price_percent))

    def is_buy(self):
        return self._is_buy

    def key(self):
        return self._key

    def secret(self):
        return self._secret

    def time_to_start_buy(self):
        return self._buy_time_start

    def time_to_sell(self):
        return self._time_to_sell

    def sell_info(self):
        return self._sell_info

    def currency_pair(self):
        return self._currency_pair

    def max_buy_price(self):
        return self._max_buy_price

    def response_order_buy(self,t):
        print("response_order_buy")
        order_response = t.get()

        print("ResponseBuyOrder : "+str(time.time()))
        print('\tstatus : '+str(order_response.status))
        print('\tprice :'+str(order_response.price))
        print('\tamount :'+str(order_response.amount))
        print('\tcurrency_pair :'+str(order_response.currency_pair))
        print('\tcreate_time :'+str(order_response.create_time))
        print('\tcreate_time_ms :'+str(order_response.create_time_ms))

        if(order_response.status == 'closed'):
            if(self._max_buy_price < float(order_response.price)):
                self._max_buy_price = float(order_response.price)
            self._is_buy = True
            self._amount_buyed = self._amount_buyed + float(order_response.amount)

    """
    def create_order_for_buy(self,price):
        print("Create Order Buy: "+str(time.time()))
        _amount_final = self._buy_price / price
        _price_buyed = self._precision.format(price)

        Order = gate_api.Order(currency_pair=self._currency_pair, type='limit', account='spot',side='buy', iceberg='0',amount=_amount_final,price=_price_buyed,time_in_force="ioc",auto_borrow=False)
        
        thread_res = self._api_spot.create_order(Order, async_req=True)
        thread = Thread(target = self.response_order_buy,args=(thread_res,))
        thread.start()
    """
    def create_orders_for_buy(self,_price_buy):
        self.increment_percent(self.buy_price_percent_loop() * -1)
        for i in range(1,int(self.number_attempt_buy() + 1)):
            print("Create Order Buy: "+str(time.time()))
            print('attemp buy '+str(i))

            self.increment_percent(self.buy_price_percent_loop())
            _price_for_buy = self.price_for_buy(_price_buy)
            _amount_final = self._buy_price / _price_for_buy
            _price_buyed = self._precision.format(_price_for_buy)

            Order = gate_api.Order(currency_pair=self._currency_pair, type='limit', account='spot',side='buy', iceberg='0',amount=_amount_final,price=_price_buyed,time_in_force="ioc",auto_borrow=False)
            
            thread_res = self._api_spot.create_order(Order, async_req=True)
            thread = Thread(target = self.response_order_buy,args=(thread_res,))
            thread.start()

    def create_order_for_sell(self,price):
        try:
            print("Create Order Sell: "+str(time.time()))
            _price_selled = self._precision.format(price)
            Order = gate_api.Order(currency_pair=self._currency_pair, type='limit', account='spot',side='sell', iceberg='0',amount=str(self._amount_buyed),price=_price_selled,time_in_force="ioc",auto_borrow=False)
            
            order_response = self._api_spot.create_order(Order)
            print("ResponseSellOrder : "+str(time.time()))
            print('\tstatus : '+str(order_response.status))
            print('\tprice :'+str(order_response.price))
            print('\tamount :'+str(order_response.amount))
            print('\tcurrency_pair :'+str(order_response.currency_pair))
            print('\tcreate_time :'+str(order_response.create_time))
            print('\tcreate_time_ms :'+str(order_response.create_time_ms))

            return order_response

        except GateApiException as ex:
            print("Gate api exception, label: %s, message: %s\n" % (ex.label, ex.message))
        except ApiException as e:
            print("Exception when calling get_currency_pair: %s\n" % e)

configBot = ConfigBot()

def on_message(ws, message):
    message = json.loads(message)

    if(message['event'] == 'subscribe'):
        print("Coin : "+str(configBot.get_currency_pair()))
        print("status: {}".format(message['result']['status']))

    elif(message['event'] == 'update'):
        # b 	String 	best bid price // to buy
        # a 	String 	best ask price // to sell    
        print("Time ("+str(time.time())+") : "+" -  buy : "+message['result']['b']+" / sell :"+message['result']['a'])
        
        if(configBot.is_buy() == False and message['result']['b'] != "" and float(message['result']['b']) != 0):
            if(int(configBot.time_to_start_buy()) <= time.time() and int(configBot.time_to_sell()) > time.time()):
                _price_buy = float(message['result']['b'])
                configBot.create_orders_for_buy(_price_buy)
                if(configBot.sell_enable() == False):
                    ws.close()
                    sys.exit("is buy without sell")


        elif(configBot.is_buy() == True):
            if(configBot.sell_enable() == False):
                ws.close()
                sys.exit("is buy without sell")
            if(int(configBot.time_to_sell()) <= time.time()):
                _price_sell = float(message['result']['a'])
                print('attemp sell 1')
                _price_for_sell = configBot.price_for_sell(_price_sell)
                if(_price_for_sell > configBot.max_buy_price()):
                    order_response = configBot.create_order_for_sell(_price_for_sell)
                    if(order_response.status == 'closed'):
                        ws.close()
                        sys.exit("is buy and sell")


def on_open(ws):
    print('websocket connected')
    ws.subscribe("spot.book_ticker", [configBot.currency_pair()], False)

if __name__ == "__main__":
    app = GateWebSocketApp("wss://api.gateio.ws/ws/v4/",
        configBot.key(),
        configBot.secret(),
        on_open=on_open,
        on_message=on_message)
    app.run_forever(ping_interval=30)
