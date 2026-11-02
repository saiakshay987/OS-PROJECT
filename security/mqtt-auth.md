```
# on the laptop (P3's machine): username/password + topic ACL
mosquitto_passwd -c "C:\Program Files\mosquitto\passwd" board
mosquitto_passwd    "C:\Program Files\mosquitto\passwd" laptop
# mosquitto.conf
listener 1883 192.168.2.1
allow_anonymous false
password_file C:\Program Files\mosquitto\passwd
acl_file      C:\Program Files\mosquitto\acl
# acl
user board
topic write pynq/features
topic write pynq/status
topic read  laptop/command
user laptop
topic read  pynq/#
topic readwrite laptop/command
# the board's password goes ONLY in /data/voice.conf on the board (MQTT_PASS=..., mode 600, root)
```
