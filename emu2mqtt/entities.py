from responses import DeviceInfo

def generate_entities(topic_prefix: str, device_info: DeviceInfo):
    ''' Generate the entity discovery objects to send to home assistant '''

    # The unique identifier
    mac = device_info.device_mac_id

    # The shared device object to link all the entities together
    device = {
        'identifiers': [mac],
        'name': 'EMU2',
        'manufacturer': device_info.manufacturer,
        'model': device_info.model_id,
        'hw_version': device_info.hwversion,
        'sw_version': device_info.fwversion,
    }

    # Track whether the serial reader is connected to the emu-2 device
    serial_connected = {
        'payload_available': True,
        'payload_not_available': False,
        'topic': f'{topic_prefix}/status',
        'value_template': '{{ value_json.connected }}',
    }

    # Track if the emu-2 device is connected to the meter
    meter_connected = {
        'payload_available': 'Connected',
        'payload_not_available': 'Disconnected',
        'topic': f'{topic_prefix}/connection_status',
        'value_template': '{% if value_json.status == "Connected" %}{{ value_json.status }}{% else %}Disconnected{% endif %}',
    }

    serial_availability = [serial_connected]
    all_availability = [serial_connected, meter_connected]

    # Note that the type attribute is not sent to home assistant but is used to
    # specify the mqtt topic for entity discovery
    return [
        {
            'type': 'binary_sensor',
            'name': 'Status',
            'device_class': 'connectivity',
            'json_attributes_topic': f'{topic_prefix}/status',
            'state_topic': f'{topic_prefix}/status',
            'value_template': '{{ value_json.connected }}',
            'payload_on': True,
            'payload_off': False,
            'entity_category': 'diagnostic',
            'unique_id': f'{mac}_status',
            'device': device,
        },
        {
            'type': 'sensor',
            'name': 'Meter Connection Strength',
            'unit_of_measurement': '%',
            'icon': 'mdi:signal',
            'json_attributes_topic': f'{topic_prefix}/connection_status',
            'state_topic': f'{topic_prefix}/connection_status',
            'value_template': '{{ value_json.link_strength }}',
            'entity_category': 'diagnostic',
            'unique_id': f'{mac}_meter_connection_strength',
            'availability': serial_availability,
            'device': device,
        },
        {
            'type': 'binary_sensor',
            'name': 'Meter Status',
            'device_class': 'connectivity',
            'json_attributes_topic': f'{topic_prefix}/connection_status',
            'state_topic': f'{topic_prefix}/connection_status',
            'value_template': '{% if value_json.status == "Connected" %}{{ value_json.status }}{% else %}Disconnected{% endif %}',
            'payload_on': 'Connected',
            'payload_off': 'Disconnected',
            'entity_category': 'diagnostic',
            'unique_id': f'{mac}_meter_status',
            'availability': serial_availability,
            'device': device,
        },
        {
            'type': 'sensor',
            'name': 'Power',
            'device_class': 'power',
            'state_class': 'measurement',
            'unit_of_measurement': 'W',
            'state_topic': f'{topic_prefix}/instantaneous_demand',
            'value_template': '{{ value_json.demand }}',
            'unique_id': f'{mac}_power',
            'device': device,
        },
        {
            'type': 'sensor',
            'name': 'Total Delivered',
            'device_class': 'energy',
            'state_class': 'total_increasing',
            'unit_of_measurement': 'kWh',
            'json_attributes_topic': f'{topic_prefix}/current_summation_delivered',
            'state_topic': f'{topic_prefix}/current_summation_delivered',
            'value_template': '{{ value_json.summation_delivered }}',
            'unique_id': f'{mac}_energy_delivered',
            'device': device,
        },
        {
            'type': 'sensor',
            'name': 'Total Received',
            'device_class': 'energy',
            'state_class': 'total_increasing',
            'unit_of_measurement': 'kWh',
            'json_attributes_topic': f'{topic_prefix}/current_summation_delivered',
            'state_topic': f'{topic_prefix}/current_summation_delivered',
            'value_template': '{{ value_json.summation_received }}',
            'unique_id': f'{mac}_energy_received',
            'device': device,
        },
        {
            'type': 'sensor',
            'name': 'Current Period Usage',
            'device_class': 'energy',
            'state_class': 'total',
            'unit_of_measurement': 'kWh',
            'json_attributes_topic': f'{topic_prefix}/current_period_usage',
            'state_topic': f'{topic_prefix}/current_period_usage',
            'value_template': '{{ value_json.current_usage }}',
            'unique_id': f'{mac}_current_usage',
            'device': device,
        },
        {
            'type': 'sensor',
            'name': 'Current Period Start',
            'device_class': 'timestamp',
            'state_topic': f'{topic_prefix}/current_period_usage',
            'value_template': '{{ as_local(as_datetime(value_json.start_date)) }}',
            'entity_category': 'diagnostic',
            'unique_id': f'{mac}_current_start',
            'device': device,
        },
        {
            'type': 'button',
            'name': 'Restart',
            'device_class': 'restart',
            'command_topic': f'{topic_prefix}/restart',
            'availability_mode': 'all',
            'availability': all_availability,
            'payload_press': 'restart',
            'entity_category': 'config',
            'unique_id': f'{mac}_restart',
            'device': device,
        },
        {
            'type': 'button',
            'name': 'Close Current Period',
            'command_topic': f'{topic_prefix}/close_current_period',
            'availability_mode': 'all',
            'availability': all_availability,
            'payload_press': 'close_current_period',
            'entity_category': 'config',
            'unique_id': f'{mac}_close_current_period',
            'device': device,
        },
        {
            'type': 'number',
            'name': 'Current Price',
            'mode': 'box',
            'min': '0',
            'step': '0.001',
            'device_class': 'monetary',
            'entity_category': 'config',
            'unit_of_measurement': '¢',
            'command_topic': f'{topic_prefix}/set_current_price',
            'json_attributes_topic': f'{topic_prefix}/price_cluster',
            'state_topic': f'{topic_prefix}/price_cluster',
            'value_template': '{{ value_json.price }}',
            'availability_mode': 'all',
            'availability': all_availability,
            'unique_id': f'{mac}_current_price',
            'device': device,
        },
        {
            'type': 'sensor',
            'name': 'Energy Price',
            'device_class': 'monetary',
            'unit_of_measurement': 'USD/kWh',
            'json_attributes_topic': f'{topic_prefix}/price_cluster',
            'state_topic': f'{topic_prefix}/price_cluster',
            'value_template': '{{ value_json.price|float / 100 }}',
            'unique_id': f'{mac}_energy_price',
            'device': device,
        },
    ]