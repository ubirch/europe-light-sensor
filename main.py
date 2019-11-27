import binascii
import json
from time import sleep
from uuid import UUID

import machine
import pycom
import wifi
from machine import I2C
from machine import Pin
from mqtt import MQTTClient
from ubirch.ubirch_client import UbirchClient

sda = Pin('P22', mode=Pin.IN)
scl = Pin('P21', mode=Pin.IN)
i2c = I2C(0, pins=('P22', 'P21'))  # create and use non-default PIN assignments (P10=SDA, P11=SCL)


def reset():
    # // send to 0x44, register 0x00, value 0x46 (RESET ISL29125)
    i2c.writeto_mem(0x44, 0x00, 0x0046, addrsize=16)
    # pins.i2cWriteNumber(0x44, 0x0046, NumberFormat.UInt16BE);

    # // send to 0x44, register 0x01, value 0x05 (GRB SAMPLING, 10kLUX)
    i2c.writeto_mem(0x44, 0x01, 0x05, addrsize=16)
    # pins.i2cWriteNumber(0x44, 0x0105, NumberFormat.UInt16BE);

    # // send to 0x44, register 0x02, value 0x05 (MAX IR FILTER)
    # pins.i2cWriteNumber(0x44, 0x02BF, NumberFormat.UInt16BE);
    i2c.writeto_mem(0x44, 0x02BF, 0x05, addrsize=16)


def main():
    pycom.heartbeat(False)
    reset()
    addr = i2c.scan()  # returns list of slave addresses
    print("in main: ")
    print(addr)
    # i2c.writeto(0x42, 'hello') # send 5 bytes to slave with address 0x42
    # bytesRead = i2c.readfrom(0x44, 5) # receive 5 bytes from slave

    # generate UUID
    uuid = UUID(b'UBIR' + 2 * machine.unique_id())
    print("\n** UUID   : " + str(uuid) + "\n")

    with open('config.json', 'r') as c:
        cfg = json.load(c)

        wifi.connect(cfg['networks'])
        wifi.set_time()

    # create MQTT client and connect
    client = MQTTClient(str(uuid), "mqtt.eclipse.org")
    client.connect()

    auth = cfg['password']
    headers = {
        'X-Ubirch-Hardware-Id': str(uuid),
        'X-Ubirch-Credential': binascii.b2a_base64(auth).decode('utf-8').rstrip('\n'),
        'X-Ubirch-Auth-Type': 'ubirch'
    }
    key_service_url = cfg['keyService']
    auth_service_url = cfg['niomon']

    ubirch = UbirchClient(uuid, headers, key_service_url, auth_service_url)

    while True:
        bytesRead = i2c.readfrom_mem(0x44, 0x09, 6, addrsize=8)

        green = (bytesRead[1] << 8) + bytesRead[0]
        red = (bytesRead[3] << 8) + bytesRead[2]
        blue = (bytesRead[5] << 8) + bytesRead[4]

        # print("red-green-blue " + hex((red << 32) + (green << 16) + blue))
        # print("red : " + hex(red << 16))
        # print("green.: " + hex(green << 8))
        # print("blue: " + hex(blue))
        rgb = (red << 16) + (green << 8) + blue
        print(hex(rgb))
        # pycom.rgbled(rgb)

        payload = bytearray(3)
        payload[0] = red
        payload[1] = green
        payload[2] = blue
        client.publish("europelight/fuerstenberg", payload)

        # send hash over data to ubirch niomon service
        message_hash = ubirch.hash(payload)
        ubirch.send(message_hash)

        sleep(60)
        # i2c.readfrom_mem(0x42, 0x10, 2) # read 2 bytes from slave 0x42, slave memory 0x10
        # i2c.writeto_mem(0x42, 0x10, 'xy') # write 2 bytes to slave 0x42, slave memory 0x10


main()
