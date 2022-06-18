
SECONDS_PER_BLOCK = (24 * 3600) / 4608

CACHE_CONFIG = {
    'default': {
        'cache_utils': "aiocache.SimpleMemoryCache",
    },
    # use redis, uncomment next
    # 'default': {
    #     'cache_utils': "aiocache.RedisCache",
    #     'endpoint': "",
    #     'port': 6379,
    #     'password': '',
    # }
}


SUPPORTED_CHAINS = [
    {
        "id": 1,
        "network_name": "mainnet",
        "chain_name": "chia",
        "network_prefix": "xch",
        "native_token": {
            "decimals": 12,
            "name": "XCH",
            "symbol": "XCH",
            "logo": "data:image/png;base64,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"
        },
        "agg_sig_me_additional_data": "ccd5bb71183532bff220ba46c268991a3ff07eb358e8255a65c30a2dce0e5fbb",
        "proxy_rpc_url": "https://localhost:8555",
        #"chia_root_path": "/home/*/.chia/mainnet/",
    },
]
