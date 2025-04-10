import os
import socket
import statistics
import time

import dns.resolver
import requests
from dns.exception import Timeout as DnsTimeout
from scapy.all import sr1
from scapy.layers.inet import ICMP, IP, UDP

from unpage.plugins import Plugin
from unpage.plugins.mixins import McpServerMixin, tool


class NetworkingPlugin(Plugin, McpServerMixin):
    """A plugin for providing common networking tools."""

    @tool()
    def ping(self, host: str) -> str:
        """Ping a host and return the result."""
        for segment in host.split("."):
            if len(segment) > 63:
                raise ValueError(
                    f"'{host}' host has a segment longer than 63 characters, which is not supported by dns"
                )
        try:
            target_ip = socket.gethostbyname(host)
        except socket.gaierror:
            return f"ping: cannot resolve {host}: Unknown host"
        result = f"PING {host} ({target_ip}): 56 data bytes\n"
        packets_transmitted = 0
        packets_received = 0
        rtt_values = []
        for i in range(4):
            packet = IP(dst=target_ip) / ICMP(id=os.getpid() & 0xFFFF, seq=i)
            reply = sr1(packet, verbose=0, timeout=1)
            packets_transmitted += 1
            if reply and reply.haslayer(ICMP) and reply[ICMP].type == 0:
                packets_received += 1
                rtt = (reply.time - packet.sent_time) * 1000  # pyright: ignore[reportOperatorIssue]
                rtt_values.append(rtt)
                result += f"64 bytes from {reply[IP].src} icmp_seq={i} ttl={reply[IP].ttl} time={rtt:.3f} ms\n"
            else:
                result += f"Request timeout for icmp_seq {i}\n"
            time.sleep(1)
        result += f"\n--- {host} ping statistics ---\n"
        result += (
            f"{packets_transmitted} packets transmitted, {packets_received} packets received, "
            f"{((packets_transmitted - packets_received) / packets_transmitted * 100):.1f}% packet loss\n"
        )
        if rtt_values:
            min_rtt = min(rtt_values)
            avg_rtt = statistics.mean(rtt_values)
            max_rtt = max(rtt_values)
            stddev_rtt = statistics.stdev(rtt_values) if len(rtt_values) > 1 else 0.0
            result += f"round-trip min/avg/max/stddev = {min_rtt:.3f}/{avg_rtt:.3f}/{max_rtt:.3f}/{stddev_rtt:.3f} ms\n"
        return result

    @tool()
    def dig(self, hostname: str, record_type: str = "A") -> str:
        """Use the 'dig' command to resolve a hostname and return the result."""
        result = ""
        try:
            resolver = dns.resolver.Resolver()
            answers = resolver.resolve(hostname, record_type)
            for rdata in answers:
                result += str(rdata) + "\n"
        except dns.resolver.NXDOMAIN:
            result = f"Host '{hostname}' not found."
        except dns.resolver.NoAnswer:
            result = f"No record found for '{hostname}' with type '{record_type}'."
        except DnsTimeout:
            result = "Timeout while querying DNS server."

        return result

    @tool()
    def traceroute(self, destination: str, max_hops: int = 30) -> str:
        """Trace the route to a destination and return the result."""
        result = ""
        for ttl in range(1, max_hops + 1):
            packet = IP(dst=destination, ttl=ttl) / UDP(dport=33434)
            reply = sr1(packet, verbose=0, timeout=1)
            if reply is None:
                result += f"{ttl}\t* * * Request timed out.\n"
            elif reply.haslayer(ICMP) and reply[ICMP].type == 11:
                result += f"{ttl}\t{reply.src}\n"
            elif reply.haslayer(ICMP) and reply[ICMP].type == 3:
                result += f"{ttl}\t{reply.src} Destination reached.\n"
                break
            else:
                result += f"{ttl}\t{reply.src} Other reply type.\n"

        return result

    @tool()
    def request_url(self, url: str) -> str:
        """Request a URL with the GET method and return the result."""
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
