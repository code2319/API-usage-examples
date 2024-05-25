from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.auth import HTTPBasicAuth


def group_id_from_name(node_group_bean_client, group_name) -> str:
    """
    :returns group id from specific name
    """
    # node_groups = [{'created': None, 'id': '', 'modified': None, 'name': '', 'status': '', 'uuid': ''},]
    node_groups = node_group_bean_client.service.getNodeGroups("*")

    node_group_id = "".join(
        [
            node_group["id"]
            for node_group in node_groups
            if node_group["name"] == group_name
        ]
    )
    print(f"{group_name} id = {node_group_id}")
    return node_group_id


def get_nodes(node_group_bean_client, node_bean_client, group_name) -> dict:
    """
    :returns
    {
        'key1': [
            {
                'key1.1': 'value1.1',
            }
        ],
        'key2': 'value2',
    }
    """
    get_member_ids = node_group_bean_client.service.getMemberIds(
        group_id_from_name(node_group_bean_client, group_name)
    )

    # for type_factory and available prefixes
    # print(node_bean_client.wsdl.dump())

    prefix_map = node_bean_client.wsdl.types.prefix_map
    for prefix, namespace in prefix_map.items():
        # we take only the one that is responsible for the filter
        # in different versions this may be a different prefix !!!
        if "filter" in namespace:
            # retrieve nodes info; getNodes(Filter filter)
            for member_id in get_member_ids:
                type_factory = node_bean_client.type_factory(prefix)
                # The filter must include a Constraint having includeCustomAttributes
                constraint = type_factory.constraint(
                    name="includeCustomAttributes", value=True
                )
                condition = type_factory.condition(
                    name="id", operator="EQ", value=member_id
                )
                filterr = type_factory.expression(
                    operator="AND", subFilters=[constraint, condition]
                )
                get_nodes = node_bean_client.service.getNodes(filterr)
                for nodes in get_nodes:
                    return nodes  # type(nodes) = zeep.objects.node


if __name__ == "__main__":
    """
    https://docs.microfocus.com/doc/Network_Node_Manager_i/10.50/NnmiWsiApi
    """
    session = Session()
    session.auth = HTTPBasicAuth("login", "password")
    session.verify = False

    node_group_bean_wsdl = "https://127.0.0.1/NodeGroupBeanService/NodeGroupBean?wsdl"
    node_bean_wsdl = "https://127.0.0.1/NodeBeanService/NodeBean?wsdl"

    node_group_bean_client = Client(
        wsdl=node_group_bean_wsdl, transport=Transport(session=session)
    )
    node_bean_client = Client(wsdl=node_bean_wsdl, transport=Transport(session=session))

    print(
        get_nodes(
            node_group_bean_client, node_bean_client, group_name="our_specific_group"
        )
    )
