from pydantic.main import BaseModel


class ChainBody(BaseModel):
    chain: str


class GetTailInfoBody(BaseModel):
    tail_puzzlehash: str
    chain: str


class GetNetworkInfoBody(BaseModel):
    with_logo: bool
    chain: str


class NamesBody(BaseModel):
    names: list
    chain: str


class PuzzlehashesBody(BaseModel):
    puzzlehashes_info: dict
    chain: str


class CoinsNameInfoBody(BaseModel):
    coins_name_info: dict
    chain: str


class SendTxBody(BaseModel):
    spend_bundle: dict
    chain: str


class GetLineAgeProofInfosBody(BaseModel):
    coin_names: dict
    chain: str
