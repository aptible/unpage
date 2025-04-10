from unpage.plugins.aptible.nodes.base import AptibleNode


class AptibleVhost(AptibleNode):
    async def get_identifiers(self) -> list[str | None]:
        return [
            *await super().get_identifiers(),
            self.raw_data["virtual_domain"],
            self.raw_data["external_host"],
        ]

    async def get_reference_identifiers(
        self,
    ) -> list[str | None | tuple[str | None, str]]:
        return [
            *await super().get_reference_identifiers(),
            self.raw_data["security_group_id"],
            (self.raw_data["elastic_load_balancer_name"], "receives_traffic_from"),
            (self.raw_data["application_load_balancer_arn"], "receives_traffic_from"),
            self.raw_data["acme_dns_challenge_host"],
        ]
