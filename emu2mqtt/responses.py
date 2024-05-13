import arrow
import decimal
import json

from caseconverter import snakecase


class GenericResponse:
    ''' Shared class to support the required '''
    def __init__(self, response_key: str, payload: dict):
        self.response_key = response_key
        self.payload = payload

    def to_dict(self) -> dict:
        return self.payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def __repr__(self) -> str:
        return '<{} {}={}>'.format(self.__class__.__name__, self.response_key, self.payload)


class MqttMessage(GenericResponse):
    ''' Class to send a general message to mqtt '''
    pass


class Status(GenericResponse):
    ''' Class to track whether the serial device is connected or not '''
    def __init__(self, payload: dict):
        super().__init__('status', payload)


class Response:
    ''' Parent class that sets a consistent response format from the emu-2 device '''
    def __init__(self, response: dict, emu=None):
        '''
        response is a dict version of the XML data from the emu-2 device. Ex:
        {'DeviceInfo': {'MacMeterId': '0x1234'}}

        Note that we pass an instance of the emu class so we can get access
        to the data that has been sent from the emu-2 device when it is needed
        in child instances of this class
        '''
        self._response = response
        self.emu = emu
        self._format()

    @classmethod
    def format_price(cls, cents: str='0.0') -> tuple[str, int]:
        ''' Format cents into the format that the emu-2 device expects '''
        price = decimal.Decimal(cents) / 100
        _, _, digits = price.normalize().as_tuple()
        price = str(price.normalize().rotate(-1 * digits).normalize())
        return (cls.to_hex(int(price)), cls.to_hex(-1 * digits))

    @classmethod
    def to_hex(cls, number: int) -> str:
        ''' Convert a number to hex '''
        return '0x{:X}'.format(number)

    @property
    def response_type(self):
        '''
        Get the response type from the data payload that was sent.
        We use the parent xml tag as the response type.
        Ex: 'DeviceInfo'
        '''
        return list(self._response.keys())[0]

    @property
    def response_key(self) -> str:
        '''
        The response_type but in snake_case format. This is used as the mqtt
        topic to send the emu-2 response to.
        Ex: device_info
        '''
        return snakecase(self.response_type)

    def to_int(self, value) -> int:
        ''' Convert hex to an int '''
        return int(value or '0x00', 16)

    def to_formatted(self, value: int) -> float:
        ''' Convert the numeric formatting that the emu-2 provides to a human readable format '''
        try:
            return round(value * self.multiplier / float(self.divisor), self.digits_right)
        except ZeroDivisionError:
            return 0

    def _format(self) -> None:
        ''' Store the response data from the emu-2 in a consistent format as attributes '''
        for key in self._response[self.response_type]:
            setattr(self, snakecase(key), self._response[self.response_type][key])

    def to_dict(self) -> dict:
        ''' Convert the attributes from the emu-2 device into a dict to send to mqtt '''
        return {attr: getattr(self, attr, None) for attr in self.__dict__.keys() if not attr.startswith('_') and attr != 'emu' }

    def to_json(self) -> str:
        ''' The json payload of the emu-2 data that will be sent to mqtt '''
        return json.dumps(self.to_dict())

    def __repr__(self) -> str:
        return '<{}>'.format(self.__class__.__name__)


class ResponseFactory:
    '''
    Send the XML data (as a dict) from the emu-2 device to this factory and
    it will provide the appropriate response object based on the incoming type
    Note that the emu instance is an optional parameter for tracking data
    already received from the emu-2 device
    '''
    def __new__(cls, response: dict, emu=None):
        response_types = {klass.__name__: klass for klass in Response.__subclasses__()}
        response_type = list(response.keys())[0]
        if response_type in response_types:
            return response_types[response_type](response, emu=emu)
        raise NotImplementedError(f'Response type "{response_type}" is not defined')


class DeviceInfo(Response):
    ''' Information about the emu-2 device '''
    pass


class ConnectionStatus(Response):
    ''' Information about the connection status between the emu-2 device and the meter '''
    def _format(self) -> None:
        ''' Update the link strength to an int '''
        super()._format()
        self.link_strength = self.to_int(self.link_strength)


class Demand(Response):
    ''' Parent class setting common calculated demand properties '''
    def _format(self) -> None:
        ''' Convert common dates and number formats to appropriate formats '''
        super()._format()
        self.multiplier = self.to_int(self.multiplier)
        self.divisor = self.to_int(self.divisor)
        self.digits_right = self.to_int(self.digits_right)
        self.digits_left = self.to_int(self.digits_left)

        # dates from the emu are really bad, so we get the current time
        # from the emu and compare it to the current time as an offset
        # the emu is passed as an argument so we can look it up
        try:
            self.local_time_offset = self.emu.time_cluster.local_time_offset
        except AttributeError:
            pass

        if hasattr(self, 'local_time_offset'):
            if getattr(self, 'time_stamp', None):
                self.time_stamp = self.to_int(self.time_stamp)
                self.reported_time_stamp = self.time_stamp
                self.time_stamp = self.time_stamp + self.local_time_offset
            if getattr(self, 'start_date', None):
                self.start_date = self.to_int(self.start_date)
                self.reported_start_date = self.start_date
                # This is where the offset is applied
                # Also round down the nearest 5 minute so second changes don't cause state updates
                self.start_date = self.start_date + self.local_time_offset
                self.start_date = self.start_date - (self.start_date % 300)
            if getattr(self, 'end_date', None):
                self.end_date = self.to_int(self.end_date)
                self.reported_end_date = self.end_date
                self.end_date = self.end_date + self.local_time_offset


class CurrentSummationDelivered(Demand, Response):
    ''' Get the total received and delivered data from the meter '''
    def _format(self) -> None:
        ''' Convert the emu-2 style values to human readable values '''
        super()._format()
        self.summation_delivered = self.to_formatted(self.to_int(self.summation_delivered))
        self.summation_received = self.to_formatted(self.to_int(self.summation_received))


class CurrentPeriodUsage(Demand, Response):
    ''' Get the current period usage from the emu-2 device '''
    def _format(self) -> None:
        ''' Format the current usage from emu-2 format '''
        super()._format()
        self.current_usage = self.to_formatted(self.to_int(self.current_usage))


class LastPeriodUsage(Demand, Response):
    ''' Get the usage from the previous period '''
    def _format(self) -> None:
        ''' Format the current usage from emu-2 format '''
        super()._format()
        self.last_usage = self.to_formatted(self.to_int(self.last_usage))


class InstantaneousDemand(Demand, Response):
    ''' Get the current demand that the meter sees '''
    def _format(self) -> None:
        ''' Format the current demand from emu-2 format '''
        super()._format()
        self.demand = self.to_int(self.demand)
        self.demand = self.to_formatted(self.demand)


class PriceCluster(Response):
    ''' Get the current price from the emu-2 device '''
    def _format(self) -> None:
        ''' Format the price '''
        super()._format()
        self.reported_price = self.price
        self.price = None if self.price == '0xffffffff' else self.to_int(self.price)
        self.currency = self.to_int(self.currency)
        self.tier = self.to_int(self.tier)
        self.trailing_digits = self.to_int(self.trailing_digits)

        # Convert the price to cents
        if self.price:
            self.price = self.price / (10 ** (self.trailing_digits - 2))


class TimeCluster(Response):
    '''
    Get the current time from the emu-2 device.
    The time seems really inconsistent so we calculate an offset based on the current time
    Note that it seems that DST is not supported?
    '''
    def _format(self) -> None:
        ''' Format the different times '''
        super()._format()
        self.utctime = self.to_int(self.utctime)
        self.local_time = self.to_int(self.local_time)
        now = arrow.now()
        self.local_time_offset = int(now.timestamp() - self.local_time + now.utcoffset().total_seconds())
