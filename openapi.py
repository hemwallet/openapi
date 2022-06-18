import json
import os
import time
from dataclasses import dataclass
from typing import List, Dict

import logzero
from aiocache import caches, cached
from fastapi import FastAPI, APIRouter, Request, Depends, HTTPException
from logzero import logger
from starlette.middleware.cors import CORSMiddleware

import config as settings
from utils.cache_utils.all_tail_list_info_cache import AllTailListInfoCache
from utils.cache_utils.tail_info_cache import TailInfoCache
from utils.cache_utils.chain_price_info_cache import ChainPriceInfoInfoCache
from post_body import GetTailInfoBody, GetNetworkInfoBody, NamesBody, CoinsNameInfoBody, PuzzlehashesBody, \
    SendTxBody, GetLineAgeProofInfosBody, ChainBody
from rpc_client import FullNodeRpcClient
from utils import int_to_hex

caches.set_config(settings.CACHE_CONFIG)

app = FastAPI()

cwd = os.path.dirname(__file__)

log_dir = os.path.join(cwd, "logs")

if not os.path.exists(log_dir):
    os.mkdir(log_dir)

logzero.logfile(os.path.join(log_dir, "api.log"))


@dataclass
class Chain:
    id: str
    chain_name: str
    network_name: str
    network_prefix: str
    logo: str
    agg_sig_me_additional_data: str
    client: FullNodeRpcClient


async def init_chains(app, chains_config):
    chains: Dict[str, Chain] = {}
    for row in chains_config:
        id_hex = int_to_hex(row['id'])
        print(id_hex)

        if row.get('proxy_rpc_url'):
            client = await FullNodeRpcClient.create_by_proxy_url(row['proxy_rpc_url'], row['chia_root_path'])
        elif row.get('chia_root_path'):
            client = await FullNodeRpcClient.create_by_chia_root_path(row['chia_root_path'])
        else:
            raise ValueError(f"chian {row['id']} has no full node rpc config")

        # check client
        network_info = await client.get_network_info()
        # print(network_info)
        chains[id_hex] = Chain(
            id_hex,
            row['chain_name'],
            row['network_name'],
            row['network_prefix'],
            row['native_token']['logo'],
            row['agg_sig_me_additional_data'],
            client)

    app.state.chains = chains


@app.on_event("startup")
async def startup():
    await init_chains(app, settings.SUPPORTED_CHAINS)


@app.on_event("shutdown")
async def shutdown():
    for chain in app.state.chains.values():
        chain.client.close()
        await chain.client.await_closed()


async def get_chain(request: Request, chain="0x01") -> Chain:
    if chain not in request.app.state.chains:
        raise HTTPException(400, "Ivalid Chain")
    return request.app.state.chains[chain]


async def get_chains(request: Request) -> Dict[Chain, str]:
    return request.app.state.chains


router = APIRouter()


@router.get('/coin_by_name')
async def coin_by_name(coin_name, chain: Chain = Depends(get_chain)):
    coin = await chain.client.get_coin_record_by_name(coin_name)
    return coin


@router.get('/coins_by_names')
async def coins_by_names(coin_names, chain: Chain = Depends(get_chain)):
    coin_names = json.loads(coin_names)
    coins = []
    for coin_name in coin_names:
        coin = await chain.client.get_coin_record_by_name(coin_name)
        coins.append(coin)
    return coins


@router.post('/whether_coins_spent')
async def whether_coins_spent(item: CoinsNameInfoBody, chains: Dict[str, Chain] = Depends(get_chains)):
    chain = chains[item.chain]
    res = {}
    for coin_name, names in item.coins_name_info.items():
        names = names
        res[coin_name] = await chain.client.whether_coins_spent(names)
    # print(names,res)
    return res


@router.get('/get_puzzle_and_solution')
async def get_puzzle_and_solution(coin_infos: str, chain: Chain = Depends(get_chain)):
    # todo: cache_utils
    coin_infos = json.loads(coin_infos)
    res = []
    for i in range(len(coin_infos)):
        coin_info = coin_infos[i]
        _ = await chain.client.get_puzzle_and_solution(coin_id=coin_info['coin_id'], height=coin_info['height'])
        res.append(_)
    return res


@router.post('/line_age_proof_infos')
async def line_age_proof_infos(item: GetLineAgeProofInfosBody, chain: Chain = Depends(get_chain)):
    coin_names = item.coin_names
    line_age_proof_infos = []
    for coin_name, height in coin_names.items():
        coin = await chain.client.get_coin_record_by_name(coin_name)
        _ = await chain.client.get_puzzle_and_solution(coin_id=coin_name, height=height)
        # print(json.dumps(_,indent=4))
        # optimize by return puzzlehash
        line_age_proof_infos.append({'amount': coin['coin']['amount'],
                                     'parent_coin_info': _['coin_solution']['coin']['parent_coin_info'],
                                     'puzzle_reveal': _['coin_solution']['puzzle_reveal']})
    return line_age_proof_infos


@router.post('/coins_by_puzzlehashes')
async def query_coins(item: PuzzlehashesBody, chains: Dict[str, Chain] = Depends(get_chains)):
    chain: Chain = chains[item.chain]
    coin_records_dict = {}
    for coin_name, info in item.puzzlehashes_info.items():
        # todo: use blocke indexer and supoort unconfirmed param
        # print(puzzlehashes,height)
        puzzlehashes = info['puzzlehashes']
        peak_height_list = info['peak_height_list']
        coin_records = []
        for i in range(len(puzzlehashes)):
            _coin_records = await chain.client.get_coin_records_by_puzzle_hash(
                puzzle_hash=puzzlehashes[i],
                include_spent_coins=info['include_spent'] if 'include_spent' in info else False,
                start_height=peak_height_list[i])
            coin_records.extend(_coin_records)
        if len(coin_records) > 400:
            st = time.time()
            name_map = {'coin': '1', 'amount': '2', 'parent_coin_info': '3', 'puzzle_hash': '4',
                        'confirmed_block_index': '5', 'spent': '6', 'timestamp': '7', 'spent_block_index': '8'}
            amount_to_name_map = {}
            name_to_amount_map = {}
            puzzlehash_to_name_map = {}
            name_to_puzzlehash_map = {}
            compressed_coin_records = []
            for coin_record in coin_records:
                puzzlehash = coin_record['coin']['puzzle_hash']
                amount = coin_record['coin']['amount']
                if puzzlehash not in puzzlehash_to_name_map:
                    puzzlehash_mapped_name = str(len(puzzlehash_to_name_map))
                    puzzlehash_to_name_map[puzzlehash] = puzzlehash_mapped_name
                    name_to_puzzlehash_map[puzzlehash_mapped_name] = puzzlehash
                else:
                    puzzlehash_mapped_name = puzzlehash_to_name_map[puzzlehash]
                if amount not in amount_to_name_map:
                    amount_mapped_name = str(len(amount_to_name_map))
                    amount_to_name_map[amount] = amount_mapped_name
                    name_to_amount_map[amount_mapped_name] = amount
                else:
                    amount_mapped_name = amount_to_name_map[amount]
                compressed_coin_records.append({
                    name_map['coin']: {
                        name_map['amount']: amount_mapped_name,
                        name_map['parent_coin_info']: coin_record['coin']['parent_coin_info'],
                        name_map['puzzle_hash']: puzzlehash_mapped_name,
                    },
                    name_map['confirmed_block_index']: coin_record['confirmed_block_index'],
                    name_map['spent']: coin_record['spent'],
                    name_map['timestamp']: coin_record['timestamp'],
                    name_map['spent_block_index']: coin_record['spent_block_index'],
                })
            coin_records_dict[coin_name] = {
                'compressed_coin_records': compressed_coin_records,
                'name_to_puzzlehash_map': name_to_puzzlehash_map,
                'name_map': name_map,
                'name_to_amount_map': name_to_amount_map
            }
            print('Compressing time:', time.time() - st)
        else:
            coin_records_dict[coin_name] = coin_records

    print('Size:', len(json.dumps(coin_records_dict)))
    return coin_records_dict


@router.post('/puzzlehashes_by_names')
async def get_puzzlehashes_by_names(item: NamesBody, chains: Dict[str, Chain] = Depends(get_chains)):
    chain: Chain = chains[item.chain]
    names = item.names
    puzzlehashes = []
    for name in names:
        # print('name', name)
        coin_record = await chain.client.get_coin_record_by_name(name)
        # print('coin_record', coin_record)
        puzzlehashes.append(coin_record['coin']['puzzle_hash'])
    return puzzlehashes


@router.post('/get_network_info')
@cached(ttl=10)
async def get_network_info(item: GetNetworkInfoBody, chains: Dict[str, Chain] = Depends(get_chains)):
    print('with_logo', item.with_logo)
    chain: Chain = chains[item.chain]
    with_logo: bool = item.with_logo
    info = await chain.client.get_network_info()
    info['chain_name'] = chain.chain_name
    if with_logo:
        info['logo'] = chain.logo
    info['agg_sig_me_additional_data'] = chain.agg_sig_me_additional_data
    return info


tail_info_cache = TailInfoCache()
all_tail_list_info_cache = AllTailListInfoCache()
chain_price_info_cache = ChainPriceInfoInfoCache()


# @cached(ttl=1800, key_builder=lambda *args, **kwargs: f"get_tail_info:{kwargs['tail_puzzlehash']}", alias='default')
@router.post('/get_tail_info')
async def get_tail_info(item: GetTailInfoBody, chains: Dict[str, Chain] = Depends(get_chains)):
    chain = chains[item.chain]
    tail_puzzlehash = item.tail_puzzlehash
    return tail_info_cache.get_tail_info(chain, tail_puzzlehash)


@router.post('/get_all_tail_list_info')
async def get_all_tail_list_info(item: ChainBody, chains: Dict[str, Chain] = Depends(get_chains)):
    chain = chains[item.chain]
    return all_tail_list_info_cache.get_all_tail_list_info(chain)


@router.post('/get_code_and_hash_list')
async def get_code_and_hash_list(item: ChainBody, chains: Dict[str, Chain] = Depends(get_chains)):
    chain = chains[item.chain]
    all_tail_list_info = all_tail_list_info_cache.get_all_tail_list_info(chain)
    tails = all_tail_list_info['tails']
    code_and_hash_list = []
    for tail in tails:
        code_and_hash_list.append({'code': tail['code'], 'hash': tail['hash']})
    # print(json.dumps(all_tail_list_info, indent=2))
    print(len(json.dumps(code_and_hash_list)))
    return code_and_hash_list


@router.post('/get_chain_price_info')
async def get_chain_price_info(item: ChainBody, chains: Dict[str, Chain] = Depends(get_chains)):
    chain = chains[item.chain]
    return chain_price_info_cache.get_chain_price_info(chain)


@router.post("/sendtx")
async def create_transaction(item: SendTxBody, chains: Dict[str, Chain] = Depends(get_chains)):
    chain: Chain = chains[item.chain]
    # print(chain.id, json.dumps(item.dict(), indent=2))
    spb = item.spend_bundle
    # print(item.spend_bundle)
    try:
        resp = await chain.client.push_tx(spb)
        # print(resp)
    except ValueError as e:
        logger.warning("sendtx: %s, error: %r", spb, e)
        raise HTTPException(400, str(e))
    return {
        'status': resp['status'],
        'id': 'deprecated',  # will be removed after goby updated
    }


def start_cache():
    tail_info_cache.get_tail_info_thread.start()
    all_tail_list_info_cache.get_all_tail_list_info_thread.start()
    chain_price_info_cache.get_chain_price_info_thread.start()


def stop_cache():
    tail_info_cache.stop()
    all_tail_list_info_cache.stop()
    chain_price_info_cache.stop()


app.include_router(router, prefix="/v1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)
