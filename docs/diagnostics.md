# Portable network diagnostics

Kali is not required. The NOCtv Docker image installs `iputils-ping`, `traceroute`,
`dnsutils` and `nmap`; **Tools → Network diagnostics** offers Ping, Traceroute,
reverse DNS, a small TCP port scan and limited service detection. Commands run in
the NOCtv container/server, never on the browser or TV.

Demo results are explicitly simulated and execute no command. Live diagnostics
are disabled by default. Enable them only for networks the operator administers:

```json
"diagnostics": {
  "enabled": true,
  "allowed_cidrs": ["192.0.2.0/24", "2001:db8:1234::/48"]
}
```

These are documentation ranges; replace them locally with authorized ranges.
Inputs accept one literal IP, never hostnames, subnets, shell commands or custom
flags. Loopback, link-local, multicast and unspecified targets are rejected.
CIDR matching happens server-side. All authenticated dashboard viewers can run
these tools when enabled; this release has no separate operator role.

Commands use fixed arguments, no shell, no connector secrets in their environment,
one active run per process, a 5-second cooldown and a 35-second timeout. Output is
limited to 16 KiB. Nmap uses unprivileged TCP connect scanning. There are no exploit
scripts, raw SYN scans or privileged containers. The request requires the same
live viewer authentication as the dashboard plus a same-origin custom header;
NOCtv does not enable cross-origin API access.

The supplied Linux Compose configuration uses UID 10001, drops all capabilities
and permits unprivileged ICMP echo sockets through `net.ipv4.ping_group_range`.
Routing, firewall rules and runtime support still determine which targets are
reachable; the container sees its own network namespace. Docker runtime behavior
must be checked on the installation host. No Docker socket is required.

For a native Debian/Ubuntu installation, an administrator may install:

```sh
sudo apt-get install iputils-ping traceroute dnsutils nmap
```

Other distributions use their equivalent packages. The UI identifies missing
binaries. Python alone is enough for the simulated demo and HTTP/TCP checks.
Installing these packages on the host is unnecessary when running the image.

To disable live diagnostics, set `enabled` to false and restart. This does not
change upstream LibreNMS/Zabbix schedules or explicitly configured
[native service checks](services.md).

References: [Linux ICMP socket permissions](https://kernel.org/doc/html/latest/networking/ip-sysctl.html),
[Nmap TCP connect scans](https://nmap.org/book/man-port-scanning-techniques.html),
[Compose sysctls](https://docs.docker.com/reference/compose-file/services/#sysctls).
