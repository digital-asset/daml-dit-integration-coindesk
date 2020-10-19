# Copyright (c) 2020, Digital Asset (Switzerland) GmbH and/or its affiliates.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging

from dataclasses import dataclass

from datetime import datetime

from aiohttp import ClientSession

from dazl import create_and_exercise, exercise
from dazl.model.core import ContractData

from daml_dit_api import \
    IntegrationEnvironment, IntegrationEvents


LOG = logging.getLogger('integration')


def normalize_coindesk_date(cd):
    return datetime.fromisoformat(cd).strftime("%Y-%m-%dT%H:%M:%SZ")


async def issue_coindesk_request(currencyCode):
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


def integration_coindesk_price_request_main(
        env: 'IntegrationEnvironment',
        events: 'IntegrationEvents'):

    @events.ledger.contract_created('CoinDesk.PriceRequest:PriceRequest')
    async def on_contract_created(event):
        LOG.info('on_contract_created: %r', event)

        currencyCode = event.cdata['currencyCode'].strip().upper()

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


@dataclass
class IntegrationCoinDeskPriceOracleEnv(IntegrationEnvironment):
    currencyCode: str
    updatePeriod: int


def integration_coindesk_price_oracle_main(
        env: 'IntegrationCoinDeskPriceOracleEnv',
        events: 'IntegrationEvents'):

    @events.time.periodic_interval(env.updatePeriod)
    async def poll_coindesk():
        resp = await issue_coindesk_request(env.currencyCode.upper())

        if not resp['success']:
            LOG.error('Invalid coindesk response (status: %r, body: %r)',
                      resp['httpStatusCode'], resp['httpResponseBody'])
            return []

        return [create_and_exercise(
            'CoinDesk.PriceOracle.CurrentPriceOracleUpdater',
            {'integrationParty': env.party},
            'CurrentPriceOracleUpdater_Update',
            {'currencyCode': env.currencyCode,
             'updatedAt': resp['updatedAt'],
             'rate': resp['rate']})]
