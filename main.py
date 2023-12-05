import time
from random import shuffle, uniform

import pyuseragents
import requests
from eth_account import Account
from eth_account.signers.local import LocalAccount
from loguru import logger
from web3 import Web3, types

from abi import CLAIM_ABI, TOKEN_ABI
from config import (AIM_WALLET, CLAIM_ADDRESS, RANDOM_WALLETS_ORDER, RPC,
                    SLEEP_BETWEEN_WALLETS, TOKEN_ADDRESS, TRANSFER_TO_ONE)

w3 = Web3(Web3.HTTPProvider(RPC))
claim_contract = w3.eth.contract(w3.to_checksum_address(CLAIM_ADDRESS), abi=CLAIM_ABI)
token_contract = w3.eth.contract(w3.to_checksum_address(TOKEN_ADDRESS), abi=TOKEN_ABI)

logger.add("log/debug.log")


headers = {
    "authority": "www.zksyncpepe.com",
    "scheme": "https",
    "cache-control": "no-cache",
    "accept": "application/json, text/plain, */*",
    "accept-encoding": "deflate, br",
    "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7,uk-UA;q=0.6,uk;q=0.5",
    "referer": "https://www.zksyncpepe.com/airdrop",
    "sec-ch-ua": '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": pyuseragents.random(),
}


def get_amount_and_proof(
    address: str, session: requests.Session
) -> tuple[int, list[str]] | None:
    base_url = "https://www.zksyncpepe.com/resources/"

    retries = 3
    delay = 5

    while retries:
        try:
            amount_url = f"{base_url}amounts/{address.lower()}.json"
            proof_url = f"{base_url}proofs/{address.lower()}.json"

            amount = session.get(amount_url).json()
            time.sleep(1)
            proof = session.get(proof_url).json()
            return amount[0], proof
        except Exception as ex:
            logger.error(
                f"Request failed for {address}. Retrying in {delay} seconds. Error: {ex}"
            )
            time.sleep(delay)
            retries -= 1
            continue


def claim(wallet: LocalAccount, proof: list[str], amount: int) -> None:
    tx_params: types.TxParams = {
        "from": wallet.address,
        "nonce": w3.eth.get_transaction_count(wallet.address),
    }
    tx = claim_contract.functions.claim(
        proof, w3.to_wei(amount, "ether")
    ).build_transaction(tx_params)

    signed_tx = wallet.sign_transaction(tx)

    try:
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logger.success(
            f"Claim {amount} tokens from {wallet.address}. Tx: https://explorer.zksync.io/tx/{tx_hash.hex()}"
        )
    except Exception as ex:
        logger.error(f"{wallet.address}. Error: {ex}")


def transfer_erc20(wallet: LocalAccount) -> None:
    tx_params: types.TxParams = {
        "from": wallet.address,
        "nonce": w3.eth.get_transaction_count(wallet.address),
    }
    balance = token_contract.functions.balanceOf(wallet.address).call()
    tx = token_contract.functions.transfer(
        w3.to_checksum_address(AIM_WALLET), balance
    ).build_transaction(tx_params)

    signed_tx = wallet.sign_transaction(tx)

    try:
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logger.success(
            f"Transfer {w3.from_wei(balance, 'ether')} tokens from {wallet.address} to {AIM_WALLET}. Tx: https://explorer.zksync.io/tx/{tx_hash.hex()}"
        )
    except Exception as ex:
        logger.error(f"{wallet.address}. Error: {ex}")


def sleep() -> None:
    sleep_amount = uniform(*SLEEP_BETWEEN_WALLETS)
    logger.info(f"Sleep {sleep_amount} s")
    time.sleep(sleep_amount)


def main() -> None:
    logger.info("Start. Powered by https://t.me/python_web3")

    with open("wallets.txt", "r", encoding="utf8") as file:
        wallets: list[LocalAccount] = [
            Account.from_key(line.strip())
            for line in file.read().split("\n")
            if line != ""
        ]

    if RANDOM_WALLETS_ORDER:
        shuffle(wallets)

    with requests.Session() as session:
        session.headers.update(headers)
        for wallet in wallets:
            res = get_amount_and_proof(wallet.address, session)
            if res is None:
                continue
            amount, proof = res
            claim(wallet, proof, amount)
            if TRANSFER_TO_ONE:
                transfer_erc20(wallet)
            sleep()

    logger.info("Finish")


if __name__ == "__main__":
    main()
