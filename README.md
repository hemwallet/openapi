# openapi

DeFi wallet on Chia Network.
[hem coin](https://www.hem.cc):Hem coin is a token issued on the chia blockchain
## Install

You can install Hem wallet [here](https://microsoftedge.microsoft.com/addons/detail/ibkgkjjpppcmhicmplcnanpalajpnodh).
hem wallet website:https://wallet.hem.cc

## Run your own node

```
git clone https://github.com/hemwallet/openapi.git
cd openapi
# change config.py
python -m venv venv
. ./venv/bin/activate
pip install -r requirements.txt
# change port or add ssl config files in run.py
mkdir cache
python run.py
```

## Thanks

Thanks to the contributions of [Chia Mine](https://github.com/Chia-Mine/clvm-js), MetaMask, and [Goby](https://github.com/GobyWallet), we stand on your shoulders to complete this project.

Also, thanks to Catcoin and [Taildatabase](https://www.taildatabase.com/) for sharing the token list.

