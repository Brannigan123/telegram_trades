from asyncio.exceptions import IncompleteReadError

import logging
import time
import toml
import json
import math
import os
import re

from ejtraderMT import Metatrader
from telethon.sync import TelegramClient
from telethon.errors.rpcbaseerrors import FloodError, TimedOutError
from telethon import events
from datetime import timedelta, datetime, timezone
from timeloop import Timeloop
from dotenv import load_dotenv

from constants import TRADE_SELL, TRADE_BUY, symbols, symbol_keywords, blacklist

logging.basicConfig(format='[%(levelname) 5s/%(asctime)s] %(name)s: %(message)s', level=logging.ERROR)
#logging.getLogger('telethon.messagebox').setLevel(logging.NOTSET + 1)
load_dotenv()


tl = Timeloop()

tg_test_signals_chat = -4000930568
tg_alerts_chat = -4046528690
tg_chats = [-1001763228815, -1001620915850, -1001195451019, -1001788360823,  tg_test_signals_chat]

server_hrs_timedelta=-3

high_imapact_news = {}
market_trends = {}




def fmt_date(d: datetime):
    """
    Formats a given datetime object into a string representation of the date in the format 'dd/mm/yyyy'.

    Parameters:
        d (datetime): The datetime object to be formatted.

    Returns:
        str: The formatted date string.
    """
    return d.strftime('%d/%m/%Y')


def avg_cons_diff(numbers: list[float]):
    """
    Calculate the average difference between consecutive numbers in a list.

    Parameters:
    - numbers (list[float]): A list of numbers.

    Returns:
    - float: The average difference between consecutive numbers. Returns None if the list has less than 2 elements.
    """
    if len(numbers) < 2:
        return None
    diff = [numbers[i] - numbers[i - 1] for i in range(1, len(numbers))]
    return sum(diff) / len(diff)


def news_affecting_symbol(symbol: str):
    """
    Retrieves news affecting a given symbol if current time is within 1 hour to news or 30 minutes after.

    Args:
        symbol (str): The symbol for which to retrieve news.

    Returns:
        str: A TOML string containing the news data if there is any news within the specified time range.
        None: If there is no news within the specified time range.
        Exception: If an error occurs while retrieving the news.

    Raises:
        None
    """
    try:
        news = high_imapact_news.get(symbol)
        if not (news is None or news.empty):
            current_time = datetime.now() + timedelta(hours=server_hrs_timedelta)
            start_time = current_time - timedelta(hours=1)
            end_time = current_time + timedelta(minutes=30)
            news = news[start_time:end_time]
            if news.empty: return None
            news.rename_axis('when', inplace=True)
            news.reset_index(inplace=True)
            news.set_index('event', inplace=True)
            return toml.dumps(json.loads(news.to_json(orient="index", date_format="iso"))) 
    except Exception as e:
        return e
    return None


def is_trade_against_trend(symbol: str, option: int):
    """
    Determines if a trade against trend is valid.

    Args:
        symbol (str): The symbol of the trade.
        option (int): The option of the trade (TRADE_SELL or TRADE_BUY).

    Returns:
        bool: True if the trade is against trend, False otherwise.
    """
    try:
        trend = market_trends.get(symbol)
        if not trend:
            return True
        if option == TRADE_SELL and trend > 0:
            return True
        if option == TRADE_BUY and trend < 0:
            return True
    except Exception as _:
        return True
    return False


def extract_symbol(message: str):
    """
    Extracts the symbol from a given message.

    Args:
        message (str): The message from which to extract the symbol.

    Returns:
        str or None: The extracted symbol if found in the message, None otherwise.
    """
    for i, keywords in enumerate(symbol_keywords):
        for keyword in keywords:
            if keyword in message:
                return symbols[i]
    return None


def extract_trade_option(message: str):
    """
    Extracts the trade option from the given message.

    Args:
        message (str): The message to extract the trade option from.

    Returns:
        str or None: The extracted trade option, which can be either TRADE_BUY or TRADE_SELL. Returns None if no trade option is found.
    """
    if 'BUY' in message or 'LONG' in message:
        return TRADE_BUY
    if 'SELL' in message or 'SHORT' in message:
        return TRADE_SELL
    return None


def extract_tps(message: str):
    """
    Extracts take profit (TP) values from a given message string.

    Args:
        message (str): The message string to extract TP values from.

    Returns:
        list: A list of TP values extracted from the message string. If no TP values are found, a list with a single None value is returned.
    """
    tp_matches = re.findall(r"TP\s*\d*\D+(\d+(?:\.\d+)?)", message)
    if not tp_matches:
        tp_matches = re.findall(r"TAKE\s*PROFIT\s*\d*\D+(\d+(?:\.\d+)?)", message)
    if not tp_matches:
        tp_matches = re.findall(r"TARGET\s*\d*\D+(\d+(?:\.\d+)?)", message)
    return [float(tp) for tp in tp_matches] if tp_matches else [None]


def extract_sl(message: str):
    """
    Extracts the stop loss value from a given message.

    Args:
        message (str): The message from which to extract the stop loss value.

    Returns:
        float: The extracted stop loss value.

    Raises:
        None
    """
    sl_matches = re.findall(r"SL\s*\d*\D+(\d+(?:\.\d+)?)", message)
    if not sl_matches:
        sl_matches = re.findall(r"STOP\s*LOSS\s*\d*\D+(\d+(?:\.\d+)?)", message)
    if not sl_matches:
        sl_matches = re.findall(r"STOP\s*\d*\D+(\d+(?:\.\d+)?)", message)
    return float(sl_matches[0]) if sl_matches else [None]


async def trade(message: str, symbol: str, trade_option: int):
    """
    Asynchronously executes a trade based on the provided message, symbol, and trade option.

    Args:
        message (str): The message containing trade information.
        symbol (str): The symbol for the trade.
        trade_option (int): The trade option (TRADE_BUY or TRADE_SELL).

    Returns:
        None
    """
    tps, sl = (extract_tps(message), extract_sl(message))
    api = Metatrader()
    if trade_option == TRADE_BUY: 
        for tp in tps: api.buy(symbol, 0.01, sl, tp, 5)
    elif trade_option == TRADE_SELL:
        for tp in tps: api.sell(symbol, 0.01, sl, tp, 5)
        
async def try_trade(event: events.NewMessage.Event | events.MessageEdited.Event):
    """
    Executes a trade based on the given event.

    Args:
        event (events.NewMessage.Event | events.MessageEdited.Event): The event that triggered the trade.

    Returns:
        None
    """
    tg_client = event.message.client
    message = event.message.message.upper()
    symbol = extract_symbol(message)
    if symbol not in symbols or any(phrase in message for phrase in blacklist): return
    
    news = news_affecting_symbol(symbol)
    if news is not None:
        await tg_client.send_message(tg_alerts_chat, f"Affected by News\n\n{news}\n\nFrom: {(await event.get_chat()).title}\n\n{message}")
    else:
        trade_option = extract_trade_option(message)
        if trade_option is None:
            return
        if is_trade_against_trend(symbol, trade_option):
            await tg_client.send_message(tg_alerts_chat, f"Against Trend {market_trends.get(symbol)}\nFrom: {(await event.get_chat()).title}\n\n{message}")   
        else:
            await trade(message, symbol, trade_option)
            await tg_client.send_message(tg_alerts_chat, f"New Trade:\nFrom: {(await event.get_chat()).title}\n\n{message}")
                    
@tl.job(interval=timedelta(minutes=10))
def update_news_impact_data():
    """
    Update the news impact data for each symbol.

    This function is decorated with `@tl.job` to schedule it to run every 2 hours. It retrieves the news data for each symbol within a specific time range and updates the `high_imapact_news` dictionary with the news articles that have an impact score greater than 1.

    Parameters:
    None

    Returns:
    None
    """
    calendar_start = datetime.now() + timedelta(hours=server_hrs_timedelta)
    calendar_end = calendar_start + timedelta(days=1)
    
    for symbol in symbols:
        retries = 0
        while retries < 5:
            try:
                api = Metatrader()
                news = api.calendar(symbol,fmt_date(calendar_start),fmt_date(calendar_end))
                high_imapact_news[symbol] = news if news.empty else news[[int(i) > 1 for i in list(news['impact'])]]
                break
            except Exception as e:
                print(symbol, retries, e, news)
                time.sleep(math.ceil(1+retries/3))
                retries += 1
            
    
@tl.job(interval=timedelta(minutes=10))
def update_market_trends():
    """
    Update the market trends by fetching historical data for each symbol and calculating the average difference between the highs and lows.
    
    Parameters:
        None
    
    Returns:
        None
    """
    history_end = datetime.now() + timedelta(hours=server_hrs_timedelta)
    history_start = history_end
    daycount = 0
    while True:
        if history_start.weekday() < 5:
            daycount += 1
            if daycount >=2: break
        history_start = history_start - timedelta(days=1)
    timeframe="M30"
    for symbol in symbols:
        retries = 0
        while retries < 5:
            try:
                api = Metatrader()
                history = api.history(symbol, timeframe,fmt_date(history_start),fmt_date(history_end))
                highs_delta = avg_cons_diff(list(history['high']))
                lows_delta = avg_cons_diff(list(history['low']))
                market_trends[symbol] = round((highs_delta + lows_delta) / 2, 4)
                print(f"{symbol} Trend: {market_trends[symbol]}")
                break
            except Exception as e:
                print(symbol, retries, e, history)
                time.sleep(math.ceil(1+retries/3))
                retries += 1
                       
                            
if __name__ == "__main__": 
   
    TELEGRAM_API_ID = int(str(os.getenv('TELEGRAM_API_ID')))
    TELEGRAM_API_HASH = str(os.getenv('TELEGRAM_API_HASH'))
    
    execute = True
    
    while execute:
        execute = False
        
        with TelegramClient('tg', TELEGRAM_API_ID, TELEGRAM_API_HASH) as tg_client:    
            try:
                @tg_client.on(events.NewMessage(chats=tg_chats,))
                async def on_new_msg(event):
                    timediff =  datetime.now(timezone.utc) - event.date
                    if timediff < timedelta(minutes=1):
                        await try_trade(event)
                        
                @tg_client.on(events.MessageEdited(chats=tg_chats,))
                async def on_edited_msg(event):
                    timediff =  datetime.now(timezone.utc) - event.date
                    if timediff < timedelta(minutes=1):
                        await try_trade(event)

                update_news_impact_data()
                update_market_trends()
                
                tl.start(block=False)
                tg_client.run_until_disconnected()
                
                
            except (ConnectionError, TimedOutError) as e:
                    time.sleep(60)
                    execute = True
            except FloodError as e:
                    time.sleep(20)
                    execute = True
            finally:
                    tl.stop()
                    tg_client.disconnect() 