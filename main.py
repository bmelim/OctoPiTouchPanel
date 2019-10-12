#!/usr/bin/python

# kivy imports
from kivy.app import App
from kivy.uix.tabbedpanel import TabbedPanel
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.lang import Builder
from kivy.config import Config
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import get_color_from_hex as rgb
from kivy.garden.graph import Graph, MeshLinePlot, SmoothLinePlot

# other imports
import time
import os
from math import sin, cos
import requests
import json
import configparser
import sys
from subprocess import *
import pprint
from collections import deque  # Fast pops from the ends of lists

# Temperature lists
hotendactual_list = deque([])
hotendtarget_list = deque([])
bedactual_list = deque([])
bedtarget_list = deque([])

# Initialize Temperature lists
for i in range(360):
    hotendactual_list.append(0)
    hotendtarget_list.append(0)
    bedactual_list.append(0)
    bedtarget_list.append(0)
# Fill timestamp list with 1000x time vals in seconds
graphtime_list = []
for i in range(360):  # Fill the list with zeros
    graphtime_list.append(0)

graphtime_list[0] = 30000
for i in range(359):  # Replace values with decreasing seconds from 30 to 0
    val = int(graphtime_list[i] - 83)
    graphtime_list[i + 1] = (val)


# Read settings from the config file
settings = configparser.ConfigParser()
settings.read('octoprint.cfg')
host = settings.get('APISettings', 'host')
nicname = settings.get('APISettings', 'nicname')
apikey = settings.get('APISettings', 'apikey')
debug = int(settings.get('Debug', 'debug_enabled'))
hotend_max = int(settings.get('MaxTemps', 'hotend_max'))
bed_max = int(settings.get('MaxTemps', 'bed_max'))
invert_X = int(settings.get('AxisInvert', 'invert_X'))
invert_Y = int(settings.get('AxisInvert', 'invert_Y'))
invert_Z = int(settings.get('AxisInvert', 'invert_Z'))

# Define Octoprint constants
httptimeout = 3   # http request timeout in seconds
printerapiurl = 'http://' + host + '/api/printer'
printheadurl = 'http://' + host + '/api/printer/printhead'
bedurl = 'http://' + host + '/api/printer/bed'
toolurl = 'http://' + host + '/api/printer/tool'
jobapiurl = 'http://' + host + '/api/job'
connectionurl = 'http://' + host + '/api/connection'
commandurl = 'http://' + host + '/api/printer/command'
headers = {'X-Api-Key': apikey, 'content-type': 'application/json'}

if debug:
    print("*********** DEBUG ENABLED ************")
    print(headers)

bed_temp_val = 0.0
hotend_temp_val = 0.0
jogincrement = 10

platform = sys.platform  # Grab platform name for platform specific commands

start_time = time.time()


# Kivy widget layout
Builder.load_string("""
#:import rgb kivy.utils.get_color_from_hex
<Panels>:
    size_hint: 1, 1
    pos_hint: {'center_x': .5, 'center_y': .5}
    do_default_tab: False
    tab_height: '60dp'
    my_graph: my_graph
    ##############
    # Tab1
    ##############
    TabbedPanelItem:
        id: tab1
        text: 'Status'
        font_size: '20sp'
        BoxLayout:
            orientation: 'horizontal'
            ######################
            # Left Stats Area
            ######################
            BoxLayout:
                size_hint: (.4, 1)
                orientation: 'vertical'
                padding: 10
                Image:
                    source: 'img/logo.png'
                    size_hint_y: None
                    height: 100
                GridLayout:
                    cols: 2
                    Label:
                        text: 'IP Address:'
                    Label:
                        id: ipaddr
                        size_hint_x: 1.75
                        text: 'N/A'
                    Label:
                        text: 'Machine State:'
                    Label:
                        id: printerstate
                        text: 'Unknown'
                    Label:
                        text: 'File:'
                    Label:
                        id: jobfilename
                        text: ' '
                    Label:
                        text: 'Time Elapsed:'
                    Label:
                        id: jobprinttime
                        text: '00:00:00'
                    Label:
                        text: 'Est. Time Left:'
                    Label:
                        id: jobprinttimeleft
                        text: '00:00:00'
                    Label:
                        text: 'Printed: '
                    Label:
                        id: jobpercent
                        text: '---%'
                ProgressBar:
                    id: progressbar
                    size_hint_x: .97
                    size_hint_y: None
                    height: '15dp'
                    value: 0
            ######################
            # Right Stats Area
            ######################
            BoxLayout:
                size_hint: (.6, 1)
                orientation: 'vertical'
                GridLayout:
                    cols: 3
                    size_hint: (1, .3)
                    Label:
                        text: ' '
                        size_hint_y: None
                        height: 20
                    Label:
                        text_size: self.size
                        halign: 'center'
                        valign: 'middle'
                        text: 'Actual'
                    Label:
                        text_size: self.size
                        halign: 'center'
                        valign: 'middle'
                        text: 'Target'
                    Label:
                        size_hint_y: None
                        height: 40
                        text_size: self.size
                        bold: True
                        halign: 'right'
                        valign: 'middle'
                        text: 'Hot End:'
                    Label:
                        id: hotend_actual
                        text_size: self.size
                        font_size: 30
                        bold: True
                        halign: 'center'
                        valign: 'middle'
                        text: 'N/A' + u"\u00b0" + ' C'
                    Label:
                        id: hotend_target
                        text_size: self.size
                        font_size: 30
                        bold: True
                        halign: 'center'
                        valign: 'middle'
                        text: 'N/A' + u"\u00b0" + ' C'
                    Label:
                        size_hint_y: None
                        height: 40
                        bold: True
                        text_size: self.size
                        halign: 'right'
                        valign: 'middle'
                        text: 'Bed:'
                    Label:
                        id: bed_actual
                        text_size: self.size
                        font_size: 30
                        bold: True
                        halign: 'center'
                        valign: 'middle'
                        text: 'N/A' + u"\u00b0" + ' C'
                    Label:
                        id: bed_target
                        text_size: self.size
                        font_size: 30
                        bold: True
                        halign: 'center'
                        valign: 'middle'
                        text: 'N/A' + u"\u00b0" + ' C'
                Graph:
                    id:my_graph
                    xlabel: 'Time'
                    ylabel: 'Temp'
                    x_ticks_minor: 5
                    x_ticks_major: 5
                    y_ticks_major: 50
                    y_grid_label: True
                    x_grid_label: True
                    padding: 5
                    xlog: False
                    ylog: False
                    x_grid: True
                    y_grid: True
                    xmin: -30
                    xmax: 0
                    ymin: 0
                    ymax: 300
                    label_options: { 'color': rgb('444444'), 'bold': True}
                    background_color: rgb('f8f8f2')  # back ground color of canvas
                    tick_color: rgb('808080')  # ticks and grid
                    border_color: rgb('808080')  # border drawn around each graph
    ##############
    # Tab2
    ##############
    TabbedPanelItem:
        text: 'Control'
        font_size: '20sp'
        FloatLayout:
            #X/Y Axis buttons
            Label:
                text: 'X/Y'
                font_size: '35sp'
                pos: -265, 95
            Button:
                text: '^'
                id: jogforward
                disabled: False
                on_press: root.jogaxis('y', 'forward')
                pos: 100, 200
                size_hint: .10, .15
            Button:
                text: '<'
                id:jogleft
                disabled: False
                on_press: root.jogaxis('x', 'left')
                pos: 10, 130
                size_hint: .10, .15
            Button:
                text: 'H'
                id: homexy
                disabled: False
                on_press: root.home('xy')
                pos: 100, 130
                size_hint: .10, .15
            Button:
                text: '>'
                id: jogright
                disabled: False
                on_press: root.jogaxis('x', 'right')
                pos: 190, 130
                size_hint: .10, .15
            Button:
                text: 'v'
                id: jogbackward
                disabled: False
                on_press: root.jogaxis('y', 'backward')
                pos: 100, 60
                size_hint: .10, .15
            #Z axis buttons
            Label:
                text: 'Z'
                font_size: '35sp'
                pos: -65, 95
            Button:
                size_hint_x: None
                width: '25dp'
                id: jogzup
                disabled: False
                text: '^'
                on_press: root.jogaxis('z', 'up')
                pos: 300, 200
                size_hint: .10, .15
            Button:
                text: 'H'
                id: homez
                disabled: False
                on_press: root.home('z')
                pos: 300, 130
                size_hint: .10, .15
            Button:
                text: 'v'
                id: jogzdown
                disabled: False
                on_press: root.jogaxis('z', 'down')
                pos: 300, 60
                size_hint: .10, .15
            #Connect Button
            Label:
                id: printerstate2
                text: 'Unknown'
                #pos: 310, 195
                pos: 335, 195
            Button:
                text: 'Connect'
                id: connect
                on_press: root.connect()
                pos: 675, 345
                size_hint: .15, .10
            Button:
                text: 'Disconnect'
                id: connect
                on_press: root.disconnect()
                pos: 675, 295
                size_hint: .15, .10
            #####################
            # Jog increments
            #####################
            ToggleButton:
                text: '0.1'
                id: joginc01
                on_press: root.jogincrement(0.1)
                group: 'jogincrement'
                state: 'normal'
                pos: 10, 0
                size_hint: .1, .09
            ToggleButton:
                text: '1'
                id: joginc1
                on_press: root.jogincrement(1)
                group: 'jogincrement'
                state: 'normal'
                pos: 105, 0
                size_hint: .1, .09
            ToggleButton:
                text: '10'
                id: joginc10
                on_press: root.jogincrement(10)
                group: 'jogincrement'
                state: 'down'
                pos: 200, 0
                size_hint: .1, .09
            ToggleButton:
                text: '100'
                id: joginc100
                on_press: root.jogincrement(100)
                group: 'jogincrement'
                state: 'normal'
                pos: 300, 0
                size_hint: .1, .09
            ######################
            # Extrude/Retract
            ######################
            Spinner:
                id: extrudeamount
                text: '5'
                values: '1', '5', '10', '20', '100'
                pos: 450, 0
                size_hint: .15, .09
            Label:
                text: 'mm'
                pos: 138, -189
            Button:
                text: 'Extrude'
                id: extrude
                disabled: False
                on_press: root.extrudefilament(1)
                pos: 450, 60
                size_hint: .15, .15
            Button:
                text: 'Retract'
                id: retract
                disabled: False
                on_press: root.extrudefilament(-1)
                pos: 450, 130
                size_hint: .15, .15
            ######################
            # Fan Controls
            ######################
            Slider:
                id: fanslider
                max: 100
                value: int(100)
                orientation: 'vertical'
                on_value: fanslider.value = int(self.value)
                size_hint: .15, .42
                pos: 620, 0
            Button:
                size_hint_x: None
                width: '25dp'
                id: fanpercent
                disabled: False
                text: 'FAN ' + str(int(fanslider.value)) + '%'
                on_press: root.fanspeed(fanslider.value)
                pos: 700, 100
                size_hint: .10, .15
            Button:
                text: 'FAN OFF'
                id: fanoff
                disabled: False
                on_press: root.fanspeed(0)
                pos: 700, 12
                size_hint: .10, .15

    ###############################
    # Tab3 - Temperature Controls
    ###############################
    TabbedPanelItem:
        text: 'Temps'
        font_size: '20sp'
        FloatLayout:
            #################
            #Bed temp slider
            #################
            Slider:
                id: bedslider
                max: 100
                value: int(0)
                on_value: bedslider.value = int(self.value)
                size_hint: .80, .15
                pos: 160, 295
            ProgressBar:
                id: bedpb
                size_hint: .76, .15
                pos: 176, 265
                value: 0
            Label:
                text: 'Selected Bed Target: ' + str(bedslider.value) + u"\u00b0" + ' C'
                font_size: '20sp'
                halign: 'left'
                pos: 50, 150
            Button:
                id: setbedtarget
                text: 'Set Bed Target'
                on_press: root.setbedtarget(bedslider.value)
                size_hint: .18, .12
                pos: 10, 325
            Button:
                id: setbedoff
                text: 'Turn Off Bed'
                on_press: root.setbedtarget(0)
                size_hint: .18, .12
                pos: 10, 270
            Label:
                id: tab3_bed_actual
                text: 'Bed Actual: ' + bed_actual.text
                font_size: '16sp'
                pos: -60, 75
            Label:
                id: tab3_bed_target
                text: 'Bed Target: ' + bed_target.text
                font_size: '16sp'
                pos: 200, 75

            ####################
            #Hot end temp slider
            ####################
            Slider:
                id: hotendslider
                max: 300
                value: int(0)
                on_value: hotendslider.value = int(self.value)
                size_hint: .80, .15
                pos: 160, 120
            ProgressBar:
                id: hotendpb
                size_hint: .76, .15
                pos: 176, 90
                value: 0
            Label:
                text: 'Selected Hot End Target: ' + str(hotendslider.value) + u"\u00b0" + ' C'
                font_size: '20sp'
                halign: 'left'
                pos: 50, -15
            Button:
                id: sendhotendtarget
                text: 'Set Hot End Target'
                on_press: root.sethotendtarget(hotendslider.value)
                size_hint: .18, .12
                pos: 10, 150
            Button:
                id: sethotendoff
                text: 'Turn Off Hot End'
                on_press: root.sethotendtarget(0)
                size_hint: .18, .12
                pos: 10, 95
            Label:
                id: tab3_hotend_actual
                text: 'Hot End Actual: ' + hotend_actual.text
                font_size: '16sp'
                pos: -60, -100
            Label:
                id: tab3_hotend_target
                text: 'Hot End Target: ' + hotend_target.text
                font_size: '16sp'
                pos: 200, -100

    #######################
    # Tab4 - Job Controls
    #######################
    TabbedPanelItem:
        text: 'Job'
        font_size: '20sp'
        FloatLayout:
            GridLayout:
                cols: 2
                pos: 0, 320
                size_hint: .75, .2
                Label:
                    text: 'Loaded File:  '
                    text_size: self.size
                    size_hint: .2, 1
                    halign: 'right'
                    valign: 'middle'
                Label:
                    id: jobfilenamefull
                    text: 'N/A'
                    text_size: self.size
                    halign: 'left'
                    valign: 'middle'
                Label:
                    text: 'Status:  '
                    text_size: self.size
                    size_hint: .2, 1
                    halign: 'right'
                    valign: 'middle'
                Label:
                    id: printerstate3
                    text: 'Unknown'
                    text_size: self.size
                    halign: 'left'
                    valign: 'middle'

            Button:
                id: printbutton
                text: 'Print'
                disabled: False
                on_press: root.jobcontrol('start')
                size_hint: .18, .18
                pos: 20, 220
            Button:
                id: pausebutton
                text: 'Pause'
                disabled: False
                on_press: root.jobcontrol('pause')
                size_hint: .18, .18
                pos: 20, 120
            Button:
                id: cancelbutton
                text: 'Cancel'
                disabled: False
                on_press: root.jobcontrol('cancel')
                size_hint: .18, .18
                pos: 20, 20


    #######################
    # Tab5 - OS Utils
    #######################
    TabbedPanelItem:
        text: 'OS Utils'
        font_size: '20sp'
        FloatLayout:
            Button:
                id: restartOS
                text: 'Reboot'
                on_press: root.restartOS('reboot')
                size_hint: .18, .12
                pos: 10, 95
            Button:
                id: shutdownOS
                text: 'Shutdown'
                on_press: root.restartOS('shutdown')
                size_hint: .18, .12
                pos: 10, 30
            Button:
                id: exitApp
                text: 'Exit'
                on_press: root.exitapp()
                size_hint: .18, .12
                pos: 10, 195
            Button:
                id: restartNetworking
                text: 'Restart Networking'
                on_press: root.restartnetworking()
                size_hint: .18, .12
                pos: 210, 195




""")  # End of kv syntax


class Panels(TabbedPanel):
    global bed_max
    global hotend_max

    def gettemps(self, *args):
        self.ids.hotendslider.max = hotend_max
        self.ids.bedslider.max = bed_max
        try:
            if debug:
                print('[GET TEMPS] Trying /printer API request to Octoprint...')
            r = requests.get(printerapiurl, headers=headers, timeout=httptimeout)
            if debug:
                print('[GET TEMPS] STATUS CODE: ', str(r.status_code))
        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print('[GET TEMPS] ERROR: Couldn\'t contact Octoprint /printer API')
                print(e)
        if r and r.status_code == 200:
            if debug:
                print('[GET TEMPS] JSON Data: ' + str(r.json()))
        if r and r.status_code == 200 and 'tool0' in r.json()['temperature']:
            printeronline = True
            hotendactual = r.json()['temperature']['tool0']['actual']
            hotendtarget = r.json()['temperature']['tool0']['target']
            bedactual = r.json()['temperature']['bed']['actual']
            bedtarget = r.json()['temperature']['bed']['target']
            printing = r.json()['state']['flags']['printing']
            paused = r.json()['state']['flags']['paused']
            operational = r.json()['state']['flags']['operational']

            if debug:
                print('   BED ACTUAL: ' + str(bedactual))
                print('HOTEND ACTUAL: ' + str(hotendactual))
                print('     PRINTING: ' + str(printing))
                print('       PAUSED: ' + str(paused))
                print('  OPERATIONAL: ' + str(operational))

            # Update tempurature arrays with new data
            hotendactual_list.popleft()
            hotendactual_list.append(hotendactual)
            hotendtarget_list.popleft()
            hotendtarget_list.append(hotendtarget)
            bedactual_list.popleft()
            bedactual_list.append(bedactual)
            bedtarget_list.popleft()
            bedtarget_list.append(bedtarget)

            # Update text color on Temps tab if values are above 40C
            if bedactual > 40:
                self.ids.tab3_bed_actual.color = [1, 0, 0, 1]
            else:
                self.ids.tab3_bed_actual.color = [1, 1, 1, 1]

            if bedtarget > 40:
                self.ids.tab3_bed_target.color = [1, 0, 0, 1]
            else:
                self.ids.tab3_bed_target.color = [1, 1, 1, 1]

            if hotendactual > 40:
                self.ids.tab3_hotend_actual.color = [1, 0, 0, 1]
            else:
                self.ids.tab3_hotend_actual.color = [1, 1, 1, 1]

            if hotendtarget > 40:
                self.ids.tab3_hotend_target.color = [1, 0, 0, 1]
            else:
                self.ids.tab3_hotend_target.color = [1, 1, 1, 1]

            # Enable/Disable extruder buttons
            if hotendactual < 130 or printing or paused:
                self.ids.extrude.disabled = True
                self.ids.retract.disabled = True
            else:
                self.ids.extrude.disabled = False
                self.ids.retract.disabled = False

            # Set pause/resume label on pause button
            if paused:
                self.ids.pausebutton.text = 'Resume'
            else:
                self.ids.pausebutton.text = 'Pause'

            # Enable/Disable print job buttons
            if printing or paused:
                self.ids.printbutton.disabled = True
                self.ids.cancelbutton.disabled = False
                self.ids.pausebutton.disabled = False
            else:
                self.ids.printbutton.disabled = False
                self.ids.cancelbutton.disabled = True
                self.ids.pausebutton.disabled = True

            # Set position of slider pointer
            self.ids.hotendpb.value = (hotendactual / self.ids.hotendslider.max) * 100
            self.ids.bedpb.value = (bedactual / self.ids.bedslider.max) * 100

            # Update tempurature values with new data
            self.ids.bed_actual.text = str(bedactual) + u"\u00b0" + ' C'
            self.ids.hotend_actual.text = str(hotendactual) + u"\u00b0" + ' C'
            if bedtarget > 0:
                self.ids.bed_target.text = str(bedtarget) + u"\u00b0" + ' C'
            else:
                self.ids.bed_target.text = 'OFF'
            if hotendtarget > 0:
                self.ids.hotend_target.text = str(hotendtarget) + u"\u00b0" + ' C'
            else:
                self.ids.hotend_target.text = 'OFF'
        else:
            if r:
                print('Error. API Status Code: ', str(r.status_code))  # Print API status code if we have one
            # If we can't get any values from Octoprint just fill values with not available.
            self.ids.bed_actual.text = 'N/A'
            self.ids.hotend_actual.text = 'N/A'
            self.ids.bed_target.text = 'N/A'
            self.ids.hotend_target.text = 'N/A'

    def home(self, *args):
        axis = args[0]
        print('HOME AXIS: ' + axis)
        if axis == 'xy':
            homedata = {'command': 'home', 'axes': ['x', 'y']}
        else:
            homedata = {'command': 'home', 'axes': ['z']}
        try:
            if debug:
                print('[HOME ' + axis + '] Trying /API request to Octoprint...')
            r = requests.post(printheadurl, headers=headers, json=homedata, timeout=httptimeout)
            if debug:
                print('[HOME ' + axis + '] STATUS CODE: ' + str(r.status_code))
        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print('ERROR: Couldn\'t contact Octoprint /job API')
                print(e)

    def jogaxis(self, *args):
        axis = args[0]
        direction = args[1]
        global invert_X
        global invert_Y
        global invert_Z
        global jogincrement
        invert_axis = {'x': invert_X, 'y': invert_Y, 'z': invert_Z}

        print('AXIS: ' + axis)
        print('DIRECTION: ' + direction)
        print('INCREMENT: ' + str(jogincrement))

        if direction == 'up' or direction == 'forward' or direction == 'left':
            if invert_axis[axis]:
                inc = jogincrement * -1
            else:
                inc = jogincrement

        if direction == 'down' or direction == 'backward' or direction == 'right':
            if invert_axis[axis]:
                inc = jogincrement
            else:
                inc = jogincrement * -1

        jogdata = {'command': 'jog', axis: inc}
        print('JOGDATA: ' + str(jogdata))
        try:
            if debug:
                print('[JOG ' + axis + ' ' + direction + '] Trying /API request to Octoprint...')
            r = requests.post(printheadurl, headers=headers, json=jogdata, timeout=httptimeout)
            if debug:
                print('STATUS CODE: ' + str(r.status_code))
        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print('ERROR: Couldn\'t contact Octoprint /job API')
                print(e)

    def jogincrement(self, *args):
        global jogincrement
        if debug:
            print('[JOG INCREMENT] Button pressed')
            print('[JOG INCREMENT] INC: ' + str(args[0]))
        jogincrement = args[0]

    def connect(self, *args):
        connectiondata = {'command': 'connect', 'port': '/dev/ttyACM0', 'baudrate': 250000,
                          'save': False, 'autoconnect': False}
        try:
            if debug:
                print('[CONNECT] Trying /job API request to Octoprint...')
                print('[CONNECT] ' + connectionurl + str(connectiondata))
            r = requests.post(connectionurl, headers=headers, json=connectiondata, timeout=httptimeout)
            if debug:
                print('[CONNECT] STATUS CODE: ' + str(r.status_code))
                print('[CONNECT] RESPONSE: ' + r.text)
        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print('[CONNECT] ERROR: Couldn\'t contact Octoprint /job API')
                print(e)

    def disconnect(self, *args):
        disconnectdata = {'command': 'disconnect'}
        try:
            if debug:
                print('[DISCONNECT] Trying /job API request to Octoprint...')
                print('[DISCONNECT] ' + connectionurl + str(disconnectdata))
            r = requests.post(connectionurl, headers=headers, json=disconnectdata, timeout=httptimeout)
            if debug:
                print('[DISCONNECT] STATUS CODE: ' + str(r.status_code))
                print('[DISCONNECT] RESPONSE: ' + r.text)
        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print('[DISCONNECT] ERROR: Couldn\'t contact Octoprint /job API')
                print(e)

    def setbedtarget(self, *args):
        bedsliderval = args[0]
        bedtargetdata = {'command': 'target', 'target': bedsliderval}
        if debug:
            print('[BED TARGET] New Value: ' + str(bedsliderval) + ' C')
        try:
            if debug:
                print('[BED TARGET] Trying /API request to Octoprint...')
            r = requests.post(bedurl, headers=headers, json=bedtargetdata, timeout=httptimeout)
            if debug:
                print ('[BED TARGET] STATUS CODE: ' + str(r.status_code))
        except requests.exceptions.RequestException as e:
            print('[BED TARGET] ERROR: Couldn\'t contact Octoprint /job API')
            print(e)
            r = False

    def sethotendtarget(self, *args):
        hotendsliderval = args[0]
        hotendtargetdata = {'command': 'target', 'targets': {'tool0': hotendsliderval}}
        if debug:
            print('[HOTEND TARGET] New Value: ' + str(hotendsliderval) + ' C')
        try:
            if debug:
                print('[HOTEND TARGET] Trying /API request to Octoprint...')
            r = requests.post(toolurl, headers=headers, json=hotendtargetdata, timeout=httptimeout)
            if debug:
                print('[HOTEND TARGET] STATUS CODE: ' + str(r.status_code))
        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print('[HOTEND TARGET] ERROR: Couldn\'t contact Octoprint /job API')
                print(e)

    def extrudefilament(self, *args):
        posneg = args[0]
        extrudeamount = (int(self.ids.extrudeamount.text) * posneg)
        if debug:
            print('[EXTRUDE FILAMENT] Amount: ' + str(extrudeamount))
        extrudedata = {'command': 'extrude', 'amount': extrudeamount}
        if debug:
            print('[EXTRUDE FILAMENT] Extruding: ' + str(extrudeamount) + ' mm')
        try:
            if debug:
                print ('[EXTRUDE FILAMENT] Trying /API request to Octoprint...')
            r = requests.post(toolurl, headers=headers, json=extrudedata, timeout=httptimeout)
            if debug:
                print('[EXTRUDE FILAMENT] STATUS CODE: ' + str(r.status_code))
        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print('[EXTRUDE FILAMENT] ERROR: Couldn\'t contact Octoprint /job API')
                print(e)

    def fanspeed(self, *args):
        speed_percent = int(args[0])
        speed_pwm = int(speed_percent * 2.551)
        fan_gcode = 'M106 S' + str(speed_pwm)
        fancmd = {"commands": [fan_gcode]}
        if debug:
            print('[FAN CONTROL] Speed: ' + str(speed_pwm))
            print('[FAN CONTROL] ' + str(fancmd))
        try:
            r = requests.post(commandurl, headers=headers, json=fancmd, timeout=httptimeout)
        except requests.exceptions.RequestException as e:
            r = False

    def jobcontrol(self, *args):
        jobcommand = args[0]
        jobdata = {'command': jobcommand}
        try:
            if debug:
                print ('[JOB COMMAND] Trying /API request to Octoprint...')
            # Send job request to the job api
            r = requests.post(jobapiurl, headers=headers, json=jobdata, timeout=httptimeout)
            if debug:
                print ('[JOB COMMAND] STATUS CODE: ' + str(r.status_code))
                print ('[JOB COMMAND]     COMMAND: ' + str(jobcommand))
                print ('[JOB COMMAND] BUTTON TEXT: ' + self.ids.pausebutton.text)
            # Update pause button text
            if r.status_code == 204 and jobcommand == 'pause' and self.ids.pausebutton.text == 'Pause':
                self.ids.pausebutton.text = 'Resume'
            elif r.status_code == 204 and jobcommand == 'pause' and self.ids.pausebutton.text == 'Resume':
                self.ids.pausebutton.text = 'Pause'

        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print ('[JOB COMMAND] ERROR: Couldn\'t contact Octoprint /job API')
                print(e)

    def getstats(self, *args):
        try:
            if debug:
                print ('[GET STATS] Trying /job API request to Octoprint...')
            r = requests.get(jobapiurl, headers=headers, timeout=1)
        except requests.exceptions.RequestException as e:
            r = False
            if debug:
                print('[GET STATS] ERROR: Couldn\'t contact Octoprint /job API')
                print(e)
        if r and r.status_code == 200:
            if debug:
                print ('[GET STATS] JSON Data: ' + str(r.json()))
            printerstate = r.json()['state']
            jobfilename = r.json()['job']['file']['name']
            jobpercent = r.json()['progress']['completion']
            jobprinttime = r.json()['progress']['printTime']
            jobprinttimeleft = r.json()['progress']['printTimeLeft']
            if debug:
                print ('[GET STATS] Printer state: ' + printerstate)
                print ('[GET STATS] Job percent: ' + str(jobpercent) + '%')
            if jobfilename is not None:
                jobfilenamefull = jobfilename
                jobfilename = jobfilename[:25]  # Shorten filename to 25 characters
                self.ids.jobfilename.text = jobfilename
                self.ids.jobfilenamefull.text = jobfilenamefull
            else:
                self.ids.jobfilename.text = '-'
            if printerstate is not None:
                self.ids.printerstate.text = printerstate
                self.ids.printerstate2.text = printerstate
                self.ids.printerstate3.text = printerstate
            else:
                self.ids.printerstate.text = 'Unknown'
                self.ids.printerstate2.text = 'Unknown'
                self.ids.printerstate3.text = 'Unknown'
            if jobpercent is not None:
                jobpercent = int(jobpercent)
                self.ids.jobpercent.text = str(jobpercent) + '%'
                self.ids.progressbar.value = jobpercent
            else:
                self.ids.jobpercent.text = '---%'
                self.ids.progressbar.value = 0
            if jobprinttime is not None:
                hours = int(jobprinttime / 60 / 60)
                if hours > 0:
                    minutes = int(jobprinttime / 60) - (60 * hours)
                else:
                    minutes = int(jobprinttime / 60)
                seconds = int(jobprinttime % 60)
                self.ids.jobprinttime.text = str(hours).zfill(2) + ':' + \
                    str(minutes).zfill(2) + ':' + str(seconds).zfill(2)
            else:
                self.ids.jobprinttime.text = '00:00:00'
            if jobprinttimeleft is not None:
                hours = int(jobprinttimeleft / 60 / 60)
                if hours > 0:
                    minutes = int(jobprinttimeleft / 60) - (60 * hours)
                else:
                    minutes = int(jobprinttimeleft / 60)
                seconds = int(jobprinttimeleft % 60)
                self.ids.jobprinttimeleft.text = str(hours).zfill(2) + \
                    ':' + str(minutes).zfill(2) + ':' + str(seconds).zfill(2)
            else:
                self.ids.jobprinttimeleft.text = '00:00:00'

        else:
            if r:
                print ('Error. API Status Code: ' + str(r.status_code))  # Print API status code if we have one
            # If we can't get any values from Octoprint API fill with these values.
            self.ids.jobfilename.text = 'N/A'
            self.ids.printerstate.text = 'Unknown'
            self.ids.printerstate2.text = 'Unknown'
            self.ids.printerstate3.text = 'Unknown'
            self.ids.jobpercent.text = 'N/A'
            self.ids.progressbar.value = 0
            self.ids.jobprinttime.text = '--:--:--'
            self.ids.jobprinttimeleft.text = '--:--:--'

    def updateipaddr(self, *args):
        global platform
        global nicname  # Network card name from config file
        if 'linux' in platform or 'Linux' in platform:
            cmd = "ip addr show " + nicname + " | grep inet | awk '{print $2}' | cut -d/ -f1"
            p = Popen(cmd, shell=True, stdout=PIPE)
            output = p.communicate()[0]
            self.ids.ipaddr.text = output
        else:
            self.ids.ipaddr.text = 'Unknown Platform'

    def restartOS(self, *args):
        command = args[0]
        global platform
        if 'linux' in platform or 'Linux' in platform:
            print ('[RESTART] OS is going to ' + str(command))
            if command == 'reboot':
                cmd = "sudo shutdown now -r"
            elif command == 'shutdown':
                cmd = "sudo shutdown now -h"
            else:
                cmd = "true"
            os.system(cmd)
        else:
            print ('[RESTART] Unsupported OS')

    def exitapp(self, *args):
        exit()

    def restartnetworking(self, *args):
        global platform
        global nicname  # Network card name from config file
        if 'linux' in platform or 'Linux' in platform:
            cmd = "sudo ifdown " + nicname
            p = Popen(cmd, shell=True, stdout=PIPE)
            output = p.communicate()[0]
            if debug:
                print('[RESTART NETWORK]: ' + output)
            cmd = "sudo ifup " + nicname
            p = Popen(cmd, shell=True, stdout=PIPE)
            output = p.communicate()[0]
            if debug:
                print('[RESTART NETWORK]: ' + output)
        else:
            if debug:
                print('Unknown Platform. Not restarting network interface')

    def graphpoints(self, *args):
        hotendactual_plot = SmoothLinePlot(color=[1, 0, 0, 1])
        hotendtarget_plot = MeshLinePlot(color=[1, 0, 0, .75])
        bedactual_plot = SmoothLinePlot(color=[0, 0, 1, 1])
        bedtarget_plot = MeshLinePlot(color=[0, 0, 1, .75])
        # Build list of plot points tuples from temp and time lists
        # FIXME - Need to reduce the number of points on the graph. 360 is overkill
        hotendactual_points_list = []
        hotendtarget_points_list = []
        bedactual_points_list = []
        bedtarget_points_list = []
        for i in range(360):
            hotendactual_points_list.append((graphtime_list[i] / 1000.0 * -1, hotendactual_list[i]))
            hotendtarget_points_list.append((graphtime_list[i] / 1000.0 * -1, hotendtarget_list[i]))
            bedactual_points_list.append((graphtime_list[i] / 1000.0 * -1, bedactual_list[i]))
            bedtarget_points_list.append((graphtime_list[i] / 1000.0 * -1, bedtarget_list[i]))

        # Remove all old plots from the graph before drawing new ones
        for plot in self.my_graph.plots:
            self.my_graph.remove_plot(plot)

        # Draw the new graphs
        hotendactual_plot.points = hotendactual_points_list
        self.my_graph.add_plot(hotendactual_plot)
        hotendtarget_plot.points = hotendtarget_points_list
        self.my_graph.add_plot(hotendtarget_plot)
        bedactual_plot.points = bedactual_points_list
        self.my_graph.add_plot(bedactual_plot)
        bedtarget_plot.points = bedtarget_points_list
        self.my_graph.add_plot(bedtarget_plot)


class TabbedPanelApp(App):
    def build(self):
        Window.size = (800, 480)
        panels = Panels()
        Clock.schedule_once(panels.gettemps, 0.5)  # Update bed and hotend at startup
        Clock.schedule_interval(panels.gettemps, 5)  # Update bed and hotend temps every 5 seconds

        Clock.schedule_interval(panels.getstats, 5)  # Update job stats every 5 seconds

        Clock.schedule_once(panels.updateipaddr, 0.5)  # Update IP addr once right away
        Clock.schedule_interval(panels.updateipaddr, 30)  # Then update IP every 30 seconds

        Clock.schedule_interval(panels.graphpoints, 10)  # Update graphs
        return panels


if __name__ == '__main__':
    TabbedPanelApp().run()
