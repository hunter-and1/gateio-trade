# coding: utf-8
import time
import gate_api
from threading import Thread
from gate_api.exceptions import ApiException, GateApiException

configuration = gate_api.Configuration(
    host = "https://api.gateio.ws/api/v4",
    key = "",
    secret = "",
)
api_client = gate_api.ApiClient(configuration)
api_spot = gate_api.SpotApi(api_client)

class BotBuyCurrency(object):
    def __init__(self):
        #Modifibale
        self._currency_pair = '_USDT'
        self._type_using = 'price'
        self._buy_price = 10 # price u want invist
        self._buy_amount = None
        self._price_percent_start = 0.52 # incrrcy by 52% from start
        self._price_percent = 0.02 # incrrcy by 2% from start
        self._price_format = "{:.5f}" # number dig for small coins
        self._start_price = 0.2 # set 0 for disable max price
        self._max_price_leave = 0.4 # set 0 for disable max price
        self._delay_end = 3
        self._time_to_skip_start = 1.9 # time to go get price seconds
        self._side = 'buy'
        self._delay_loop = 0.1 # 0 to disable

        #NoChange
        currency_buy = api_spot.get_currency_pair(self._currency_pair)
        self._buyDateStart = currency_buy.buy_start
        self._buyDateEnd = self._buyDateStart + self._delay_end

        print("Target : "+str(self._buyDateStart))

        self._loop = True
        self._thread = None
        self._priceCalu = 0
        self._amountFinal = 0
        self._prevPriceCalu = 0

    def Stop(self):#
        self._loop = False

    def SetThread(self,t):
        self._thread = t

    def SetPrice(self,price):
        self._priceCalu = price

    def UpdatePrice(self,percent):
        self._priceCalu = float(self._priceCalu) + (float(self._priceCalu) * float(percent))

    def UpdateAmount(self):
        self._amountFinal = self._buy_price / self._priceCalu
        self._priceCalu = self._price_format.format(self._priceCalu)

    def ResponseOrder(self):
        order_response = self._thread.get()
        print("ResponseOrder#"+str(order_response.id)+" : "+str(time.time()))
        if(order_response.status == 'closed'):
            self._loop = False
        else:
            print(order_response)
    
    def ReturnOrder(self):
        print("Price Calcu: "+str(self._priceCalu));
        self._prevPriceCalu = self._priceCalu
        return gate_api.Order(currency_pair=self._currency_pair, type='limit', account='spot', side=self._side, iceberg='0',amount=self._amountFinal,price=self._priceCalu,time_in_force="ioc",auto_borrow=False)

def main():
    try:
        botBuyCurrency = BotBuyCurrency()
        t = 1
        while botBuyCurrency._loop:
            
            if(time.time() >= botBuyCurrency._buyDateStart):
                if(botBuyCurrency._buyDateStart + botBuyCurrency._time_to_skip_start > time.time()):
                    print("Start-INIT#"+str(t)+" : "+str(time.time()))
                    if(botBuyCurrency._prevPriceCalu == 0):
                        botBuyCurrency.SetPrice(botBuyCurrency._start_price)
                        botBuyCurrency.UpdatePrice(botBuyCurrency._price_percent_start)
                    else:
                        botBuyCurrency.SetPrice(botBuyCurrency._prevPriceCalu)
                        botBuyCurrency.UpdatePrice(botBuyCurrency._price_percent)
                else:
                    print("Start-GET#"+str(t)+" : "+str(time.time()))
                    currency_tickers = api_spot.list_tickers(currency_pair=botBuyCurrency._currency_pair)
                    if(float(currency_tickers[0].last) != 0):
                        botBuyCurrency.SetPrice(float(currency_tickers[0].last))
                        botBuyCurrency.UpdatePrice(botBuyCurrency._price_percent)

                botBuyCurrency.UpdateAmount()

                if(botBuyCurrency._max_price_leave != 0 and float(botBuyCurrency._priceCalu) >= botBuyCurrency._max_price_leave):
                    print("Stop#"+str(t)+" : "+str(time.time())+" Get MAX")
                    break

                print("Order#"+str(t)+" : "+str(time.time()))
                thread_res = api_spot.create_order(botBuyCurrency.ReturnOrder(), async_req=True)
                botBuyCurrency.SetThread(thread_res)
                thread = Thread(target = botBuyCurrency.ResponseOrder)
                thread.start()
                if(botBuyCurrency._delay_loop != 0):
                    time.sleep(botBuyCurrency._delay_loop)
            t += 1
            if(time.time() > botBuyCurrency._buyDateEnd):
                break
        print("Count Loop in Time : "+str(t))

    except GateApiException as ex:
        print("Gate api exception, label: %s, message: %s\n" % (ex.label, ex.message))
    except ApiException as e:
        print("Exception when calling get_currency_pair: %s\n" % e)
        
if __name__ == "__main__":
    main()