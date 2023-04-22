#!/usr/bin/env python3
# Author: Alexander Couzens <lynxis@fe80.eu>
# (C) 2021 by sysmocom - s.f.m.c. GmbH <info@sysmocom.de>

import configparser
import logging
from xml.etree.ElementTree import fromstring, tostring

from flask import Flask, make_response, render_template, request, session
from flask_caching import Cache
from flask_kvsession import KVSessionExtension
from simplekv.fs import FilesystemStore

from xmlutils import *

LOG = logging.getLogger("acs_emu")
STORE = FilesystemStore('./data')

app = Flask("acs_emu")
KVSessionExtension(STORE, app)

app.config.from_pyfile('./config/flask.py')
cache = Cache()
cache.init_app(app=app, config={"CACHE_TYPE": 'FileSystemCache', "CACHE_DIR": "./cache"})
cache.clear()

def send_configuration(serial, push):
    """ write to the 'database' if this serial needs a configuration """
    cache.set(serial, push)

def need_configuration(serial):
    """ does this device needs a new configuration? """
    need = cache.get(serial)
    if need is None:
        cache.set(serial, True)
        return True
    return need

def generate_config(params=None, serial=None, config_file='./config/femtocells.ini'):
    """ return a params dict for setparams from the config file """
    if params is None:
        params = {}

    config = configparser.ConfigParser()
    config.optionxform=str
    config.read(config_file)

    def read_config_to_params(section):
        for key in config[section]:
            try:
                val, xmltype = config[section][key].split('|')
                params[key] = {'value': val, 'xmltype': xmltype}
            except:
                LOG.error("Failed to parse %s key %s with value %s", section, key, config[section][key])

    read_config_to_params('Common')

    if serial and serial in config:
        read_config_to_params(serial)
    return params

@app.route('/', methods=['GET', 'POST'])
def root():
    return 'This is a femto-acs/tr069 server'

def fault(tree, node):
    """ handle a Fault """
    LOG.error("Fault: %s", tostring(node).decode('utf-8'))
    return "Fault"

def inform(tree, node):
    """ handle a device Inform request """
    cwmpid = get_cwmp_id(tree)
    serial = get_cwmp_inform_serial(node)
    events = get_cwmp_inform_events(node)

    session['serial'] = serial
    if '0 BOOTSTRAP' in events or '1 BOOT' in events:
        send_configuration(serial, True)
        LOG.error("Device %s booted", serial)

    LOG.error("Device %s informed us. cwmpipd %s. Events %s", serial, cwmpid, ", ".join(events))
    response = make_response(render_template('inform.jinja.xml', cwmpid=cwmpid))
    response.headers['Content-Type'] = 'text/xml; charset="utf-8"'
    response.headers['SOAPServer'] = 'femto-acs/1.1.1'
    response.headers['Server'] = 'femto-acs/1.1.1'
    return response

def send_setparams():
    """ request a setparams """
    # e.g. params are {name: "arfcn", xmltype: "xsd:int", value: "23"}
    serial = session['serial']

    params = {}
    params = generate_config(params, serial)

    # keep track if we already sent out a response
    LOG.error("Device %s sending configuration", serial)
    send_configuration(serial, True)
    response = make_response(render_template('setparams.jinja.xml',
                                             cwmpid=23, params=params, length_params=len(params)))
    response.headers['Content-Type'] = 'text/xml'
    return response

def setparams_response(tree, node):
    """ handle the setparams response """
    serial = session['serial']
    status = get_cwmp_setresponse_status(node)
    if status is not None:
        if status == '0':
            LOG.error("Device %s applied configuration changes without reboot", serial)
        elif status == '1':
            LOG.error("Device %s applied configuration changes but require a reboot", serial)
        else:
            LOG.error("Device %s returned unknown status value (%s)", serial)
    send_configuration(serial, False)
    response = make_response()
    response.headers['Content-Type'] = 'text/xml'
    return response

@app.route('/acs', methods=['GET', 'POST'])
def acs():
    """ main tr069/acs entry point """
    if request.method == 'GET':
        return 'This is a femoto-acs/tr069 server'

    if request.method != 'POST':
        return 'There is nothing to show'

    # POST requests
    if request.content_type != 'text/xml':
        return 'Wrong content type'

    # when the client doesn't send us any data, it's ready for our request
    if not request.content_length:
        if 'serial' not in session:
            LOG.error("Received an empty request from an unknown device. Can not generate configuration!")
            return make_response()
        if need_configuration(session['serial']):
            return send_setparams()

        LOG.error("Device %s already configured", session['serial'])
        return make_response()

    # some request content data
    try:
        tree = fromstring(request.data)
    except:
        return 'Could not parse the request as XML'

    method = get_cwmp_method(tree)
    if not method:
        return 'Failed to get the cwmp method'

    method, node = method

    if method == "Fault":
        return fault(tree, node)

    if method == "Inform":
        return inform(tree, node)

    if method == "SetParameterValuesResponse":
        return setparams_response(tree, node)

    return 'This is a femto-acs/tr069 server'

if __name__ == '__main__':
    app.run()
