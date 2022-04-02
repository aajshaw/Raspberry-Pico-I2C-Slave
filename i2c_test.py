from machine import Pin, I2C

scl = Pin(1, pull = None)
sda = Pin(0)

i2c = I2C(0, scl = scl, sda = sda, freq = 100000)

devices = i2c.scan()

if len(devices) == 0:
    print('No I2C devices found')
else:
    print('Found', len(devices), 'I2C devices')
    for device in devices:
        print('Address Decimal:', device, 'Hex:', hex(device))
    
    # Try sending to 0x41
    buf = bytearray(5)
    buf[1] = 0xF1
    buf[2] = 3
    buf[3] = 1
    buf[4] = 255
    for test in range(100):
        for ndx in range(256):
            buf[0] = ndx
            acks = i2c.writeto(0x41, buf)
            if ndx == 255:
                # This is a read
                data = i2c.readfrom(0x41, 2)
                if data[0] != 0x7f or data[1] != 0xf7:
                    print('Invalid data received')
                    break