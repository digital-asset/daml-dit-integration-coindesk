# Copyright (c) 2020, Digital Asset (Switzerland) GmbH and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging

from dataclasses import dataclass

from datetime import datetime

from aiohttp import ClientSession

from dazl import create_and_exercise, exercise
from dazl.model.core import ContractData

from daml_dit_if.api import \
    IntegrationEnvironment, IntegrationEvents


LOG = logging.getLogger('integration')


def normalize_coindesk_date(cd):
    return datetime.fromisoformat(cd).strftime("%Y-%m-%dT%H:%M:%SZ")


async def issue_coindesk_request(currencyCode):
    currencyCode = currencyCode.strip().upper()

    if len(currencyCode) != 3:
        return {
            'success': False,
            'httpStatusCode': -1,
            'httpResponseBody': f'Invalid currency code: {currencyCode}'
        }

    url = f'https://api.coindesk.com/v1/bpi/currentprice/{currencyCode}.json'
    async with ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                json = await resp.json(content_type='application/javascript')
                return {
                    'success': True,
                    'updatedAt': normalize_coindesk_date(json['time']['updatedISO']),
                    'rate': json['bpi'][currencyCode]['rate_float']
                }
            else:
                return {
                    'success': False,
                    'httpStatusCode': resp.status,
                    'httpResponseBody': await resp.text()
                }


async def update_oracle_commands(cid, currencyCode: str):
    LOG.debug('update_oracle_commands: %r, %r', cid, currencyCode)
    resp = await issue_coindesk_request(currencyCode)

    if resp['success']:
        return [exercise(cid, 'CurrentPriceOracleUpdater_Update', {
            'updatedAt': resp['updatedAt'],
            'rate': resp['rate']
        })]
    else:
        LOG.error('Invalid coindesk response (status: %r, body: %r)',
                  resp['httpStatusCode'], resp['httpResponseBody'])
        return []

def integration_coindesk_main(
        env: 'IntegrationEnvironment',
        events: 'IntegrationEvents'):

    # Request/Response style integration

    @events.ledger.contract_created('CoinDesk.PriceRequest:PriceRequest')
    async def on_contract_created(event):
        LOG.debug('Noticed new price request: %r', event)

        currencyCode = event.cdata['currencyCode']

        resp = await issue_coindesk_request(currencyCode)

        if resp['success']:
            return exercise(event.cid, 'PriceRequest_RespondSuccess', {
                'updatedAt': resp['updatedAt'],
                'rate': resp['rate']
            })
        else:
            return exercise(event.cid, 'PriceRequest_RespondFailure', {
                'httpStatusCode': resp['httpStatusCode'],
                'httpResponseBody': resp['httpResponseBody']
            })

    # Oracle style integration

    active_oracles = {}

    @events.ledger.contract_created('CoinDesk.PriceOracle:PriceOracleRequest')
    async def on_contract_created(event):
        LOG.debug('Noticed oracle request contract: %r (%r)', event.cid, event.cdata)

        currencyCode = event.cdata['currencyCode']

        active_oracles[event.cid] = currencyCode

        return await update_oracle_commands(event.cid, currencyCode)

    @events.ledger.contract_archived('CoinDesk.PriceOracle.PriceOracleRequest')
    async def on_ledger_archived(event):
        LOG.debug('Archived oracle request contract: %r', event.cid)
        active_oracles.pop(event.cid, None)

    @events.time.periodic_interval(30, label='Poll CoinDesk')
    async def poll_coindesk():

        cmds = []

        for (cid, currencyCode) in active_oracles.items():
            cmds.extend(await update_oracle_commands(cid, currencyCode))

        LOG.debug('Update commands: %r', cmds)

        return cmds

