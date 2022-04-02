from machine import mem32, Pin

class SlaveI2C:
    I2C0_BASE = 0x40044000
    I2C1_BASE = 0x40048000
    IO_BANK0_BASE = 0x40014000
    
    mem_rw =  0x0000
    mem_xor = 0x1000
    mem_set = 0x2000
    mem_clr = 0x3000
    
    IC_CON = 0x00
    IC_TAR = 0x04
    IC_SAR = 0x08
    IC_SAR_MASK = 0x3ff
    IC_DATA_CMD = 0x10
    IC_DATA_CMD_DAT_MASK = 0xFF
    IC_DATA_CMD_CMD_MASK = 0x100
    IC_DATA_CMD_STOP_MASK = 0x200
    IC_DATA_CMD_RESTART_MASK = 0x400
    IC_DATA_CMD_FIRST_DATA_BYTE_MASK = 0x800
    IC_RAW_INTR_STAT = 0x34
    IC_RAW_INTR_STAT_RD_REQ_MASK = 0x20
    IC_RAW_INTR_STAT_STOP_DET_MASK = 0x200
    IC_RX_TL = 0x38
    IC_TX_TL = 0x3C
    IC_CLR_INTR = 0x40
    IC_CLR_RD_REQ = 0x50
    IC_CLR_TX_ABRT = 0x54
    IC_ENABLE = 0x6c
    IC_STATUS = 0x70
    IC_STATUS_RFNE_MASK = 0x08
    
    def write_reg(self, reg, data, method = 0):
        mem32[ self.i2c_base | method | reg] = data
        
    def set_reg(self, reg, data):
        self.write_reg(reg, data, method = self.mem_set)
        
    def clr_reg(self, reg, data):
        self.write_reg(reg, data, method = self.mem_clr)
                
    def __init__(self, i2c_id = 0, sda = 0,  scl = 1, address = 0x41):
        p0 = Pin(sda, pull = None)
        p1 = Pin(scl, pull = None)
        
        self.scl = scl
        self.sda = sda
        self.address = address
        self.i2c_id = i2c_id
        self.data_cmd_cache = None
        if self.i2c_id == 0:
            self.i2c_base = self.I2C0_BASE
        else:
            self.i2c_base = self.I2C1_BASE
        
        # 1 Disable DW_apb_i2c
        self.clr_reg(self.IC_ENABLE, 1)
        # 2 set slave address
        # clr bit 0 to 9
        # set slave address
        self.clr_reg(self.IC_SAR, 0x1ff)
        self.set_reg(self.IC_SAR, self.address & self.IC_SAR_MASK)
        # 3 write IC_CON  7 bit, enable in slave-only
        self.clr_reg(self.IC_CON, 0b01001001)
        # 3.1 Hold the bus when receive fifo is full
        self.set_reg(self.IC_CON, 0x200)
        # 3.2 Set the RX FIFO to maximum
        self.set_reg(self.IC_RX_TL, 0xFF)
        
        # set SDA PIN
        mem32[ self.IO_BANK0_BASE | self.mem_clr |  ( 4 + 8 * self.sda) ] = 0x1f
        mem32[ self.IO_BANK0_BASE | self.mem_set |  ( 4 + 8 * self.sda) ] = 3
        # set SLA PIN
        mem32[ self.IO_BANK0_BASE | self.mem_clr |  ( 4 + 8 * self.scl) ] = 0x1f
        mem32[ self.IO_BANK0_BASE | self.mem_set |  ( 4 + 8 * self.scl) ] = 3
        
        # 4 enable i2c 
        self.set_reg(self.IC_ENABLE, 1)

    def get_address(self):
        return self.slave_address

    def rd_req(self):
        status = mem32[ self.i2c_base | self.IC_RAW_INTR_STAT] & self.IC_RAW_INTR_STAT_RD_REQ_MASK
        if status:
            return True
        return False

    def put_byte(self, data):
        # reset flag       
        self.clr_reg(self.IC_CLR_TX_ABRT, 1)
        status = mem32[ self.i2c_base | self.IC_CLR_RD_REQ]
        mem32[ self.i2c_base | self.IC_DATA_CMD] = data  & self.IC_DATA_CMD_DAT_MASK

    def rfne(self):
        # get IC_STATUS
        status = mem32[ self.i2c_base | self.IC_STATUS]
        # check RFNE receive fifio not empty
        if (status &  self.IC_STATUS_RFNE_MASK):
            return True
        return False
    
    def get_command(self):
        if self.data_cmd_cache:
            command = self.data_cmd_cache & self.IC_DATA_CMD_DAT_MASK
            self.data_cmd_cache = None
            return command
        
        if not self.rfne():
            return None
        
        no_command = True
        # The 'command' byte is the first byte of the data stream
        while no_command:
            if not self.rfne():
                return None
            data_cmd = mem32[self.i2c_base | self.IC_DATA_CMD]
            if data_cmd & self.IC_DATA_CMD_FIRST_DATA_BYTE_MASK:
                no_command = False
                command = data_cmd & self.IC_DATA_CMD_DAT_MASK
        return command
    
    def get_byte(self):
        while not self.rfne():
            pass
        data_cmd = mem32[self.i2c_base | self.IC_DATA_CMD]
        if data_cmd & self.IC_DATA_CMD_FIRST_DATA_BYTE_MASK:
            self.data_cmd_cache = data_cmd
            return None
        else:
            return data_cmd & self.IC_DATA_CMD_DAT_MASK
    
if __name__ == "__main__":
    
    i2c = SlaveI2C(0, sda = 0, scl = 1, address = 0x41)
    counter = 1
    expected_command = 0
    try:
        while True:
            if i2c.rfne() or i2c.data_cmd_cache:
                command = i2c.get_command()
                if command is None:
                    continue
                data_bytes = []
                while len(data_bytes) < 4:
                    data = i2c.get_byte()
                    if data:
                        data_bytes.append(data)
                    else:
                        break
                if command == 0:
                    expected_command = 0
                    print('W', end = '')
                else:
                    expected_command += 1
                if command != expected_command:
                    print('Received unexpected command', command,'expected', expected_command)
                    break
                if len(data_bytes) != 4:
                    print('Expected length of data_bytes to be 4:', data_bytes)
                    break
                if data_bytes[0] != 0xF1 or data_bytes[1] != 3 or data_bytes[2] != 1 or data_bytes[3] != 255:
                    print('Unexpected data:', data_bytes)
                    break
                if command == 255:
                    # expected to write 2 bytes
                    i2c.put_byte(0x7f)
                    i2c.put_byte(0xf7)
                    print('R', end = '')
        
    except KeyboardInterrupt:
        pass