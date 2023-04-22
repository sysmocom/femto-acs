#!/usr/bin/env python3
# Author: Alexander Couzens <lynxis@fe80.eu>
# (C) 2021 by sysmocom - s.f.m.c. GmbH <info@sysmocom.de>

XML_NS = {
        'soap-env': 'http://schemas.xmlsoap.org/soap/envelope/',
        'cwmp': 'urn:dslforum-org:cwmp-1-0'
        }

def get_cwmp_method(root):
    """ retrieve the cwmp method from the xml root Node """
    body = root.find('soap-env:Body', XML_NS)
    if body is None:
        return None

    for child in body:
        if child.tag == '{' + XML_NS['soap-env'] + '}Fault':
            return ('Fault', child)
        if child.tag == '{urn:dslforum-org:cwmp-1-0}Inform':
            return ('Inform', child)
        if child.tag == '{urn:dslforum-org:cwmp-1-0}SetParameterValuesResponse':
            return ('SetParameterValuesResponse', child)
    return None

def get_cwmp_id(root):
    """ retrieve the cwmp id """
    header = root.find('soap-env:Header', XML_NS)
    if header is None:
        return None

    cwmpid = header.find('{urn:dslforum-org:cwmp-1-0}ID', XML_NS)
    if cwmpid is not None:
        return cwmpid.text
    return None

def get_cwmp_inform_events(inform):
    """ return a list of Inform Events """
    eventnode = inform.find('Event')
    if eventnode is None:
        return None

    events = []
    """ parse
			<Event soap-enc:arrayType="cwmp:EventStruct[2]"
				<EventStruct>
					<EventCode>4 VALUE CHANGE</EventCode>
					<CommandKey></CommandKey>
				</EventStruct>
				<EventStruct>
					<EventCode>0 BOOTSTRAP</EventCode>
					<CommandKey></CommandKey>
				</EventStruct>
			</Event>
    """
    for ev in eventnode:
        if ev.tag != "EventStruct":
            continue

        evcodenode = ev.find('EventCode')
        events.append(evcodenode.text)
    return events

def get_cwmp_inform_serial(inform):
    """ retrieve the serial from an inform node """
    device_id = inform.find('DeviceId')
    if device_id is None:
        return None

    serial = device_id.find('SerialNumber')
    if serial is None:
        return None
    return serial.text

def get_cwmp_setresponse_status(setparametervaluesresponse):
    """ retrieve the status from a setparametervaluesresponse node """
    statusnode = setparametervaluesresponse.find('Status')
    if statusnode is None:
        return None
    return statusnode.text
