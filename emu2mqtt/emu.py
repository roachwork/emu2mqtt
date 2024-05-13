import aiomqtt
import arrow
import asyncio
import logging
import os
from pathlib import Path
import serial_asyncio
import signal
from serial import SerialException
from typing import Callable
import xmltodict

from entities import generate_entities
from responses import DeviceInfo, MqttMessage, Response, ResponseFactory, Status


logger = logging.getLogger(__name__)

class Emu2:
    '''
    The class responsible for:
    * Communication with the EMU-2 device
    * Sending info to MQTT
    * Receiving commands from MQTT
    * Scheduling updates between the two
    * Probably too much
    '''
    connected: bool = False
    disconnecting: bool = False
    reader: asyncio.StreamReader = None
    writer: asyncio.StreamWriter = None
    device_info: DeviceInfo = None
    poll_offset: int = 0
    homeassistant_birth: str = 'homeassistant/status'
    healthcheck_file: str = '/app/healthcheck'
    healthcheck_path: Path = None

    def __init__(self):
        ''' Initiate the class and store references to async queues '''
        self.mqtt_queue = asyncio.Queue()
        self.serial_queue = asyncio.Queue()
        self.healthcheck_path = Path(self.healthcheck_file)
        self.homeassistant_birth = os.environ.get('MQTT_HA_STATUS', self.homeassistant_birth)

    def mqtt_config(self) -> tuple[str, str | int, dict, str]:
        ''' Get the config for the mqtt server '''
        return (
            os.environ.get('MQTT_HOSTNAME', '127.0.0.1'),
            os.environ.get('MQTT_PORT', 1883),
            {
                'username': os.environ.get('MQTT_USERNAME'),
                'password': os.environ.get('MQTT_PASSWORD'),
            },
            os.environ.get('MQTT_PREFIX', 'emu2')
        )

    def serial_config(self) -> dict[str]:
        ''' Get the config for the serial interface '''
        return {
            'url': os.environ.get('SERIAL_DEVICE', '/dev/ttyACM0'),
            'baudrate': os.environ.get('SERIAL_BAUDRATE', 115200)
        }

    async def send_discovery(self) -> None:
        ''' Send the entity config for discovery in home assistant '''
        if self.device_info:
            logger.info('Sending device discovery to Home Assistant')
            topic_prefix = os.environ.get('MQTT_PREFIX', 'emu2')
            entities = generate_entities(topic_prefix, self.device_info)
            for entity in entities:
                entity_type = entity.pop('type')
                topic = f'homeassistant/{entity_type}/{entity["unique_id"]}/config'
                payload = MqttMessage(topic, entity)
                self.mqtt_queue.put_nowait(payload)

            await asyncio.sleep(2)
            self.send_status()

    async def queue_discovery(self) -> None:
        ''' Queue the entity discovery for home assistant '''
        while True:
            if self.device_info:
                await self.send_discovery()
                break
            else:
                await asyncio.sleep(10)


    async def mqtt_reader(self) -> None:
        ''' Subscribe to necessary mqtt topics to send commands to the emu device '''
        while not self.disconnecting:
            try:
                hostname, port, credentials, topic_prefix = self.mqtt_config()
                async with aiomqtt.Client(hostname, port, **credentials) as client:
                    logger.info('Reader connected to mqtt broker')
                    await client.subscribe(f'{topic_prefix}/command')
                    await client.subscribe(f'{topic_prefix}/reinitialize')
                    await client.subscribe(f'{topic_prefix}/close_current_period')
                    await client.subscribe(f'{topic_prefix}/restart')
                    await client.subscribe(f'{topic_prefix}/set_current_price')
                    await client.subscribe(self.homeassistant_birth)
                    async for message in client.messages:
                        logger.debug('Got mqtt message %s from %s' % (message.payload, message.topic))
                        topic = str(message.topic)

                        if topic == f'{topic_prefix}/close_current_period':
                            self.close_current_period()
                            continue

                        if topic == f'{topic_prefix}/restart':
                            self.restart()
                            continue

                        try:
                            payload = message.payload.decode()
                        except Exception as e:
                            logger.warning('Failed to decode mqtt message %s' % e)
                            continue

                        if topic == self.homeassistant_birth and payload == 'online':
                            await self.reinitialize()
                            continue

                        if topic == f'{topic_prefix}/reinitialize':
                            await self.reinitialize()
                            continue

                        if topic == f'{topic_prefix}/set_current_price':
                            await self.set_current_price(payload)
                            continue

                        if topic == f'{topic_prefix}/command':
                            self.serial_queue.put_nowait(payload)
                            continue

            except aiomqtt.MqttError:
                logger.warning('Reader reconnecting to mqtt broker in 5 seconds...')
                await asyncio.sleep(5)

    async def mqtt_writer(self) -> None:
        ''' Send data to mqtt '''
        while not self.disconnecting:
            try:
                hostname, port, credentials, topic_prefix = self.mqtt_config()
                async with aiomqtt.Client(hostname, port, **credentials) as client:
                    logger.info('Writer connected to mqtt broker')
                    try:
                        while True:
                            event = await self.mqtt_queue.get()
                            if isinstance(event, MqttMessage):
                                topic = event.response_key
                            else:
                                topic = f'{topic_prefix}/{event.response_key}'
                            message = event.to_json()
                            logger.debug('Sent mqtt message to %s: %s' % (topic, message))
                            await client.publish(topic, message)
                    except asyncio.CancelledError:
                        self.healthcheck_status()
                        event = Status({'connected': False, 'datetime': arrow.now().isoformat()})
                        topic = f'{topic_prefix}/{event.response_key}'
                        message = event.to_json()
                        logger.debug('Sent mqtt message to %s: %s' % (topic, message))
                        await client.publish(topic, message)
            except aiomqtt.MqttError:
                logger.warning('Writer reconnecting to mqtt broker in 5 seconds...')
                await asyncio.sleep(5)

    async def connect(self) -> None:
        ''' Connect to mqtt/serial device and handle startup/reconnecting '''
        if self.connected:
            return True

        while not self.disconnecting:
            try:
                self.reader, self.writer = await serial_asyncio.open_serial_connection(**self.serial_config())
                logger.info('Connected to emu2 device')
                self.connected = True
                await asyncio.sleep(2)
                self.send_status()
                return True
            except SerialException as e:
                logger.warning('Reconnecting to emu2 device in 5 seconds...')
                await asyncio.sleep(5)

    async def disconnect(self, signame: str, loop: asyncio.BaseEventLoop) -> None:
        ''' Disconnect from mqtt/serial device and handle clean up '''
        self.disconnecting = True
        logger.info(f'Got {signame} request to disconnect')
        await asyncio.sleep(1)
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        logger.debug(f'Cancelling {len(tasks)} tasks')
        [task.cancel() for task in tasks]
        await asyncio.gather(*tasks)
        loop.stop()

    async def serial_reader(self) -> None:
        ''' Handle reading data from the serial device '''
        if not self.connected:
            await self.connect()

        buffer = ''
        while not self.disconnecting:
            try:
                line = await self.reader.readline()
            except SerialException:
                self.connected = False
                self.send_status()
                await self.connect()
                continue
            except asyncio.CancelledError:
                self.connected = False
                self.send_status()
                continue

            # @TODO: handle instances where line is not encoded
            line = line.decode('utf-8').strip()
            buffer += line
            if line.startswith('</'):
                logger.debug('Got response from emu2: %s' % buffer)
                try:
                    response = ResponseFactory(xmltodict.parse(buffer), emu=self)
                    setattr(self, response.response_key, response)
                    self.mqtt_queue.put_nowait(response)
                    buffer = ''
                except Exception as e:
                    logger.warning('Unrecognized response from emu2: %s' % e)
                    buffer = ''

        if self.disconnecting:
            self.connected = False

    async def serial_writer(self) -> None:
        ''' Handle writing data to the serial device '''
        lock = asyncio.Lock()
        while not self.disconnecting:
            try:
                if self.connected:
                    command = await self.serial_queue.get()
                    async with lock:
                        logger.debug('Sending command to emu2: %s' % command)
                        self.writer.write(command.encode('utf-8'))
                        await self.writer.drain()
                        await asyncio.sleep(3)
                else:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                if self.writer:
                    self.writer.close()
                    await self.writer.wait_closed()

        if self.disconnecting and self.writer:
            self.writer.close()

    def healthcheck_status(self) -> None:
        ''' Add/remove file for the docker healthcheck '''
        exists = self.healthcheck_path.exists()
        if self.connected and not exists:
            with open(self.healthcheck_file, 'w') as f:
                f.write(arrow.now().isoformat())
        if not self.connected and exists:
            self.healthcheck_path.unlink()

    def send_status(self) -> None:
        ''' Send if we are actively connected to the serial device or not '''
        status = Status({'connected': self.connected, 'datetime': arrow.now().isoformat()})
        self.mqtt_queue.put_nowait(status)
        self.healthcheck_status()

    def send_command(self, command: str, params: dict=None) -> None:
        ''' Send a command to the serial device '''
        payload = {'Command': {'Name': command}}
        if params is not None:
            payload['Command'].update(params)
        formatted_command = '\n'.join(xmltodict.unparse(payload).split('\n')[1:])
        logger.debug('Queuing command to emu2: %s' % formatted_command)
        self.serial_queue.put_nowait(formatted_command)

    async def set_current_price(self, cents: str='0.0') -> None:
        ''' Set the price for energy on the emu-2 device '''
        if self.device_info:
            price, digits = Response.format_price(cents)
            params = {
                'MeterMacId': self.device_info.device_mac_id,
                'Price': price,
                'TrailingDigits': digits,
            }
            self.send_command('set_current_price', params)
            await asyncio.sleep(3)
            self.get_current_price()

    def close_current_period(self) -> None:
        ''' Mark that the current period is now ended '''
        if self.device_info:
            params = {'MeterMacId': self.device_info.device_mac_id}
            self.send_command('close_current_period', params)
            self.get_current_period_usage()
            self.get_last_period_usage()

    def restart(self) -> None:
        ''' Restart the emu-2 device '''
        logger.warning('Restarting Emu unit...')
        self.send_command('restart')

    def get_device_info(self) -> None:
        ''' Request information about the emu-2 unit over serial '''
        self.send_command('get_device_info')

    def get_time(self) -> None:
        ''' Get the time from the emu-2 device '''
        self.send_command('get_time')

    def get_connection_status(self) -> None:
        ''' Get the connection status between the emu-2 device and the meter '''
        if self.device_info:
            params = {'MeterMacId': self.device_info.device_mac_id, 'Refresh': 'Y'}
            self.send_command('get_connection_status', params)

    def get_current_summation_delivered(self) -> None:
        ''' Get the total meter reading from the emu-2 device '''
        if self.device_info:
            params = {'MeterMacId': self.device_info.device_mac_id, 'Refresh': 'Y'}
            self.send_command('get_current_summation_delivered', params)

    def get_current_period_usage(self) -> None:
        ''' Get the current period usage from the emu-2 device '''
        if self.device_info:
            params = {'MeterMacId': self.device_info.device_mac_id}
            self.send_command('get_current_period_usage', params)

    def get_last_period_usage(self) -> None:
        ''' Get the previous period usage from the emu-2 device '''
        if self.device_info:
            params = {'MeterMacId': self.device_info.device_mac_id}
            self.send_command('get_last_period_usage', params)

    def get_current_price(self) -> None:
        ''' Get the current price from the emu-2 device '''
        if self.device_info:
            params = {'MeterMacId': self.device_info.device_mac_id}
            self.send_command('get_current_price', params)

    async def poll_command(self, command: Callable, frequency: int) -> None:
        ''' Schedule a command to be polled every frequency seconds '''
        # Offset commands by 5 seconds so we don't flood the emu
        self.poll_offset += 5
        await asyncio.sleep(self.poll_offset)
        logger.info(f'Polling {command.__name__} event {frequency} seconds')
        while not self.disconnecting:
            if not self.connected:
                await asyncio.sleep(5)
                continue
            command()
            await asyncio.sleep(frequency)

    async def reinitialize(self) -> None:
        ''' Restart some of the common messages when home assistant starts '''
        logger.info('Home assistant started, requesting new info and sending discovery')
        tasks = [
            'get_device_info',
            'get_connection_status',
            'get_time',
            'get_current_price',
            'get_current_summation_delivered',
            'get_last_period_usage'
        ]
        self.get_device_info()
        await asyncio.sleep(10)
        await self.send_discovery()
        await asyncio.sleep(5)
        for task in tasks:
            command = getattr(self, task)
            command()
            await asyncio.sleep(10)

    async def tasks(self) -> None:
        ''' Schedule all the tasks to run and handle events to disconnect '''
        loop = asyncio.get_running_loop()
        signals = ('SIGTERM', 'SIGINT')
        for signame in signals:
            sig = getattr(signal, signame)
            loop.add_signal_handler(sig, lambda signame=signame: asyncio.create_task(self.disconnect(signame, loop)))

        mqtt_reader_task = asyncio.create_task(self.mqtt_reader())
        mqtt_writer_task = asyncio.create_task(self.mqtt_writer())
        serial_reader_task = asyncio.create_task(self.serial_reader())
        serial_writer_task = asyncio.create_task(self.serial_writer())

        device_task = asyncio.create_task(self.poll_command(self.get_device_info, 300))
        entities_task = asyncio.create_task(self.queue_discovery())
        connection_task = asyncio.create_task(self.poll_command(self.get_connection_status, 60))
        time_task = asyncio.create_task(self.poll_command(self.get_time, 3600))
        price_task = asyncio.create_task(self.poll_command(self.get_current_price, 1800))
        summation_task = asyncio.create_task(self.poll_command(self.get_current_summation_delivered, 60))
        current_period_task = asyncio.create_task(self.poll_command(self.get_current_period_usage, 60))
        last_period_task = asyncio.create_task(self.poll_command(self.get_last_period_usage, 10800))

        await mqtt_reader_task
        await mqtt_writer_task
        await serial_reader_task
        await serial_writer_task

        self.get_device_info()
        await asyncio.sleep(2)
        await device_task
        await time_task
        await entities_task
        await connection_task
        await price_task
        await summation_task
        await current_period_task
        await last_period_task