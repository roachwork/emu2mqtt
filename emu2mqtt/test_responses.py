from emu2mqtt import responses
import xmltodict

def test_device_info():
    payload = '''<DeviceInfo>
        <DeviceMacId>0xd8d5b900000113ae</DeviceMacId>
        <InstallCode>0xbb35d34d84377160</InstallCode>
        <LinkKey>0x83f3ab2666b525cd75cd434c72c95e5e</LinkKey>
        <FWVersion>2.0.0 (7400)</FWVersion>
        <HWVersion>2.7.3</HWVersion>
        <ImageType>0x2201</ImageType>
        <Manufacturer>Rainforest Automation, Inc.</Manufacturer>
        <ModelId>Z105-2-EMU2-LEDD_JM</ModelId>
        <DateCode>2020051135221102</DateCode>
    </DeviceInfo>'''
    obj = responses.ResponseFactory(xmltodict.parse(payload))
    assert type(obj) == responses.DeviceInfo
    assert obj.device_mac_id == '0xd8d5b900000113ae'
    assert obj.response_key == 'device_info'

def test_connection_status():
    payload = '''<ConnectionStatus>
        <DeviceMacId>0xd8d5b900000113ae</DeviceMacId>
        <MeterMacId>0x00078100007a175d</MeterMacId>
        <Status>Connected</Status>
        <Description>Successfully Joined</Description>
        <ExtPanId>0x00078100007a175d</ExtPanId>
        <Channel>25</Channel>
        <ShortAddr>0x4969</ShortAddr>
        <LinkStrength>0x64</LinkStrength>
    </ConnectionStatus>'''
    obj = responses.ResponseFactory(xmltodict.parse(payload))
    assert type(obj) == responses.ConnectionStatus
    assert obj.device_mac_id == '0xd8d5b900000113ae'
    assert obj.response_key == 'connection_status'
    assert obj.link_strength == 100

def test_current_summation_delivered():
    payload = '''<CurrentSummationDelivered>
        <DeviceMacId>0xd8d5b900000113ae</DeviceMacId>
        <MeterMacId>0x00078100007a175d</MeterMacId>
        <TimeStamp>0x2db8b898</TimeStamp>
        <SummationDelivered>0x00000000095800be</SummationDelivered>
        <SummationReceived>0x0000000000000000</SummationReceived>
        <Multiplier>0x00000001</Multiplier>
        <Divisor>0x000003e8</Divisor>
        <DigitsRight>0x01</DigitsRight>
        <DigitsLeft>0x06</DigitsLeft>
        <SuppressLeadingZero>Y</SuppressLeadingZero>
    </CurrentSummationDelivered>'''
    obj = responses.ResponseFactory(xmltodict.parse(payload))
    assert type(obj) == responses.CurrentSummationDelivered
    assert obj.device_mac_id == '0xd8d5b900000113ae'
    assert obj.response_key == 'current_summation_delivered'
    assert obj.summation_delivered == 156762.3
    assert obj.summation_received == 0

class EmuTest():
    pass

def test_current_period_usage_time_cluster():
    time_payload = '''<TimeCluster>
        <DeviceMacId>0xd8d5b900000113ae</DeviceMacId>
        <MeterMacId>0x00078100007a175d</MeterMacId>
        <UTCTime>0x2dba38b2</UTCTime>
        <LocalTime>0x2db9c832</LocalTime>
    </TimeCluster>'''
    time = responses.ResponseFactory(xmltodict.parse(time_payload))
    ref = EmuTest()
    ref.time_cluster = time

    assert type(time) == responses.TimeCluster
    assert time.device_mac_id == '0xd8d5b900000113ae'
    assert time.response_key == 'time_cluster'
    assert time.local_time == 767150130
    assert time.utctime == 767178930

    payload = '''<CurrentPeriodUsage>
        <DeviceMacId>0xd8d5b900000113ae</DeviceMacId>
        <MeterMacId>0x00078100007a175d</MeterMacId>
        <TimeStamp>0xffffffff</TimeStamp>
        <CurrentUsage>0x0000000000005a3a</CurrentUsage>
        <Multiplier>0x00000001</Multiplier>
        <Divisor>0x000003e8</Divisor>
        <DigitsRight>0x01</DigitsRight>
        <DigitsLeft>0x00</DigitsLeft>
        <SuppressLeadingZero>Y</SuppressLeadingZero>
        <StartDate>0x2db82ad2</StartDate>
    </CurrentPeriodUsage>'''
    obj = responses.ResponseFactory(xmltodict.parse(payload), emu=ref)

    assert type(obj) == responses.CurrentPeriodUsage
    assert obj.device_mac_id == '0xd8d5b900000113ae'
    assert obj.response_key == 'current_period_usage'

    adjusted_date = obj.reported_start_date + obj.local_time_offset
    adjusted_date = adjusted_date - (adjusted_date % 300)
    assert obj.start_date == adjusted_date

def test_instantaneous_demand():
    payload = '''<InstantaneousDemand>
        <DeviceMacId>0xd8d5b900000113ae</DeviceMacId>
        <MeterMacId>0x00078100007a175d</MeterMacId>
        <TimeStamp>0x2db8b962</TimeStamp>
        <Demand>0x0004ad</Demand>
        <Multiplier>0x00000001</Multiplier>
        <Divisor>0x000003e8</Divisor>
        <DigitsRight>0x03</DigitsRight>
        <DigitsLeft>0x06</DigitsLeft>
        <SuppressLeadingZero>Y</SuppressLeadingZero>
    </InstantaneousDemand>'''
    obj = responses.ResponseFactory(xmltodict.parse(payload))
    assert type(obj) == responses.InstantaneousDemand
    assert obj.device_mac_id == '0xd8d5b900000113ae'
    assert obj.response_key == 'instantaneous_demand'
    assert obj.demand == 1.197

def test_last_period_usage():
    payload = '''<LastPeriodUsage>
        <DeviceMacId>0xd8d5b900000113ae</DeviceMacId>
        <MeterMacId>0x00078100007a175d</MeterMacId>
        <LastUsage>0x0000000002473708</LastUsage>
        <Multiplier>0x00000001</Multiplier>
        <Divisor>0x000003e8</Divisor>
        <DigitsRight>0x01</DigitsRight>
        <DigitsLeft>0x00</DigitsLeft>
        <SuppressLeadingZero>Y</SuppressLeadingZero>
        <StartDate>0x28a58a8e</StartDate>
        <EndDate>0x2db82a96</EndDate>
    </LastPeriodUsage>'''
    obj = responses.ResponseFactory(xmltodict.parse(payload))
    assert type(obj) == responses.LastPeriodUsage
    assert obj.device_mac_id == '0xd8d5b900000113ae'
    assert obj.response_key == 'last_period_usage'
    assert obj.last_usage == 38221.6

def test_price_cluster():
    payload = '''<PriceCluster>
        <DeviceMacId>0xd8d5b900000113ae</DeviceMacId>
        <MeterMacId>0x00078100007a175d</MeterMacId>
        <TimeStamp>0x2db8c655</TimeStamp>
        <Price>0x0000013b</Price>
        <Currency>0x0348</Currency>
        <TrailingDigits>0x03</TrailingDigits>
        <Tier>0x01</Tier>
        <StartTime>0xffffffff</StartTime>
        <Duration>0xffff</Duration>
        <RateLabel>Set by User</RateLabel>
    </PriceCluster>'''
    obj = responses.ResponseFactory(xmltodict.parse(payload))
    assert type(obj) == responses.PriceCluster
    assert obj.device_mac_id == '0xd8d5b900000113ae'
    assert obj.response_key == 'price_cluster'
    assert obj.price == 31.5


def test_price_format():
    cls = responses.Response
    assert cls.format_price('1.1') == (cls.to_hex(11), cls.to_hex(3))
    assert cls.format_price('31.50') == (cls.to_hex(315), cls.to_hex(3))
    assert cls.format_price('111.111') == (cls.to_hex(111111), cls.to_hex(5))
    assert cls.format_price('1.11') == (cls.to_hex(111), cls.to_hex(4))