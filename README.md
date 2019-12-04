Heat Spreader
=============

Heat Spreader controls OpenStack Heat stacks across multiple clouds.

Currently, it specifically controls a configurable count parameter on
templates that use a resource of type OS::Heat::ResourceGroup. It does this to
scale the number of instances a resource group should run in each cloud.

# Configuration

## OpenStack cloud configuration

The first thing you need to do is configure the different clouds that you want
to control. Heat Spreader uses the OpenStack SDK, read the
[configuration guide](https://docs.openstack.org/openstacksdk/latest/user/config/configuration.html)
on how to configure the cloud authentication.

## Heat Spreader configuration

When the clouds are configured the next step is to configure the Heat Spreader
configuration. The following configuration options are available:

* backend - Configuration for how the state should be persisted.
* clouds - A list of clouds that should be controlled.
* server - HTTP server configuration.

See the [example configurations](./examples) for a sample of a server and a
client configuration.

Heat Spreader, by default, looks for the config file at
`${HOME}/.config/openstack/heat-spreader.yaml`, to use a different config
file path set the environment variable `HEAT_SPREADER_CONFIG_FILE`.

# Usage

## Quickstart

**Start the HTTP API server and the scaling controller loop**

```
heat-spreader run
```

**Add a multicloud stack**

```
heat-spreader add [stack name] \
    --count [desired count] --parameter [stack count parameter]
```

**Add multicloud stack cloud weights**

```
heat-spreader weight set [stack name] [cloud 1 name] --weight 0.5
heat-spreader weight set [stack name] [cloud 2 name] --weight 0.5
```

## Environment variables

* HEAT_SPREADER_CONFIG_FILE - Configuration file path
* HEAT_SPREADER_LOG_JSON - Use JSON log output format
* HEAT_SPREADER_LOG_LEVEL - Log level (logging module level names)
* HEAT_SPREADER_LOG_VERBOSE - Include third-party library logs
* HEAT_SPREADER_LOG_FILE - Write logs to file instead of stdout

## Multicloud scaling

### Weights

When the desired count is calculated the total count is multiplied by the
weight each cloud has been configured with. For example, if a multicloud stack
configuration looks like this:
```
count: 10
cloud_1 weight: 0.6
cloud_2 weight: 0.2
cloud_3 weight: 0.2
```
The resulting count in each cloud's stack will be:
```
cloud_1 count: 6
cloud_2 count: 2
cloud_3 count: 2
```

### Failover

Whenever a cloud is unreachable the configured weight for that cloud will be
spread across the other reachable clouds evenly. For example, if a multicloud
stack configuration is the following:
```
count: 10
cloud_1 weight: 0.6
cloud_2 weight: 0.2
cloud_3 weight: 0.2
```
And `cloud_3` becomes unreachable, the resulting weights will become:
```
cloud_1 weight: 0.7
cloud_2 weight: 0.3
cloud_3 weight: 0.0
```
Which finally will make the count parameter in each stack to be updated to:
```
cloud_1 count: 7
cloud_2 count: 3
cloud_3 count: 0
```
Essentially rescheduling the resources lost due to the cloud being down.

# Q&A

Q: Why not simply use the remote stack feature in Heat, i.e. a stack resource
with region and credential attributes set?

A: The goals of this project and remote stacks in Heat are different. While
using remote stacks are great for creating and managing stacks in a remote
region from a local Heat deployment this project aims to view multiple remote
stacks as a single unit working in a collaborative fashion across multiple
clouds/regions.

One example of this is how the Heat Spreader controller reacts to a cloud no
longer being reachable by rescheduling the lost instances to any of the
cloud(s) that are still active.

# Limitations

## False-positive cloud failure detection

Currently the health checking mechanism is based on internal exceptions, e.g.
whether the scaling controller can communicate with Heat or not. Since a
connection failure can occur due to a lot of different reasons and not only an
actual cloud outage this could lead to an overcommit of resources until the
connection is again established.

This could be mitigated by implementing support for some form of external
distributed watchdog system.
