TRADE_SELL=0
TRADE_BUY=1

symbol_keywords = [
    ['XAUUSD','XAU/USD', 'GOLD'],
    ['EURUSD','EUR/USD', 'EURO'],
    ['AUDUSD','AUD/USD'],
    ['NZDUSD','NZD/USD'],
    ['GBPUSD','GBP/USD'],
    ['AUDCAD','AUD/CAD'],
    ['NZDCAD','NZD/CAD'],
    ['EURGBP','EUR/GBP'],
    ['AUDJPY','AUD/JPY'],
    ['USDJPY','USD/JPY'],
    ['CADJPY','CAD/JPY'],
    ['CHFJPY','CHF/JPY'],
    ['GBPJPY','GBP/JPY'],
    ['EURAUD','EUR/AUD']
]

symbols = [keywords[0] for keywords in symbol_keywords]

blacklist = ['HOLD', 'BE', 'BREAKEVEN', 'HIT', 'RUNNING', 'CLOSE', 'COLLECT', 'PIPS', 'SUCCESS']

tg_test_signals_chat = -4000930568
tg_alerts_chat = -4046528690
tg_chats = [
    # UK Scalping Traders official
    -1001195451019,
    # XAUUSD/NASDAQ
    -1001788360823,
    # Forex Scalping
    -1001620915850,
    # Test Signals Channel
    tg_test_signals_chat
    ]
