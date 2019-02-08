#!/bin/bash

echo 0 > /proc/sys/net/ipv4/conf/eth0/send_redirects
ip ro ls default | grep default | cut -f3 -d' ' > /tmp/gw

/usr/bin/supervisord
