# Screenshots

Taken from a test PuppetDB with made-up nodes.

## Web interface

* Overview

![Overview](../screenshots/overview.png)

* Nodes view, all active nodes

![Nodes view, all active nodes](../screenshots/nodes.png)

* Single node

![Single node](../screenshots/node.png)

* Report view

![Report view](../screenshots/report.png)

* Failures view, the errors of all failing nodes

![Failures view](../screenshots/failures.png)

* Facts view

![Facts view](../screenshots/facts.png)

* Single fact, with graphs

![Single fact, with graphs](../screenshots/fact.png)

* All nodes that have this fact with that value

![All nodes that have this fact with that value](../screenshots/fact_value.png)

* Query view, results as table

![Query view](../screenshots/query_result_table.png)

* Query view, results as JSON

![Query view](../screenshots/query_result_json.png)

* Metrics view

![Metrics view](../screenshots/metrics.png)

* Single metric

![Single metric](../screenshots/metric.png)

* Inventory view

![Inventory view](../screenshots/inventory.png)

* Classes view, group the resource events of the last reports by Puppet class

![Classes view](../screenshots/classes.png)

* Class view, the nodes with at least one resource event in a given class

![Class view](../screenshots/class.png)

* Radiator view, for a wall display

![Radiator view](../screenshots/radiator.png)

## JSON API

Real `curl` calls and their answers, see [API.md](API.md#examples).

![Nodes that failed their last run](../screenshots/api_failed_nodes.png)

![Two facts of one node](../screenshots/api_node_facts.png)

![A PQL query for the status of all database nodes](../screenshots/api_pql.png)

## MCP server

Claude Code connected to `/mcp`, with the tool calls it made, see [MCP.md](MCP.md#examples).

![Which nodes failed their last Puppet run, and why?](../screenshots/mcp_failed_nodes.png)

![Which operating system versions do my nodes run, per environment?](../screenshots/mcp_os_versions.png)

![Which nodes have not reported to Puppet in the last hour?](../screenshots/mcp_unreported.png)
