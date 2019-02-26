#!/usr/bin/env python3
from lightning import Plugin
from prometheus_client import start_http_server, CollectorRegistry
from prometheus_client.core import InfoMetricFamily, GaugeMetricFamily
from sys import exit

plugin = Plugin()


class BaseLnCollector(object):
    def __init__(self, rpc, registry):
        self.rpc = rpc
        self.registry = registry


class NodeCollector(BaseLnCollector):
    def collect(self):
        info = self.rpc.getinfo()
        info_labels = {k: v for k, v in info.items() if isinstance(v, str)}
        node_info_fam = InfoMetricFamily(
            'node',
            'Static node information',
            labels=info_labels.keys(),
        )
        node_info_fam.add_metric(info_labels, info_labels)
        yield node_info_fam


class FundsCollector(BaseLnCollector):
    def collect(self):
        funds = self.rpc.listfunds()
        print(funds['outputs'])
        output_funds = sum(
            [o['amount_msat'].to_satoshi() for o in funds['outputs']]
        )
        channel_funds = sum(
            [c['our_amount_msat'].to_satoshi() for c in funds['channels']]
        )
        total = output_funds + channel_funds

        yield GaugeMetricFamily(
            'total_funds',
            "Total satoshis we own on this node.",
            value=total,
        )
        yield GaugeMetricFamily(
            'output_funds',
            "On-chain satoshis at our disposal",
            value=output_funds,
        )
        yield GaugeMetricFamily(
            'channel_funds',
            "Satoshis in channels.",
            value=channel_funds,
        )


class PeerCollector(BaseLnCollector):
    def collect(self):
        peers = self.rpc.listpeers()['peers']

        connected = GaugeMetricFamily(
            'connected',
            'Is the peer currently connected?',
            labels=['id'],
        )
        count = GaugeMetricFamily(
            'num_channels',
            "The number of channels with the peer",
            labels=['id'],
        )

        for p in peers:
            labels = [p['id']]
            count.add_metric(labels, len(p['channels']))
            connected.add_metric(labels, int(p['connected']))

        return [count, connected]


class ChannelsCollector(BaseLnCollector):
    def collect(self):
        balance_gauge = GaugeMetricFamily(
            'channel_balance',
            'How many funds are at our disposal?',
            labels=['id', 'scid'],
        )
        spendable_gauge = GaugeMetricFamily(
            'channel_spendable',
            'How much can we currently send over this channel?',
            labels=['id', 'scid']
        )
        total_gauge = GaugeMetricFamily(
            'channel_total',
            'How many funds are in this channel in total?',
            labels=['id', 'scid'],
        )
        htlc_gauge = GaugeMetricFamily(
            'channel_htlcs',
            'How many HTLCs are currently active on this channel?',
            labels=['id', 'scid'],
        )

        peers = self.rpc.listpeers()['peers']
        for p in peers:
            for c in p['channels']:
                labels = [p['id'], c['short_channel_id']]
                balance_gauge.add_metric(labels, c['to_us_msat'].to_satoshi())
                spendable_gauge.add_metric(labels,
                                           c['spendable_msat'].to_satoshi())
                total_gauge.add_metric(labels, c['total_msat'].to_satoshi())
                htlc_gauge.add_metric(labels, len(c['htlcs']))

        return [htlc_gauge, total_gauge, spendable_gauge, balance_gauge]


@plugin.init()
def init(options, configuration, plugin):
    s = options['prometheus-listen'].rpartition(':')
    if len(s) != 3 or s[1] != ':':
        print("Could not parse prometheus-listen address")
        exit(1)
    ip, port = s[0], int(s[2])

    registry = CollectorRegistry()
    start_http_server(addr=ip, port=port, registry=registry)
    registry.register(NodeCollector(plugin.rpc, registry))
    registry.register(FundsCollector(plugin.rpc, registry))
    registry.register(PeerCollector(plugin.rpc, registry))
    registry.register(ChannelsCollector(plugin.rpc, registry))


plugin.add_option(
    'prometheus-listen',
    '0.0.0.0:9900',
    'Address and port to bind to'
)


plugin.run()
