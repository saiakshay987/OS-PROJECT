# MQTT authentication and topic rules (broker on the demo laptop)

```
mosquitto_passwd -c passwd appliance
mosquitto_passwd    passwd laptop
# in mosquitto.conf, replace 'allow_anonymous true' with:
allow_anonymous false
password_file passwd
acl_file acl
# acl
user appliance
topic read  net/flows
topic read  ids/verdict
topic write ids/alert
topic write ids/status
user laptop
topic write net/flows
topic write ids/verdict
topic read  ids/#
```
The appliance's password goes only in `/data/ids.conf` (`MQTT_USER=appliance`, `MQTT_PASS=...`, mode 600), never in git.
