New Order(TRADE)
API Description
Send in a new order.

HTTP Request
POST /fapi/v1/order

Request Weight
1 on 10s order rate limit(X-MBX-ORDER-COUNT-10S); 1 on 1min order rate limit(X-MBX-ORDER-COUNT-1M); 0 on IP rate limit(x-mbx-used-weight-1m)

Request Parameters
Name Type Mandatory Description
symbol STRING YES
side ENUM YES
positionSide ENUM NO Default BOTH for One-way Mode ; LONG or SHORT for Hedge Mode. It must be sent in Hedge Mode.
type ENUM YES
timeInForce ENUM NO
quantity DECIMAL NO
reduceOnly STRING NO "true" or "false". default "false". Cannot be sent in Hedge Mode
price DECIMAL NO
newClientOrderId STRING NO A unique id among open orders. Automatically generated if not sent. Can only be string following the rule: ^[\.A-Z\:/a-z0-9_-]{1,36}$
newOrderRespType ENUM NO "ACK", "RESULT", default "ACK"
priceMatch ENUM NO only avaliable for LIMIT/STOP/TAKE_PROFIT order; can be set to OPPONENT/ OPPONENT_5/ OPPONENT_10/ OPPONENT_20: /QUEUE/ QUEUE_5/ QUEUE_10/ QUEUE_20; Can't be passed together with price
selfTradePreventionMode ENUM NO EXPIRE_TAKER:expire taker order when STP triggers/ EXPIRE_MAKER:expire taker order when STP triggers/ EXPIRE_BOTH:expire both orders when STP triggers; default EXPIRE_MAKER
goodTillDate LONG NO order cancel time for timeInForce GTD, mandatory when timeInforce set to GTD; order the timestamp only retains second-level precision, ms part will be ignored; The goodTillDate timestamp must be greater than the current time plus 600 seconds and smaller than 253402300799000
recvWindow LONG NO
timestamp LONG YES
Additional mandatory parameters based on type:

Type Additional mandatory parameters
LIMIT timeInForce, quantity, price
MARKET quantity
If newOrderRespType is sent as RESULT :
MARKET order: the final FILLED result of the order will be return directly.
LIMIT order with special timeInForce: the final status result of the order(FILLED or EXPIRED) will be returned directly.
selfTradePreventionMode is only effective when timeInForce set to IOC or GTC or GTD.
In extreme market conditions, timeInForce GTD order auto cancel time might be delayed comparing to goodTillDate
Response Example
{
  "clientOrderId": "testOrder",
  "cumQty": "0",
  "cumQuote": "0",
  "executedQty": "0",
  "orderId": 22542179,
  "avgPrice": "0.00000",
  "origQty": "10",
  "price": "0",
   "reduceOnly": false,
   "side": "BUY",
   "positionSide": "SHORT",
   "status": "NEW",
   "stopPrice": "9300",  // please ignore when order type is TRAILING_STOP_MARKET
   "closePosition": false,   // if Close-All
   "symbol": "BTCUSDT",
   "timeInForce": "GTD",
   "type": "TRAILING_STOP_MARKET",
   "origType": "TRAILING_STOP_MARKET",
  "updateTime": 1566818724722,
  "workingType": "CONTRACT_PRICE",
  "priceProtect": false,      // if conditional order trigger is protected
  "priceMatch": "NONE",              //price match mode
  "selfTradePreventionMode": "NONE", //self trading preventation mode
  "goodTillDate": 1693207680000      //order pre-set auot cancel time for TIF GTD order
}

Place Multiple Orders(TRADE)
API Description
Place Multiple Orders

HTTP Request
POST /fapi/v1/batchOrders

Request Weight
5 on 10s order rate limit(X-MBX-ORDER-COUNT-10S); 1 on 1min order rate limit(X-MBX-ORDER-COUNT-1M); 5 on IP rate limit(x-mbx-used-weight-1m);

Request Parameters
Name Type Mandatory Description
batchOrders LIST<JSON> YES order list. Max 5 orders
recvWindow LONG NO
timestamp LONG YES
Where batchOrders is the list of order parameters in JSON

Example: /fapi/v1/batchOrders?batchOrders=[{"type":"LIMIT","timeInForce":"GTC",
"symbol":"BTCUSDT","side":"BUY","price":"10001","quantity":"0.001"}]
Name Type Mandatory Description
symbol STRING YES
side ENUM YES
positionSide ENUM NO Default BOTH for One-way Mode ; LONG or SHORT for Hedge Mode. It must be sent with Hedge Mode.
type ENUM YES
timeInForce ENUM NO
quantity DECIMAL YES
reduceOnly STRING NO "true" or "false". default "false".
price DECIMAL NO
newClientOrderId STRING NO A unique id among open orders. Automatically generated if not sent. Can only be string following the rule: ^[\.A-Z\:/a-z0-9_-]{1,36}$
newOrderRespType ENUM NO "ACK", "RESULT", default "ACK"
priceMatch ENUM NO only avaliable for LIMIT/STOP/TAKE_PROFIT order; can be set to OPPONENT/ OPPONENT_5/ OPPONENT_10/ OPPONENT_20: /QUEUE/ QUEUE_5/ QUEUE_10/ QUEUE_20; Can't be passed together with price
selfTradePreventionMode ENUM NO EXPIRE_TAKER:expire taker order when STP triggers/ EXPIRE_MAKER:expire taker order when STP triggers/ EXPIRE_BOTH:expire both orders when STP triggers; default NONE
goodTillDate LONG NO order cancel time for timeInForce GTD, mandatory when timeInforce set to GTD; order the timestamp only retains second-level precision, ms part will be ignored; The goodTillDate timestamp must be greater than the current time plus 600 seconds and smaller than 253402300799000
Paremeter rules are same with New Order
Batch orders are processed concurrently, and the order of matching is not guaranteed.
The order of returned contents for batch orders is the same as the order of the order list.
Response Example
[
 {
   "clientOrderId": "testOrder",
   "cumQty": "0",
   "cumQuote": "0",
   "executedQty": "0",
   "orderId": 22542179,
   "avgPrice": "0.00000",
   "origQty": "10",
   "price": "0",
    "reduceOnly": false,
    "side": "BUY",
    "positionSide": "SHORT",
    "status": "NEW",
    "stopPrice": "0",
   "closePosition": false,
    "symbol": "BTCUSDT",
    "timeInForce": "GTC",
    "type": "TRAILING_STOP_MARKET",
    "origType": "TRAILING_STOP_MARKET",
    "updateTime": 1566818724722,
   "workingType": "CONTRACT_PRICE",
   "priceProtect": false,      // if conditional order trigger is protected
  "priceMatch": "NONE",              //price match mode
  "selfTradePreventionMode": "NONE", //self trading preventation mode
  "goodTillDate": 1693207680000      //order pre-set auto cancel time for TIF GTD order
 },
 {
  "code": -2022,
  "msg": "ReduceOnly Order is rejected."
 }
]
Modify Order (TRADE)
API Description
Order modify function, currently only LIMIT order modification is supported, modified orders will be reordered in the match queue

HTTP Request
PUT /fapi/v1/order

Request Weight
1 on 10s order rate limit(X-MBX-ORDER-COUNT-10S); 1 on 1min order rate limit(X-MBX-ORDER-COUNT-1M); 0 on IP rate limit(x-mbx-used-weight-1m)

Request Parameters
Name Type Mandatory Description
orderId LONG NO
origClientOrderId STRING NO
symbol STRING YES
side ENUM YES SELL, BUY
quantity DECIMAL YES Order quantity, cannot be sent with closePosition=true
price DECIMAL YES
priceMatch ENUM NO only avaliable for LIMIT/STOP/TAKE_PROFIT order; can be set to OPPONENT/ OPPONENT_5/ OPPONENT_10/ OPPONENT_20: /QUEUE/ QUEUE_5/ QUEUE_10/ QUEUE_20; Can't be passed together with price
recvWindow LONG NO
timestamp LONG YES
Either orderId or origClientOrderId must be sent, and the orderId will prevail if both are sent.
Both quantity and price must be sent, which is different from dapi modify order endpoint.
When the new quantity or price doesn't satisfy PRICE_FILTER / PERCENT_FILTER / LOT_SIZE, amendment will be rejected and the order will stay as it is.
However the order will be cancelled by the amendment in the following situations:
when the order is in partially filled status and the new quantity <= executedQty
When the order is GTX and the new price will cause it to be executed immediately
One order can only be modfied for less than 10000 times
Response Example
{
  "orderId": 20072994037,
  "symbol": "BTCUSDT",
  "pair": "BTCUSDT",
  "status": "NEW",
  "clientOrderId": "LJ9R4QZDihCaS8UAOOLpgW",
  "price": "30005",
  "avgPrice": "0.0",
  "origQty": "1",
  "executedQty": "0",
  "cumQty": "0",
  "cumBase": "0",
  "timeInForce": "GTC",
  "type": "LIMIT",
  "reduceOnly": false,
  "closePosition": false,
  "side": "BUY",
  "positionSide": "LONG",
  "stopPrice": "0",
  "workingType": "CONTRACT_PRICE",
  "priceProtect": false,
  "origType": "LIMIT",
    "priceMatch": "NONE",              //price match mode
    "selfTradePreventionMode": "NONE", //self trading preventation mode
    "goodTillDate": 0,                 //order pre-set auot cancel time for TIF GTD order
  "updateTime": 1629182711600
}
Modify Multiple Orders(TRADE)
API Description
Modify Multiple Orders (TRADE)

HTTP Request
PUT /fapi/v1/batchOrders

Request Weight
5 on 10s order rate limit(X-MBX-ORDER-COUNT-10S); 1 on 1min order rate limit(X-MBX-ORDER-COUNT-1M); 5 on IP rate limit(x-mbx-used-weight-1m);

Request Parameters
Name Type Mandatory Description
batchOrders list<JSON> YES order list. Max 5 orders
recvWindow LONG NO
timestamp LONG YES
Where batchOrders is the list of order parameters in JSON

Name Type Mandatory Description
orderId LONG NO
origClientOrderId STRING NO
symbol STRING YES
side ENUM YES SELL, BUY
quantity DECIMAL YES Order quantity, cannot be sent with closePosition=true
price DECIMAL YES
priceMatch ENUM NO only avaliable for LIMIT/STOP/TAKE_PROFIT order; can be set to OPPONENT/ OPPONENT_5/ OPPONENT_10/ OPPONENT_20: /QUEUE/ QUEUE_5/ QUEUE_10/ QUEUE_20; Can't be passed together with price
stopPrice DECIMAL NO stop price, only STOP, STOP_MARKET, TAKE_PROFIT, TAKE_PROFIT_MARKET need
recvWindow LONG NO
timestamp LONG YES
Parameter rules are same with Modify Order
Batch modify orders are processed concurrently, and the order of matching is not guaranteed.
The order of returned contents for batch modify orders is the same as the order of the order list.
One order can only be modfied for less than 10000 times
Response Example
[
 {
  "orderId": 20072994037,
  "symbol": "BTCUSDT",
  "pair": "BTCUSDT",
  "status": "NEW",
  "clientOrderId": "LJ9R4QZDihCaS8UAOOLpgW",
  "price": "30005",
  "avgPrice": "0.0",
  "origQty": "1",
  "executedQty": "0",
  "cumQty": "0",
  "cumBase": "0",
  "timeInForce": "GTC",
  "type": "LIMIT",
  "reduceOnly": false,
  "closePosition": false,
  "side": "BUY",
  "positionSide": "LONG",
  "stopPrice": "0",
  "workingType": "CONTRACT_PRICE",
  "priceProtect": false,
  "origType": "LIMIT",
        "priceMatch": "NONE",              //price match mode
        "selfTradePreventionMode": "NONE", //self trading preventation mode
        "goodTillDate": 0,                 //order pre-set auot cancel time for TIF GTD order
  "updateTime": 1629182711600
 },
 {
  "code": -2022,
  "msg": "ReduceOnly Order is rejected."
 }
]
Get Order Modify History (USER_DATA)
API Description
Get order modification history

HTTP Request
GET /fapi/v1/orderAmendment

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
orderId LONG NO
origClientOrderId STRING NO
startTime LONG NO Timestamp in ms to get modification history from INCLUSIVE
endTime LONG NO Timestamp in ms to get modification history until INCLUSIVE
limit INT NO Default 50; max 100
recvWindow LONG NO
timestamp LONG YES
Either orderId or origClientOrderId must be sent, and the orderId will prevail if both are sent.
Order modify history longer than 3 month is not avaliable
Response Example
[
    {
        "amendmentId": 5363, // Order modification ID
        "symbol": "BTCUSDT",
        "pair": "BTCUSDT",
        "orderId": 20072994037,
        "clientOrderId": "LJ9R4QZDihCaS8UAOOLpgW",
        "time": 1629184560899, // Order modification time
        "amendment": {
            "price": {
                "before": "30004",
                "after": "30003.2"
            },
            "origQty": {
                "before": "1",
                "after": "1"
            },
            "count": 3 // Order modification count, representing the number of times the order has been modified
        }
    },
    {
        "amendmentId": 5361,
        "symbol": "BTCUSDT",
        "pair": "BTCUSDT",
        "orderId": 20072994037,
        "clientOrderId": "LJ9R4QZDihCaS8UAOOLpgW",
        "time": 1629184533946,
        "amendment": {
            "price": {
                "before": "30005",
                "after": "30004"
            },
            "origQty": {
                "before": "1",
                "after": "1"
            },
            "count": 2
        }
    },
    {
        "amendmentId": 5325,
        "symbol": "BTCUSDT",
        "pair": "BTCUSDT",
        "orderId": 20072994037,
        "clientOrderId": "LJ9R4QZDihCaS8UAOOLpgW",
        "time": 1629182711787,
        "amendment": {
            "price": {
                "before": "30002",
                "after": "30005"
            },
            "origQty": {
                "before": "1",
                "after": "1"
            },
            "count": 1
        }
    }
]

Cancel Order (TRADE)
API Description
Cancel an active order.

HTTP Request
DELETE /fapi/v1/order

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
orderId LONG NO
origClientOrderId STRING NO
recvWindow LONG NO
timestamp LONG YES
Either orderId or origClientOrderId must be sent.
Response Example
{
  "clientOrderId": "myOrder1",
  "cumQty": "0",
  "cumQuote": "0",
  "executedQty": "0",
  "orderId": 283194212,
  "origQty": "11",
  "origType": "TRAILING_STOP_MARKET",
   "price": "0",
   "avgPrice": "0.00",
   "reduceOnly": false,
   "side": "BUY",
   "positionSide": "SHORT",
   "status": "CANCELED",
   "stopPrice": "9300",    // please ignore when order type is TRAILING_STOP_MARKET
   "closePosition": false,   // if Close-All
   "symbol": "BTCUSDT",
   "timeInForce": "GTC",
   "type": "TRAILING_STOP_MARKET",
   "activatePrice": "9020",   // activation price, only return with TRAILING_STOP_MARKET order
   "priceRate": "0.3",     // callback rate, only return with TRAILING_STOP_MARKET order
  "updateTime": 1571110484038,
  "workingType": "CONTRACT_PRICE",
  "priceProtect": false,            // if conditional order trigger is protected
 "priceMatch": "NONE",              //price match mode
 "selfTradePreventionMode": "NONE", //self trading preventation mode
 "goodTillDate": 1693207680000      //order pre-set auot cancel time for TIF GTD order
}

Cancel Multiple Orders (TRADE)
API Description
Cancel Multiple Orders

HTTP Request
DELETE /fapi/v1/batchOrders

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
orderIdList LIST<LONG> NO max length 10
e.g. [1234567,2345678]
origClientOrderIdList LIST<STRING> NO max length 10
e.g. ["my_id_1","my_id_2"], encode the double quotes. No space after comma.
recvWindow LONG NO
timestamp LONG YES
Either orderIdList or origClientOrderIdList must be sent.
Response Example
[
 {
   "clientOrderId": "myOrder1",
   "cumQty": "0",
   "cumQuote": "0",
   "executedQty": "0",
   "orderId": 283194212,
   "origQty": "11",
   "origType": "TRAILING_STOP_MARKET",
    "price": "0",
    "reduceOnly": false,
    "side": "BUY",
    "positionSide": "SHORT",
    "status": "CANCELED",
    "stopPrice": "9300",    // please ignore when order type is TRAILING_STOP_MARKET
    "closePosition": false,   // if Close-All
    "symbol": "BTCUSDT",
    "timeInForce": "GTC",
    "type": "TRAILING_STOP_MARKET",
    "activatePrice": "9020",   // activation price, only return with TRAILING_STOP_MARKET order
    "priceRate": "0.3",     // callback rate, only return with TRAILING_STOP_MARKET order
   "updateTime": 1571110484038,
   "workingType": "CONTRACT_PRICE",
   "priceProtect": false,            // if conditional order trigger is protected
   "priceMatch": "NONE",              //price match mode
   "selfTradePreventionMode": "NONE", //self trading preventation mode
   "goodTillDate": 1693207680000      //order pre-set auot cancel time for TIF GTD order
 },
 {
  "code": -2011,
  "msg": "Unknown order sent."
 }
]

Cancel All Open Orders (TRADE)
API Description
Cancel All Open Orders

HTTP Request
DELETE /fapi/v1/allOpenOrders

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
recvWindow LONG NO
timestamp LONG YES
Response Example
{
 "code": 200,
 "msg": "The operation of cancel all open order is done."
}

Previous
Cancel Multiple Orders
Next

Auto-Cancel All Open Orders (TRADE)
API Description
Cancel all open orders of the specified symbol at the end of the specified countdown. The endpoint should be called repeatedly as heartbeats so that the existing countdown time can be canceled and replaced by a new one.

Example usage:
Call this endpoint at 30s intervals with an countdownTime of 120000 (120s).
If this endpoint is not called within 120 seconds, all your orders of the specified symbol will be automatically canceled.
If this endpoint is called with an countdownTime of 0, the countdown timer will be stopped.
The system will check all countdowns approximately every 10 milliseconds, so please note that sufficient redundancy should be considered when using this function. We do not recommend setting the countdown time to be too precise or too small.

HTTP Request
POST /fapi/v1/countdownCancelAll

Weight: 10

Parameters:

Name Type Mandatory Description
symbol STRING YES
countdownTime LONG YES countdown time, 1000 for 1 second. 0 to cancel the timer
recvWindow LONG NO
timestamp LONG YES
Response Example
{
 "symbol": "BTCUSDT",
 "countdownTime": "100000"
}
Query Order (USER_DATA)
API Description
Check an order's status.

These orders will not be found:
order status is CANCELED or EXPIRED AND order has NO filled trade AND created time + 3 days < current time
order create time + 90 days < current time
HTTP Request
GET /fapi/v1/order

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
orderId LONG NO
origClientOrderId STRING NO
recvWindow LONG NO
timestamp LONG YES
Notes:

Either orderId or origClientOrderId must be sent.
orderId is self-increment for each specific symbol
Response Example
{
    "id": "605a6d20-6588-4cb9-afa0-b0ab087507ba",
    "status": 200,
    "result": {
        "avgPrice": "0.00000",
        "clientOrderId": "abc",
        "cumQuote": "0",
        "executedQty": "0",
        "orderId": 1917641,
        "origQty": "0.40",
        "origType": "TRAILING_STOP_MARKET",
        "price": "0",
        "reduceOnly": false,
        "side": "BUY",
        "positionSide": "SHORT",
        "status": "NEW",
        "stopPrice": "9300",    // please ignore when order type is TRAILING_STOP_MARKET
        "closePosition": false,   // if Close-All
        "symbol": "BTCUSDT",
        "time": 1579276756075,    // order time
        "timeInForce": "GTC",
        "type": "TRAILING_STOP_MARKET",
        "activatePrice": "9020",   // activation price, only return with TRAILING_STOP_MARKET order
        "priceRate": "0.3",     // callback rate, only return with TRAILING_STOP_MARKET order
        "updateTime": 1579276756075,  // update time
        "workingType": "CONTRACT_PRICE",
        "priceProtect": false            // if conditional order trigger is protected
    }
}

All Orders (USER_DATA)
API Description
Get all account orders; active, canceled, or filled.

These orders will not be found:
order status is CANCELED or EXPIRED AND order has NO filled trade AND created time + 3 days < current time
order create time + 90 days < current time
HTTP Request
GET /fapi/v1/allOrders

Request Weight
5

Request Parameters
Name Type Mandatory Description
symbol STRING YES
orderId LONG NO
startTime LONG NO
endTime LONG NO
limit INT NO Default 500; max 1000.
recvWindow LONG NO
timestamp LONG YES
Notes:

If orderId is set, it will get orders >= that orderId. Otherwise most recent orders are returned.
The query time period must be less then 7 days( default as the recent 7 days).
Response Example
[
  {
    "avgPrice": "0.00000",
   "clientOrderId": "abc",
   "cumQuote": "0",
   "executedQty": "0",
   "orderId": 1917641,
   "origQty": "0.40",
   "origType": "TRAILING_STOP_MARKET",
   "price": "0",
   "reduceOnly": false,
   "side": "BUY",
   "positionSide": "SHORT",
   "status": "NEW",
   "stopPrice": "9300",    // please ignore when order type is TRAILING_STOP_MARKET
   "closePosition": false,   // if Close-All
   "symbol": "BTCUSDT",
   "time": 1579276756075,    // order time
   "timeInForce": "GTC",
   "type": "TRAILING_STOP_MARKET",
   "activatePrice": "9020",   // activation price, only return with TRAILING_STOP_MARKET order
   "priceRate": "0.3",     // callback rate, only return with TRAILING_STOP_MARKET order
   "updateTime": 1579276756075,  // update time
   "workingType": "CONTRACT_PRICE",
   "priceProtect": false,              // if conditional order trigger is protected
   "priceMatch": "NONE",              //price match mode
   "selfTradePreventionMode": "NONE", //self trading preventation mode
   "goodTillDate": 0      //order pre-set auot cancel time for TIF GTD order
  }
]
Current All Open Orders (USER_DATA)
API Description
Get all open orders on a symbol.

HTTP Request
GET /fapi/v1/openOrders

Request Weight
1 for a single symbol; 40 when the symbol parameter is omitted

Careful when accessing this with no symbol.

Request Parameters
Name Type Mandatory Description
symbol STRING NO
recvWindow LONG NO
timestamp LONG YES
If the symbol is not sent, orders for all symbols will be returned in an array.
Response Example
[
  {
   "avgPrice": "0.00000",
   "clientOrderId": "abc",
   "cumQuote": "0",
   "executedQty": "0",
   "orderId": 1917641,
   "origQty": "0.40",
   "origType": "TRAILING_STOP_MARKET",
   "price": "0",
   "reduceOnly": false,
   "side": "BUY",
   "positionSide": "SHORT",
   "status": "NEW",
   "stopPrice": "9300",    // please ignore when order type is TRAILING_STOP_MARKET
   "closePosition": false,   // if Close-All
   "symbol": "BTCUSDT",
   "time": 1579276756075,    // order time
   "timeInForce": "GTC",
   "type": "TRAILING_STOP_MARKET",
   "activatePrice": "9020",   // activation price, only return with TRAILING_STOP_MARKET order
   "priceRate": "0.3",     // callback rate, only return with TRAILING_STOP_MARKET order
   "updateTime": 1579276756075,  // update time
   "workingType": "CONTRACT_PRICE",
   "priceProtect": false,            // if conditional order trigger is protected
 "priceMatch": "NONE",              //price match mode
    "selfTradePreventionMode": "NONE", //self trading preventation mode
    "goodTillDate": 0      //order pre-set auot cancel time for TIF GTD order
  }
]

Query Current Open Order (USER_DATA)
API Description
Query open order

HTTP Request
GET /fapi/v1/openOrder

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
orderId LONG NO
origClientOrderId STRING NO
recvWindow LONG NO
timestamp LONG YES
EitherorderId or origClientOrderId must be sent
If the queried order has been filled or cancelled, the error message "Order does not exist" will be returned.
Response Example
{
   "avgPrice": "0.00000",
   "clientOrderId": "abc",
   "cumQuote": "0",
   "executedQty": "0",
   "orderId": 1917641,
   "origQty": "0.40",
   "origType": "TRAILING_STOP_MARKET",
   "price": "0",
   "reduceOnly": false,
   "side": "BUY",
   "positionSide": "SHORT",
   "status": "NEW",
   "stopPrice": "9300",    // please ignore when order type is TRAILING_STOP_MARKET
   "closePosition": false,      // if Close-All
   "symbol": "BTCUSDT",
   "time": 1579276756075,    // order time
   "timeInForce": "GTC",
   "type": "TRAILING_STOP_MARKET",
   "activatePrice": "9020",   // activation price, only return with TRAILING_STOP_MARKET order
   "priceRate": "0.3",     // callback rate, only return with TRAILING_STOP_MARKET order
   "updateTime": 1579276756075,  
   "workingType": "CONTRACT_PRICE",
   "priceProtect": false,            // if conditional order trigger is protected
 "priceMatch": "NONE",              //price match mode
    "selfTradePreventionMode": "NONE", //self trading preventation mode
    "goodTillDate": 0      //order pre-set auot cancel time for TIF GTD order
}

User's Force Orders (USER_DATA)
API Description
Query user's Force Orders

HTTP Request
GET /fapi/v1/forceOrders

Request Weight
20 with symbol, 50 without symbol

Request Parameters
Name Type Mandatory Description
symbol STRING NO
autoCloseType ENUM NO "LIQUIDATION" for liquidation orders, "ADL" for ADL orders.
startTime LONG NO
endTime LONG NO
limit INT NO Default 50; max 100.
recvWindow LONG NO
timestamp LONG YES
If "autoCloseType" is not sent, orders with both of the types will be returned
If "startTime" is not sent, data within 7 days before "endTime" can be queried
Response Example
[
  {
   "orderId": 6071832819,
   "symbol": "BTCUSDT",
   "status": "FILLED",
   "clientOrderId": "autoclose-1596107620040000020",
   "price": "10871.09",
   "avgPrice": "10913.21000",
   "origQty": "0.001",
   "executedQty": "0.001",
   "cumQuote": "10.91321",
   "timeInForce": "IOC",
   "type": "LIMIT",
   "reduceOnly": false,
   "closePosition": false,
   "side": "SELL",
   "positionSide": "BOTH",
   "stopPrice": "0",
   "workingType": "CONTRACT_PRICE",
   "origType": "LIMIT",
   "time": 1596107620044,
   "updateTime": 1596107620087
  }
  {
    "orderId": 6072734303,
    "symbol": "BTCUSDT",
    "status": "FILLED",
    "clientOrderId": "adl_autoclose",
    "price": "11023.14",
    "avgPrice": "10979.82000",
    "origQty": "0.001",
    "executedQty": "0.001",
    "cumQuote": "10.97982",
    "timeInForce": "GTC",
    "type": "LIMIT",
    "reduceOnly": false,
    "closePosition": false,
    "side": "BUY",
    "positionSide": "SHORT",
    "stopPrice": "0",
    "workingType": "CONTRACT_PRICE",
    "origType": "LIMIT",
    "time": 1596110725059,
    "updateTime": 1596110725071
  }
]

Account Trade List (USER_DATA)
API Description
Get trades for a specific account and symbol.

HTTP Request
GET /fapi/v1/userTrades

Request Weight
5

Request Parameters
Name Type Mandatory Description
symbol STRING YES
orderId LONG NO This can only be used in combination with symbol
startTime LONG NO
endTime LONG NO
fromId LONG NO Trade id to fetch from. Default gets most recent trades.
limit INT NO Default 500; max 1000.
recvWindow LONG NO
timestamp LONG YES
If startTime and endTime are both not sent, then the last 7 days' data will be returned.
The time between startTime and endTime cannot be longer than 7 days.
The parameter fromId cannot be sent with startTime or endTime.
Only support querying trade in the past 6 months
Response Example
[
  {
   "buyer": false,
   "commission": "-0.07819010",
   "commissionAsset": "USDT",
   "id": 698759,
   "maker": false,
   "orderId": 25851813,
   "price": "7819.01",
   "qty": "0.002",
   "quoteQty": "15.63802",
   "realizedPnl": "-0.91539999",
   "side": "SELL",
   "positionSide": "SHORT",
   "symbol": "BTCUSDT",
   "time": 1569514978020
  }
]

Change Margin Type(TRADE)
API Description
Change symbol level margin type

HTTP Request
POST /fapi/v1/marginType

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
marginType ENUM YES ISOLATED, CROSSED
recvWindow LONG NO
timestamp LONG YES
Response Example
{
 "code": 200,
 "msg": "success"
}

Change Position Mode(TRADE)
API Description
Change user's position mode (Hedge Mode or One-way Mode ) on EVERY symbol

HTTP Request
POST /fapi/v1/positionSide/dual

Request Weight
1

Request Parameters
Name Type Mandatory Description
dualSidePosition STRING YES "true": Hedge Mode; "false": One-way Mode
recvWindow LONG NO
timestamp LONG YES
Response Example
{
 "code": 200,
 "msg": "success"
}

Change Initial Leverage(TRADE)
API Description
Change user's initial leverage of specific symbol market.

HTTP Request
POST /fapi/v1/leverage

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
leverage INT YES target initial leverage: int from 1 to 125
recvWindow LONG NO
timestamp LONG YES
Response Example
{
  "leverage": 21,
  "maxNotionalValue": "1000000",
  "symbol": "BTCUSDT"
}

Change Multi-Assets Mode (TRADE)
API Description
Change user's Multi-Assets mode (Multi-Assets Mode or Single-Asset Mode) on Every symbol

HTTP Request
POST /fapi/v1/multiAssetsMargin

Request Weight
1

Request Parameters
Name Type Mandatory Description
multiAssetsMargin STRING YES "true": Multi-Assets Mode; "false": Single-Asset Mode
recvWindow LONG NO
timestamp LONG YES
Response Example
{
 "code": 200,
 "msg": "success"
}

Modify Isolated Position Margin(TRADE)
API Description
Modify Isolated Position Margin

HTTP Request
POST /fapi/v1/positionMargin

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
positionSide ENUM NO Default BOTH for One-way Mode ; LONG or SHORT for Hedge Mode. It must be sent with Hedge Mode.
amount DECIMAL YES
type INT YES 1: Add position margin，2: Reduce position margin
recvWindow LONG NO
timestamp LONG YES
Only for isolated symbol
Response Example
{
 "amount": 100.0,
   "code": 200,
   "msg": "Successfully modify position margin.",
   "type": 1
}

Previous
Change Multi Assets Mode

Position Information V2 (USER_DATA)
API Description
Get current position information.

HTTP Request
GET /fapi/v2/positionRisk

Request Weight
5

Request Parameters
Name Type Mandatory Description
symbol STRING NO
recvWindow LONG NO
timestamp LONG YES
Note

Please use with user data stream ACCOUNT_UPDATE to meet your timeliness and accuracy needs.

Response Example
For One-way position mode:

[
   {
    "entryPrice": "0.00000",
        "breakEvenPrice": "0.0",  
    "marginType": "isolated",
    "isAutoAddMargin": "false",
    "isolatedMargin": "0.00000000",
    "leverage": "10",
    "liquidationPrice": "0",
    "markPrice": "6679.50671178",
    "maxNotionalValue": "20000000",
    "positionAmt": "0.000",
    "notional": "0",,
    "isolatedWallet": "0",
    "symbol": "BTCUSDT",
    "unRealizedProfit": "0.00000000",
    "positionSide": "BOTH",
    "updateTime": 0
   }
]

For Hedge position mode:

[
    {
        "symbol": "BTCUSDT",
        "positionAmt": "0.001",
        "entryPrice": "22185.2",
        "breakEvenPrice": "0.0",  
        "markPrice": "21123.05052574",
        "unRealizedProfit": "-1.06214947",
        "liquidationPrice": "19731.45529116",
        "leverage": "4",
        "maxNotionalValue": "100000000",
        "marginType": "cross",
        "isolatedMargin": "0.00000000",
        "isAutoAddMargin": "false",
        "positionSide": "LONG",
        "notional": "21.12305052",
        "isolatedWallet": "0",
        "updateTime": 1655217461579
    },
    {
        "symbol": "BTCUSDT",
        "positionAmt": "0.000",
        "entryPrice": "0.0",
        "breakEvenPrice": "0.0",  
        "markPrice": "21123.05052574",
        "unRealizedProfit": "0.00000000",
        "liquidationPrice": "0",
        "leverage": "4",
        "maxNotionalValue": "100000000",
        "marginType": "cross",
        "isolatedMargin": "0.00000000",
        "isAutoAddMargin": "false",
        "positionSide": "SHORT",
        "notional": "0",
        "isolatedWallet": "0",
        "updateTime": 0
    }
]

Position Information V3 (USER_DATA)
API Description
Get current position information(only symbol that has position or open orders will be returned).

HTTP Request
GET /fapi/v3/positionRisk

Request Weight
5

Request Parameters
Name Type Mandatory Description
symbol STRING NO
recvWindow LONG NO
timestamp LONG YES
Note

Please use with user data stream ACCOUNT_UPDATE to meet your timeliness and accuracy needs.

Response Example
For One-way position mode:

[
  {
        "symbol": "ADAUSDT",
        "positionSide": "BOTH",               // position side
        "positionAmt": "30",
        "entryPrice": "0.385",
        "breakEvenPrice": "0.385077",
        "markPrice": "0.41047590",
        "unRealizedProfit": "0.76427700",     // unrealized profit  
        "liquidationPrice": "0",
        "isolatedMargin": "0",
        "notional": "12.31427700",
        "marginAsset": "USDT",
        "isolatedWallet": "0",
        "initialMargin": "0.61571385",        // initial margin required with current mark price
        "maintMargin": "0.08004280",          // maintenance margin required
        "positionInitialMargin": "0.61571385",// initial margin required for positions with current mark price
        "openOrderInitialMargin": "0",        // initial margin required for open orders with current mark price
        "adl": 2,
        "bidNotional": "0",                   // bids notional, ignore
        "askNotional": "0",                   // ask notional, ignore
        "updateTime": 1720736417660
  }
]

For Hedge position mode:

[
  {
        "symbol": "ADAUSDT",
        "positionSide": "LONG",               // position side
        "positionAmt": "30",
        "entryPrice": "0.385",
        "breakEvenPrice": "0.385077",
        "markPrice": "0.41047590",
        "unRealizedProfit": "0.76427700",     // unrealized profit  
        "liquidationPrice": "0",
        "isolatedMargin": "0",
        "notional": "12.31427700",
        "marginAsset": "USDT",
        "isolatedWallet": "0",
        "initialMargin": "0.61571385",        // initial margin required with current mark price
        "maintMargin": "0.08004280",          // maintenance margin required
        "positionInitialMargin": "0.61571385",// initial margin required for positions with current mark price
        "openOrderInitialMargin": "0",        // initial margin required for open orders with current mark price
        "adl": 2,
        "bidNotional": "0",                   // bids notional, ignore
        "askNotional": "0",                   // ask notional, ignore
        "updateTime": 1720736417660
  },
  {
        "symbol": "COMPUSDT",
        "positionSide": "SHORT",
        "positionAmt": "-1.000",
        "entryPrice": "70.92841",
        "breakEvenPrice": "70.900038636",
        "markPrice": "49.72023376",
        "unRealizedProfit": "21.20817624",
        "liquidationPrice": "2260.56757210",
        "isolatedMargin": "0",
        "notional": "-49.72023376",
        "marginAsset": "USDT",
        "isolatedWallet": "0",
        "initialMargin": "2.48601168",
        "maintMargin": "0.49720233",
        "positionInitialMargin": "2.48601168",
        "openOrderInitialMargin": "0",
        "adl": 2,
        "bidNotional": "0",
        "askNotional": "0",
        "updateTime": 1708943511656
  }
]

Position ADL Quantile Estimation(USER_DATA)
API Description
Position ADL Quantile Estimation

Values update every 30s.
Values 0, 1, 2, 3, 4 shows the queue position and possibility of ADL from low to high.
For positions of the symbol are in One-way Mode or isolated margined in Hedge Mode, "LONG", "SHORT", and "BOTH" will be returned to show the positions' adl quantiles of different position sides.
If the positions of the symbol are crossed margined in Hedge Mode:
"HEDGE" as a sign will be returned instead of "BOTH";
A same value caculated on unrealized pnls on long and short sides' positions will be shown for "LONG" and "SHORT" when there are positions in both of long and short sides.
HTTP Request
GET /fapi/v1/adlQuantile

Request Weight
5

Request Parameters
Name Type Mandatory Description
symbol STRING NO
recvWindow LONG NO
timestamp LONG YES
Response Example
[
 {
  "symbol": "ETHUSDT",
  "adlQuantile":
   {
    // if the positions of the symbol are crossed margined in Hedge Mode, "LONG" and "SHORT" will be returned a same quantile value, and "HEDGE" will be returned instead of "BOTH".
    "LONG": 3,  
    "SHORT": 3,
    "HEDGE": 0   // only a sign, ignore the value
   }
  },
  {
   "symbol": "BTCUSDT",
   "adlQuantile":
    {
     // for positions of the symbol are in One-way Mode or isolated margined in Hedge Mode
     "LONG": 1,  // adl quantile for "LONG" position in hedge mode
     "SHORT": 2,  // adl qauntile for "SHORT" position in hedge mode
     "BOTH": 0  // adl qunatile for position in one-way mode
    }
  }
 ]

 Get Position Margin Change History (TRADE)
API Description
Get Position Margin Change History

HTTP Request
GET /fapi/v1/positionMargin/history

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
type INT NO 1: Add position margin，2: Reduce position margin
startTime LONG NO
endTime LONG NO Default current time if not pass
limit INT NO Default: 500
recvWindow LONG NO
timestamp LONG YES
Support querying future histories that are not older than 30 days
The time between startTime and endTimecan't be more than 30 days
Response Example
[
 {
    "symbol": "BTCUSDT",
    "type": 1,
  "deltaType": "USER_ADJUST",
  "amount": "23.36332311",
    "asset": "USDT",
    "time": 1578047897183,
    "positionSide": "BOTH"
 },
 {
  "symbol": "BTCUSDT",
    "type": 1,
  "deltaType": "USER_ADJUST",
  "amount": "100",
    "asset": "USDT",
    "time": 1578047900425,
    "positionSide": "LONG"
 }
]

Test Order(TRADE)
API Description
Testing order request, this order will not be submitted to matching engine

HTTP Request
POST /fapi/v1/order/test

Request Parameters
Name Type Mandatory Description
symbol STRING YES
side ENUM YES
positionSide ENUM NO Default BOTH for One-way Mode ; LONG or SHORT for Hedge Mode. It must be sent in Hedge Mode.
type ENUM YES
timeInForce ENUM NO
quantity DECIMAL NO Cannot be sent with closePosition=true(Close-All)
reduceOnly STRING NO "true" or "false". default "false". Cannot be sent in Hedge Mode; cannot be sent with closePosition=true
price DECIMAL NO
newClientOrderId STRING NO A unique id among open orders. Automatically generated if not sent. Can only be string following the rule: ^[\.A-Z\:/a-z0-9_-]{1,36}$
stopPrice DECIMAL NO Used with STOP/STOP_MARKET or TAKE_PROFIT/TAKE_PROFIT_MARKET orders.
closePosition STRING NO true, false；Close-All，used with STOP_MARKET or TAKE_PROFIT_MARKET.
activationPrice DECIMAL NO Used with TRAILING_STOP_MARKET orders, default as the latest price(supporting different workingType)
callbackRate DECIMAL NO Used with TRAILING_STOP_MARKET orders, min 0.1, max 5 where 1 for 1%
workingType ENUM NO stopPrice triggered by: "MARK_PRICE", "CONTRACT_PRICE". Default "CONTRACT_PRICE"
priceProtect STRING NO "TRUE" or "FALSE", default "FALSE". Used with STOP/STOP_MARKET or TAKE_PROFIT/TAKE_PROFIT_MARKET orders.
newOrderRespType ENUM NO "ACK", "RESULT", default "ACK"
priceMatch ENUM NO only avaliable for LIMIT/STOP/TAKE_PROFIT order; can be set to OPPONENT/ OPPONENT_5/ OPPONENT_10/ OPPONENT_20: /QUEUE/ QUEUE_5/ QUEUE_10/ QUEUE_20; Can't be passed together with price
selfTradePreventionMode ENUM NO NONE:No STP / EXPIRE_TAKER:expire taker order when STP triggers/ EXPIRE_MAKER:expire taker order when STP triggers/ EXPIRE_BOTH:expire both orders when STP triggers; default NONE
goodTillDate LONG NO order cancel time for timeInForce GTD, mandatory when timeInforce set to GTD; order the timestamp only retains second-level precision, ms part will be ignored; The goodTillDate timestamp must be greater than the current time plus 600 seconds and smaller than 253402300799000
recvWindow LONG NO
timestamp LONG YES
Additional mandatory parameters based on type:

Type Additional mandatory parameters
LIMIT timeInForce, quantity, price
MARKET quantity
STOP/TAKE_PROFIT quantity, price, stopPrice
STOP_MARKET/TAKE_PROFIT_MARKET stopPrice
TRAILING_STOP_MARKET callbackRate
Order with type STOP, parameter timeInForce can be sent ( default GTC).

Order with type TAKE_PROFIT, parameter timeInForce can be sent ( default GTC).

Condition orders will be triggered when:

If parameterpriceProtectis sent as true:
when price reaches the stopPrice ，the difference rate between "MARK_PRICE" and "CONTRACT_PRICE" cannot be larger than the "triggerProtect" of the symbol
"triggerProtect" of a symbol can be got from GET /fapi/v1/exchangeInfo
STOP, STOP_MARKET:
BUY: latest price ("MARK_PRICE" or "CONTRACT_PRICE") >= stopPrice
SELL: latest price ("MARK_PRICE" or "CONTRACT_PRICE") <= stopPrice
TAKE_PROFIT, TAKE_PROFIT_MARKET:
BUY: latest price ("MARK_PRICE" or "CONTRACT_PRICE") <= stopPrice
SELL: latest price ("MARK_PRICE" or "CONTRACT_PRICE") >= stopPrice
TRAILING_STOP_MARKET:
BUY: the lowest price after order placed <= activationPrice, and the latest price >= the lowest price *(1 + callbackRate)
SELL: the highest price after order placed >= activationPrice, and the latest price <= the highest price* (1 - callbackRate)
For TRAILING_STOP_MARKET, if you got such error code.
{"code": -2021, "msg": "Order would immediately trigger."}
means that the parameters you send do not meet the following requirements:

BUY: activationPrice should be smaller than latest price.
SELL: activationPrice should be larger than latest price.
If newOrderRespType is sent as RESULT :

MARKET order: the final FILLED result of the order will be return directly.
LIMIT order with special timeInForce: the final status result of the order(FILLED or EXPIRED) will be returned directly.
STOP_MARKET, TAKE_PROFIT_MARKET with closePosition=true:

Follow the same rules for condition orders.
If triggered，close all current long position( if SELL) or current short position( if BUY).
Cannot be used with quantity paremeter
Cannot be used with reduceOnly parameter
In Hedge Mode,cannot be used with BUY orders in LONG position side. and cannot be used with SELL orders in SHORT position side
selfTradePreventionMode is only effective when timeInForce set to IOC or GTC or GTD.

In extreme market conditions, timeInForce GTD order auto cancel time might be delayed comparing to goodTillDate

Response Example
{
  "clientOrderId": "testOrder",
  "cumQty": "0",
  "cumQuote": "0",
  "executedQty": "0",
  "orderId": 22542179,
  "avgPrice": "0.00000",
  "origQty": "10",
  "price": "0",
   "reduceOnly": false,
   "side": "BUY",
   "positionSide": "SHORT",
   "status": "NEW",
   "stopPrice": "9300",  // please ignore when order type is TRAILING_STOP_MARKET
   "closePosition": false,   // if Close-All
   "symbol": "BTCUSDT",
   "timeInForce": "GTD",
   "type": "TRAILING_STOP_MARKET",
   "origType": "TRAILING_STOP_MARKET",
   "activatePrice": "9020", // activation price, only return with TRAILING_STOP_MARKET order
   "priceRate": "0.3",   // callback rate, only return with TRAILING_STOP_MARKET order
  "updateTime": 1566818724722,
  "workingType": "CONTRACT_PRICE",
  "priceProtect": false,      // if conditional order trigger is protected
  "priceMatch": "NONE",              //price match mode
  "selfTradePreventionMode": "NONE", //self trading preventation mode
  "goodTillDate": 1693207680000      //order pre-set auot cancel time for TIF GTD order
}

New Algo Order(TRADE)
API Description
Send in a new Algo order.

HTTP Request
POST /fapi/v1/algoOrder

Request Weight
0 on IP rate limit(x-mbx-used-weight-1m)

Request Parameters
Name Type Mandatory Description
algoType ENUM YES Only support CONDITIONAL
symbol STRING YES
side ENUM YES
positionSide ENUM NO Default BOTH for One-way Mode ; LONG or SHORT for Hedge Mode. It must be sent in Hedge Mode.
type ENUM YES For CONDITIONAL algoType, STOP_MARKET/TAKE_PROFIT_MARKET/STOP/TAKE_PROFIT/TRAILING_STOP_MARKET as order type
timeInForce ENUM NO IOC or GTC or FOK or GTX , default GTC
quantity DECIMAL NO Cannot be sent with closePosition=true(Close-All)
price DECIMAL NO
triggerPrice DECIMAL NO
workingType ENUM NO triggerPrice triggered by: MARK_PRICE, CONTRACT_PRICE. Default CONTRACT_PRICE
priceMatch ENUM NO only avaliable for LIMIT/STOP/TAKE_PROFIT order; can be set to OPPONENT/ OPPONENT_5/ OPPONENT_10/ OPPONENT_20: /QUEUE/ QUEUE_5/ QUEUE_10/ QUEUE_20; Can't be passed together with price
closePosition STRING NO true, false；Close-All，used with STOP_MARKET or TAKE_PROFIT_MARKET.
priceProtect STRING NO "TRUE" or "FALSE", default "FALSE". Used with STOP_MARKET or TAKE_PROFIT_MARKET order. when price reaches the triggerPrice ，the difference rate between "MARK_PRICE" and "CONTRACT_PRICE" cannot be larger than the Price Protection Threshold of the symbol.
reduceOnly STRING NO "true" or "false". default "false". Cannot be sent in Hedge Mode; cannot be sent with closePosition=true
activatePrice DECIMAL NO Used with TRAILING_STOP_MARKET orders, default as the latest price(supporting different workingType)
callbackRate DECIMAL NO Used with TRAILING_STOP_MARKET orders, min 0.1, max 10 where 1 for 1%
clientAlgoId STRING NO A unique id among open orders. Automatically generated if not sent. Can only be string following the rule: ^[\.A-Z\:/a-z0-9_-]{1,36}$
newOrderRespType ENUM NO "ACK", "RESULT", default "ACK"
selfTradePreventionMode ENUM NO EXPIRE_TAKER:expire taker order when STP triggers/ EXPIRE_MAKER:expire taker order when STP triggers/ EXPIRE_BOTH:expire both orders when STP triggers; default NONE
goodTillDate LONG NO order cancel time for timeInForce GTD, mandatory when timeInforce set to GTD; order the timestamp only retains second-level precision, ms part will be ignored; The goodTillDate timestamp must be greater than the current time plus 600 seconds and smaller than 253402300799000
recvWindow LONG NO
timestamp LONG YES
Algo order with type STOP, parameter timeInForce can be sent ( default GTC).
Algo order with type TAKE_PROFIT, parameter timeInForce can be sent ( default GTC).
Condition orders will be triggered when:

If parameterpriceProtectis sent as true:
when price reaches the triggerPrice ，the difference rate between "MARK_PRICE" and "CONTRACT_PRICE" cannot be larger than the "triggerProtect" of the symbol
"triggerProtect" of a symbol can be got from GET /fapi/v1/exchangeInfo
STOP, STOP_MARKET:
BUY: latest price ("MARK_PRICE" or "CONTRACT_PRICE") >= triggerPrice
SELL: latest price ("MARK_PRICE" or "CONTRACT_PRICE") <= triggerPrice
TAKE_PROFIT, TAKE_PROFIT_MARKET:
BUY: latest price ("MARK_PRICE" or "CONTRACT_PRICE") <= triggerPrice
SELL: latest price ("MARK_PRICE" or "CONTRACT_PRICE") >= triggerPrice
TRAILING_STOP_MARKET:
BUY: the lowest price after order placed <= activatePrice, and the latest price >= the lowest price *(1 + callbackRate)
SELL: the highest price after order placed >= activatePrice, and the latest price <= the highest price* (1 - callbackRate)
For TRAILING_STOP_MARKET, if you got such error code.
{"code": -2021, "msg": "Order would immediately trigger."}
means that the parameters you send do not meet the following requirements:

BUY: activatePrice should be smaller than latest price.
SELL: activatePrice should be larger than latest price.
STOP_MARKET, TAKE_PROFIT_MARKET with closePosition=true:

Follow the same rules for condition orders.
If triggered，close all current long position( if SELL) or current short position( if BUY).
Cannot be used with quantity paremeter
Cannot be used with reduceOnly parameter
In Hedge Mode,cannot be used with BUY orders in LONG position side. and cannot be used with SELL orders in SHORT position side
selfTradePreventionMode is only effective when timeInForce set to IOC or GTC or GTD.

Response Example
{
   "algoId": 2146760,
   "clientAlgoId": "6B2I9XVcJpCjqPAJ4YoFX7",
   "algoType": "CONDITIONAL",
   "orderType": "TAKE_PROFIT",
   "symbol": "BNBUSDT",
   "side": "SELL",
   "positionSide": "BOTH",
   "timeInForce": "GTC",
   "quantity": "0.01",
   "algoStatus": "NEW",
   "triggerPrice": "750.000",
   "price": "750.000",
   "icebergQuantity": null,
   "selfTradePreventionMode": "EXPIRE_MAKER",
   "workingType": "CONTRACT_PRICE",
   "priceMatch": "NONE",
   "closePosition": false,
   "priceProtect": false,
   "reduceOnly": false,
   "activatePrice": "", //TRAILING_STOP_MARKET order
   "callbackRate": "",  //TRAILING_STOP_MARKET order
   "createTime": 1750485492076,
   "updateTime": 1750485492076,
   "triggerTime": 0,
   "goodTillDate": 0
}

Cancel Algo Order (TRADE)
API Description
Cancel an active algo order.

HTTP Request
DELETE /fapi/v1/algoOrder

Request Weight
1

Request Parameters
Name Type Mandatory Description
algoId LONG NO
clientAlgoId STRING NO
recvWindow LONG NO
timestamp LONG YES
Either algoId or clientAlgoId must be sent.
Response Example
{
   "algoId": 2146760,
   "clientAlgoId": "6B2I9XVcJpCjqPAJ4YoFX7",
   "code": "200",
   "msg": "success"
}
Cancel All Algo Open Orders (TRADE)
API Description
Cancel All Algo Open Orders

HTTP Request
DELETE /fapi/v1/algoOpenOrders

Request Weight
1

Request Parameters
Name Type Mandatory Description
symbol STRING YES
recvWindow LONG NO
timestamp LONG YES
Response Example
{
 "code": 200,
 "msg": "The operation of cancel all open order is done."
}

Query Algo Order (USER_DATA)
API Description
Check an algo order's status.

These orders will not be found:
order status is CANCELED or EXPIRED AND order has NO filled trade AND created time + 3 days < current time
order create time + 90 days < current time
HTTP Request
GET /fapi/v1/algoOrder

Request Weight
1

Request Parameters
Name Type Mandatory Description
algoId LONG NO
clientAlgoId STRING NO
recvWindow LONG NO
timestamp LONG YES
Notes:

Either algoId or clientAlgoId must be sent.
algoId is self-increment for each specific symbol
Response Example
{
   "algoId": 2146760,
   "clientAlgoId": "6B2I9XVcJpCjqPAJ4YoFX7",
   "algoType": "CONDITIONAL",
   "orderType": "TAKE_PROFIT",
   "symbol": "BNBUSDT",
   "side": "SELL",
   "positionSide": "BOTH",
   "timeInForce": "GTC",
   "quantity": "0.01",
   "algoStatus": "CANCELED",
   "actualOrderId": "",
   "actualPrice": "0.00000",
   "triggerPrice": "750.000",
   "price": "750.000",
   "icebergQuantity": null,
   "tpTriggerPrice": "0.000",
   "tpPrice": "0.000",
   "slTriggerPrice": "0.000",
   "slPrice": "0.000",
   "tpOrderType": "",
   "selfTradePreventionMode": "EXPIRE_MAKER",
   "workingType": "CONTRACT_PRICE",
   "priceMatch": "NONE",
   "closePosition": false,
   "priceProtect": false,
   "reduceOnly": false,
   "createTime": 1750485492076,
   "updateTime": 1750514545091,
   "triggerTime": 0,
   "goodTillDate": 0
}

Current All Algo Open Orders (USER_DATA)
API Description
Get all algo open orders on a symbol.

HTTP Request
GET /fapi/v1/openAlgoOrders

Request Weight
1 for a single symbol; 40 when the symbol parameter is omitted

Careful when accessing this with no symbol.

Request Parameters
Name Type Mandatory Description
algoType STRING NO
symbol STRING NO
algoId LONG NO
recvWindow LONG NO
timestamp LONG YES
If the symbol is not sent, orders for all symbols will be returned in an array.
Response Example
[
   {
       "algoId": 2148627,
       "clientAlgoId": "MRumok0dkhrP4kCm12AHaB",
       "algoType": "CONDITIONAL",
       "orderType": "TAKE_PROFIT",
       "symbol": "BNBUSDT",
       "side": "SELL",
       "positionSide": "BOTH",
       "timeInForce": "GTC",
       "quantity": "0.01",
       "algoStatus": "NEW",
       "actualOrderId": "",
       "actualPrice": "0.00000",
       "triggerPrice": "750.000",
       "price": "750.000",
       "icebergQuantity": null,
       "tpTriggerPrice": "0.000",
       "tpPrice": "0.000",
    "slTriggerPrice": "0.000",
    "slPrice": "0.000",
       "tpOrderType": "",
       "selfTradePreventionMode": "EXPIRE_MAKER",
       "workingType": "CONTRACT_PRICE",
       "priceMatch": "NONE",
       "closePosition": false,
       "priceProtect": false,
       "reduceOnly": false,
       "createTime": 1750514941540,
       "updateTime": 1750514941540,
       "triggerTime": 0,
       "goodTillDate": 0
   }
]

Query All Algo Orders (USER_DATA)
API Description
Get all algo orders; active, CANCELED, TRIGGERED or FINISHED .

These orders will not be found:
order status is CANCELED or EXPIRED AND order has NO filled trade AND created time + 3 days < current time
order create time + 90 days < current time
HTTP Request
GET /fapi/v1/allAlgoOrders

Request Weight
5

Request Parameters
Name Type Mandatory Description
symbol STRING YES
algoId LONG NO
startTime LONG NO
endTime LONG NO
page INT NO
limit INT NO Default 500; max 1000.
recvWindow LONG NO
timestamp LONG YES
Notes:

If algoId is set, it will get orders >= that algoId. Otherwise most recent orders are returned.
The query time period must be less then 7 days( default as the recent 7 days).
Response Example
[
   {
       "algoId": 2146760,
       "clientAlgoId": "6B2I9XVcJpCjqPAJ4YoFX7",
       "algoType": "CONDITIONAL",
       "orderType": "TAKE_PROFIT",
       "symbol": "BNBUSDT",
       "side": "SELL",
       "positionSide": "BOTH",
       "timeInForce": "GTC",
       "quantity": "0.01",
       "algoStatus": "CANCELED",
       "actualOrderId": "",
       "actualPrice": "0.00000",
       "triggerPrice": "750.000",
       "price": "750.000",
       "icebergQuantity": null,
       "tpTriggerPrice": "0.000",
       "tpPrice": "0.000",
       "slTriggerPrice": "0.000",
       "slPrice": "0.000",
       "tpOrderType": "",
       "selfTradePreventionMode": "EXPIRE_MAKER",
       "workingType": "CONTRACT_PRICE",
       "priceMatch": "NONE",
       "closePosition": false,
       "priceProtect": false,
       "reduceOnly": false,
       "createTime": 1750485492076,
       "updateTime": 1750514545091,
       "triggerTime": 0,
       "goodTillDate": 0
   }
]

Futures TradFi Perps Contract(USER_DATA)
API Description
Sign TradFi-Perps agreement contract

HTTP Request
POST /fapi/v1/stock/contract

Request Weigh
50

Request Parameters
Name Type Mandatory Description
recvWindow LONG NO
timestamp LONG YES
Response Example
{
   "code": 200,
 "msg": "success"
}
